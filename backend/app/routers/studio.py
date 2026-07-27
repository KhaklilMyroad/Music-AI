"""Studio operations: every edit spawns a new child track (non-destructive lineage)."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from ..db import get_session
from ..models import TaskType, Track, TrackStatus
from ..schemas import CoverRequest, ExtendRequest, RepaintRequest
from ..services.acestep import get_acestep

router = APIRouter(prefix="/api/studio", tags=["studio"])

# Engine model-support matrix (README Model Zoo): extract/complete are ONLY
# supported by the base model; repaint/cover need the 50-step CFG models —
# running them on turbo (8 steps, no CFG) produces noise instead of music.
# Model names are resolved per the engine's loaded family (2B vs XL).
async def _task_settings(task_type: TaskType) -> dict:
    client = get_acestep()
    if task_type in (TaskType.extract, TaskType.complete):
        return {"model": await client.base_model(), "inference_steps": 50}
    sft_model, steps = await client.quality_model("pro")
    if task_type is TaskType.cover:
        return {"model": sft_model, "inference_steps": steps}
    if task_type is TaskType.repaint:
        return {
            "model": sft_model,
            "inference_steps": steps,
            # blend the repainted region into its surroundings instead of the
            # engine default hard splice, and stay close to the source groove
            "repaint_wav_crossfade_sec": 0.4,
            "repaint_mode": "balanced",
        }
    return {}


def _ready_source(session: Session, track_id: str) -> Track:
    track = session.get(Track, track_id)
    if not track:
        raise HTTPException(404, "source track not found")
    if track.status is not TrackStatus.ready or not track.audio_path:
        raise HTTPException(409, "source track has no audio yet")
    return track


async def _spawn_child(
    session: Session,
    source: Track,
    task_type: TaskType,
    prompt: str,
    *,
    title_suffix: str,
    duration: Optional[float] = None,
    repainting_start: Optional[float] = None,
    repainting_end: Optional[float] = None,
    audio_cover_strength: Optional[float] = None,
) -> Track:
    child = Track(
        title=f"{source.title} ({title_suffix})",
        prompt=prompt,
        lyrics=source.lyrics,
        task_type=task_type,
        parent_id=source.id,
        duration=duration or source.duration,
        vocal_language=source.vocal_language,
    )
    try:
        child.engine_task_id = await get_acestep().release_task(
            task_type=task_type.value,
            prompt=prompt,
            lyrics=source.lyrics,
            src_audio_path=source.audio_path,
            audio_duration=duration,
            repainting_start=repainting_start,
            repainting_end=repainting_end,
            audio_cover_strength=audio_cover_strength,
            **(await _task_settings(task_type)),
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"engine rejected the task: {exc}") from exc
    session.add(child)
    session.commit()
    session.refresh(child)
    return child


@router.post("/{track_id}/repaint", status_code=201)
async def repaint(track_id: str, req: RepaintRequest, session: Session = Depends(get_session)):
    if req.end <= req.start:
        raise HTTPException(422, "end must be after start")
    source = _ready_source(session, track_id)
    return await _spawn_child(
        session, source, TaskType.repaint, req.prompt, title_suffix="repaint",
        repainting_start=req.start, repainting_end=req.end,
    )


@router.post("/{track_id}/cover", status_code=201)
async def cover(track_id: str, req: CoverRequest, session: Session = Depends(get_session)):
    source = _ready_source(session, track_id)
    return await _spawn_child(
        session, source, TaskType.cover, req.prompt, title_suffix="cover",
        audio_cover_strength=req.strength,
    )


@router.post("/{track_id}/stems", status_code=201)
async def stems(track_id: str, session: Session = Depends(get_session)):
    source = _ready_source(session, track_id)
    return await _spawn_child(
        session, source, TaskType.extract, source.prompt, title_suffix="stems",
    )


@router.post("/{track_id}/extend", status_code=201)
async def extend(track_id: str, req: ExtendRequest, session: Session = Depends(get_session)):
    source = _ready_source(session, track_id)
    return await _spawn_child(
        session, source, TaskType.complete, req.prompt, title_suffix="extended",
        duration=req.duration,
    )
