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
import shutil
from datetime import datetime, timezone
from pathlib import Path

from sqlmodel import Session

from ..config import get_settings
from ..db import engine
from ..models import Track, TrackStatus
from .acestep import get_acestep
from .jobs import _find_audio_path
from .mastering import (
    download_engine_audio,
    master_file,
    master_track,
    post_production_enabled,
    run_ffmpeg,
)

log = logging.getLogger("crescendo.composer")

CROSSFADE_SECONDS = 1.5


async def _probe_duration(path: Path) -> float | None:
    proc = await asyncio.create_subprocess_exec(
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
    )
    out, _ = await proc.communicate()
    try:
        return float(out.strip())
    except (ValueError, TypeError):
        return None


async def _assemble(parts: list[tuple[Path, float]], out: Path) -> bool:
    """Concatenate section files with per-section gain and equal-power crossfades.

    This is what turns 8 generations into one track with a deliberate energy
    arc and musical seams (measured against a commercial reference: smooth
    transitions ~12 dB/s max, not jump cuts).
    """
    if len(parts) == 1:
        shutil.copyfile(parts[0][0], out)
        return True
    args: list[str] = []
    for path, _gain in parts:
        args += ["-i", str(path)]
    graph = "".join(f"[{i}:a]volume={gain}dB[v{i}];" for i, (_p, gain) in enumerate(parts))
    current = "v0"
    for i in range(1, len(parts)):
        nxt = f"x{i}"
        graph += f"[{current}][v{i}]acrossfade=d={CROSSFADE_SECONDS}:c1=tri:c2=tri[{nxt}];"
        current = nxt
    args += ["-filter_complex", graph.rstrip(";"), "-map", f"[{current}]", str(out)]
    return await run_ffmpeg(*args)


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


def _compile_arrangement_script(sections: list[dict]) -> str:
    """Compile the arc plan into one tagged lyric script.

    Research note: both Suno and ACE-Step's LM planner achieve coherent
    arrangements from a SINGLE generation guided by bracketed section tags in
    the lyrics — one plan, one key, one groove, musical transitions. Stitching
    separate generations can never recover that coherence, so single-pass is
    the default compose mode.
    """
    parts: list[str] = []
    for section in sections:
        name = section.get("name", "section")
        descriptor = section.get("prompt", "").strip()
        duration = section.get("duration")
        hint = f" (~{int(duration)}s)" if duration else ""
        tag = f"[{name}{hint}: {descriptor}]" if descriptor else f"[{name}{hint}]"
        lyric = (section.get("lyrics") or "").strip()
        parts.append(f"{tag}\n{lyric}" if lyric else tag)
    return "\n\n".join(parts)


async def compose_track(
    track_id: str,
    base_prompt: str,
    sections: list[dict],
    *,
    mode: str = "single",
    model: str | None = None,
    inference_steps: int | None = None,
    guidance_scale: float | None = None,
    vocal_language: str | None = None,
    thinking: bool = True,
) -> None:
    """Orchestrate the full arrangement build for an already-created Track."""
    if mode == "single":
        await _compose_single_pass(
            track_id, base_prompt, sections,
            model=model, inference_steps=inference_steps,
            guidance_scale=guidance_scale, vocal_language=vocal_language,
            thinking=thinking,
        )
        return
    await _compose_stitched(
        track_id, base_prompt, sections,
        model=model, inference_steps=inference_steps,
        guidance_scale=guidance_scale, vocal_language=vocal_language,
    )


async def _compose_single_pass(
    track_id: str,
    base_prompt: str,
    sections: list[dict],
    *,
    model: str | None,
    inference_steps: int | None,
    guidance_scale: float | None,
    vocal_language: str | None,
    thinking: bool = True,
) -> None:
    """One coherent generation over the full tagged arrangement script."""
    try:
        total = sum(float(s.get("duration", 0)) for s in sections)
        script = _compile_arrangement_script(sections)
        _set(track_id, status=TrackStatus.generating, stage="generating full arrangement",
             lyrics=script)
        audio = await _run_engine_task(
            task_type="text2music",
            prompt=base_prompt,
            lyrics=script,
            audio_duration=total if total > 0 else None,
            model=model,
            inference_steps=inference_steps,
            guidance_scale=guidance_scale,
            vocal_language=vocal_language,
            thinking=thinking,
        )
        _set(track_id, stage="mastering")
        local = await master_track(track_id, audio)
        _set(track_id, audio_path=audio, local_path=local,
             status=TrackStatus.ready, stage=None)
    except Exception as exc:  # noqa: BLE001
        log.exception("single-pass compose failed for %s", track_id)
        _set(track_id, status=TrackStatus.failed,
             error=str(exc) or type(exc).__name__, stage=None)


async def _compose_stitched(
    track_id: str,
    base_prompt: str,
    sections: list[dict],
    *,
    model: str | None = None,
    inference_steps: int | None = None,
    guidance_scale: float | None = None,
    vocal_language: str | None = None,
) -> None:
    """Legacy mode: chain per-section continuations and reassemble locally."""
    # 'complete' is only supported by the base model (engine support matrix),
    # so the whole chain runs on it for consistency.
    model = await get_acestep().base_model()
    inference_steps = 50
    audio_so_far: str | None = None
    total = len(sections)
    post = post_production_enabled()
    work_dir = Path(get_settings().media_dir) / f"compose_{track_id}"
    parts: list[tuple[Path, float]] = []  # (section file, gain dB from the arc plan)
    consumed = 0.0  # duration of the chained audio already covered by earlier parts
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

            if post:
                # keep only the NEW tail this section added, so we can reassemble
                # with our own crossfades and per-section gain automation
                full = await download_engine_audio(audio_so_far, work_dir / f"s{idx}.full.flac")
                actual = await _probe_duration(full)
                part = work_dir / f"s{idx}.part.flac"
                start = max(0.0, consumed - CROSSFADE_SECONDS)  # overlap feeds the crossfade
                if await run_ffmpeg("-ss", f"{start:.3f}", "-i", str(full), str(part)):
                    parts.append((part, float(section.get("gain", 0.0))))
                    if actual:
                        consumed = actual
                else:
                    post = False  # slicing failed; fall back to the chained audio

        local: str | None = None
        if post and parts:
            _set(track_id, stage="assembling arrangement")
            assembled = work_dir / "assembled.flac"
            if await _assemble(parts, assembled):
                _set(track_id, stage="mastering")
                local = await master_file(track_id, assembled)
        if local is None:
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
        _set(track_id, status=TrackStatus.failed,
             error=str(exc) or type(exc).__name__, stage=None)
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
