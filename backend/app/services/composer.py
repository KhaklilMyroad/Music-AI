"""Section Composer: builds a track section-by-section for a real energy arc.

One-shot generation flattens the arrangement — the engine can't hold an
8-section arc in a single pass. The composer chains engine calls instead:
section 1 is generated from scratch, then each following section CONTINUES the
audio so far ('complete' task) with its own energy-specific prompt. The result
is one track whose intro, build, drop and breakdown were each explicitly
directed — then the mastering chain runs on top.
"""
import asyncio
import logging
from datetime import datetime, timezone

from sqlmodel import Session

from ..config import get_settings
from ..db import engine
from ..models import Track, TrackStatus
from .acestep import get_acestep
from .jobs import _find_audio_path
from .mastering import master_track

log = logging.getLogger("crescendo.composer")


class ComposeError(RuntimeError):
    pass


def _set(track_id: str, **fields) -> None:
    with Session(engine) as session:
        track = session.get(Track, track_id)
        if not track:
            return
        for key, value in fields.items():
            setattr(track, key, value)
        track.updated_at = datetime.now(timezone.utc)
        session.add(track)
        session.commit()


async def _run_engine_task(**kwargs) -> str:
    """Submit one engine task and poll it to completion; return the audio path."""
    client = get_acestep()
    task_id = await client.release_task(**kwargs)
    interval = get_settings().poll_interval_seconds
    for _ in range(int(1800 / max(interval, 0.05))):  # 30 min ceiling per section
        await asyncio.sleep(interval)
        states = await client.query_results([task_id])
        state = states.get(task_id)
        if not state:
            continue
        if state.get("status") == 1:
            path = _find_audio_path(state.get("result"))
            if not path:
                raise ComposeError("section completed but returned no audio")
            return path
        if state.get("status") == 2:
            raise ComposeError(f"section generation failed: {state.get('result')}")
    raise ComposeError("section generation timed out")


async def compose_track(
    track_id: str,
    base_prompt: str,
    sections: list[dict],
    *,
    model: str | None = None,
    inference_steps: int | None = None,
    guidance_scale: float | None = None,
    vocal_language: str | None = None,
) -> None:
    """Orchestrate the full multi-section build for an already-created Track."""
    audio_so_far: str | None = None
    total = len(sections)
    try:
        for idx, section in enumerate(sections, start=1):
            name = section.get("name", f"section {idx}")
            _set(track_id, status=TrackStatus.generating, stage=f"section {idx}/{total}: {name}")
            section_prompt = f"{base_prompt}, {section['prompt']}" if base_prompt else section["prompt"]
            common = dict(
                prompt=section_prompt,
                lyrics=section.get("lyrics", ""),
                audio_duration=float(section["duration"]),
                model=model,
                inference_steps=inference_steps,
                guidance_scale=guidance_scale,
                vocal_language=vocal_language,
            )
            if audio_so_far is None:
                audio_so_far = await _run_engine_task(task_type="text2music", **common)
            else:
                audio_so_far = await _run_engine_task(
                    task_type="complete", src_audio_path=audio_so_far, **common
                )
            log.info("compose %s: %s done (%s)", track_id, name, audio_so_far)

        _set(track_id, stage="mastering")
        local = await master_track(track_id, audio_so_far)
        _set(
            track_id,
            audio_path=audio_so_far,
            local_path=local,
            status=TrackStatus.ready,
            stage=None,
        )
    except Exception as exc:  # noqa: BLE001
        log.exception("compose failed for %s", track_id)
        _set(track_id, status=TrackStatus.failed, error=str(exc), stage=None)
