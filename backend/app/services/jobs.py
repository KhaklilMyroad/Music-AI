"""Background poller: reconciles queued/generating tracks against the engine."""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qs, urlsplit

from sqlmodel import Session, select

from ..config import get_settings
from ..db import engine
from ..models import Track, TrackStatus
from .acestep import get_acestep

log = logging.getLogger("crescendo.jobs")


_AUDIO_EXTS = (".mp3", ".wav", ".flac", ".opus", ".aac", ".ogg", ".m4a")


def _normalize_audio_path(value: str) -> str:
    """Reduce an engine download URL (/v1/audio?path=<urlencoded>) to the raw
    file path, so our streaming proxy can re-wrap it exactly once."""
    if "?" in value:
        inner = parse_qs(urlsplit(value).query).get("path", [None])[0]
        if inner:
            return inner
    return value


def _find_audio_path(node: Any) -> str | None:
    """Depth-first search for the first string that looks like an audio file.

    Engine versions disagree on where the file lands in the result JSON
    (top-level key, nested dict, list of takes), so match by extension anywhere.
    """
    if isinstance(node, str):
        low = node.lower()
        # match plain paths, URLs with trailing query (x.mp3?sig=1), and URLs
        # whose query carries the path (/v1/audio?path=...%5Cx.flac)
        if low.split("?", 1)[0].endswith(_AUDIO_EXTS) or low.endswith(_AUDIO_EXTS):
            return _normalize_audio_path(node)
        return None
    if isinstance(node, dict):
        values = node.values()
    elif isinstance(node, list):
        values = node
    else:
        return None
    for value in values:
        found = _find_audio_path(value)
        if found:
            return found
    return None


def _apply_result(track: Track, result: Any) -> None:
    """Copy engine result fields onto the track. Result shape per docs/en/API.md."""
    track.audio_path = _find_audio_path(result) or track.audio_path
    if not track.audio_path:
        log.warning("no audio file found in engine result: %r", result)
    if not isinstance(result, dict):
        return
    meta = result.get("metadata") if isinstance(result.get("metadata"), dict) else result
    track.bpm = meta.get("bpm", track.bpm)
    track.duration = meta.get("duration", meta.get("audio_duration", track.duration))
    track.key_scale = meta.get("key_scale", meta.get("key", track.key_scale))
    track.time_signature = meta.get("time_signature", track.time_signature)
    seed = meta.get("seed", result.get("seed"))
    if isinstance(seed, list) and seed:
        seed = seed[0]
    if isinstance(seed, int):
        track.seed = seed


async def poll_once() -> int:
    """One reconciliation pass. Returns the number of tracks still pending."""
    with Session(engine) as session:
        pending = session.exec(
            select(Track).where(
                Track.status.in_([TrackStatus.queued, TrackStatus.generating]),  # type: ignore[attr-defined]
                Track.engine_task_id.is_not(None),  # type: ignore[union-attr]
            )
        ).all()
        if not pending:
            return 0

        by_task = {t.engine_task_id: t for t in pending if t.engine_task_id}
        try:
            states = await get_acestep().query_results(list(by_task))
        except Exception as exc:  # noqa: BLE001 - engine may be briefly unreachable
            log.warning("engine poll failed: %s", exc)
            return len(pending)

        for task_id, state in states.items():
            track = by_task.get(task_id)
            if track is None:
                continue
            status = state.get("status")
            if status == 1:
                _apply_result(track, state.get("result") or {})
                track.status = TrackStatus.ready if track.audio_path else TrackStatus.failed
                if track.status is TrackStatus.failed:
                    track.error = "engine completed but returned no audio path"
            elif status == 2:
                track.status = TrackStatus.failed
                failure = state.get("result")
                if isinstance(failure, dict):
                    failure = failure.get("raw") or failure.get("error") or failure
                track.error = str(failure or "generation failed")
            else:
                track.status = TrackStatus.generating
            track.updated_at = datetime.now(timezone.utc)
            session.add(track)
        session.commit()
        return sum(1 for t in pending if t.status in (TrackStatus.queued, TrackStatus.generating))


async def poll_loop(stop: asyncio.Event) -> None:
    interval = get_settings().poll_interval_seconds
    while not stop.is_set():
        try:
            await poll_once()
        except Exception:  # noqa: BLE001
            log.exception("poll pass crashed")
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
        except asyncio.TimeoutError:
            pass
