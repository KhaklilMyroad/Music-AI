"""Background poller: reconciles queued/generating tracks against the engine."""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session, select

from ..config import get_settings
from ..db import engine
from ..models import Track, TrackStatus
from .acestep import get_acestep

log = logging.getLogger("crescendo.jobs")


def _apply_result(track: Track, result: dict[str, Any]) -> None:
    """Copy engine result fields onto the track. Result shape per docs/en/API.md."""
    if not isinstance(result, dict):
        return
    # The engine returns file path/url plus detected metadata; keys vary slightly
    # between versions, so probe the common spellings.
    for key in ("audio_path", "file", "file_path", "audio_url", "url", "path"):
        value = result.get(key)
        if isinstance(value, list) and value:
            value = value[0]
        if isinstance(value, str) and value:
            track.audio_path = value
            break
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
                track.error = str((state.get("result") or {}).get("raw", "generation failed"))
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
