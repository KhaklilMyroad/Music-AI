import asyncio
import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from sqlmodel import Session, select

from ..db import get_session
from ..models import TaskType, Track, TrackStatus
from ..schemas import ComposeRequest, GenerateRequest
from ..services.acestep import AceStepError, get_acestep
from ..services.composer import compose_track

router = APIRouter(prefix="/api/songs", tags=["songs"])

_MEDIA_TYPES = {"mp3": "audio/mpeg", "wav": "audio/wav", "flac": "audio/flac",
                "opus": "audio/ogg", "aac": "audio/aac"}


@router.post("", status_code=201)
async def create_song(req: GenerateRequest, session: Session = Depends(get_session)):
    track = Track(
        title=req.title or (req.prompt[:60] if req.prompt else "Untitled"),
        prompt=req.prompt,
        lyrics=req.lyrics,
        task_type=TaskType.text2music,
        duration=req.duration,
        bpm=req.bpm,
        key_scale=req.key_scale,
        time_signature=req.time_signature,
        vocal_language=req.vocal_language,
        seed=req.seed,
    )
    try:
        track.engine_task_id = await get_acestep().release_task(
            task_type="text2music",
            prompt=req.prompt,
            lyrics=req.lyrics,
            audio_duration=req.duration,
            bpm=req.bpm,
            key_scale=req.key_scale,
            time_signature=req.time_signature,
            vocal_language=req.vocal_language,
            batch_size=req.batch_size,
            seed=req.seed,
            model=req.model,
            inference_steps=req.inference_steps,
            guidance_scale=req.guidance_scale,
        )
    except (AceStepError, Exception) as exc:  # noqa: BLE001
        raise HTTPException(502, f"engine rejected the task: {exc}") from exc
    session.add(track)
    session.commit()
    session.refresh(track)
    return track


@router.post("/compose", status_code=201)
async def compose_song(req: ComposeRequest, session: Session = Depends(get_session)):
    """Multi-section arrangement: each section is generated as a continuation of
    the previous one with its own energy prompt, then the result is mastered."""
    track = Track(
        title=req.title or f"{req.base_prompt[:50]} (composed)",
        prompt=req.base_prompt,
        lyrics="\n\n".join(
            f"[{s.name}]\n{s.lyrics}".strip() for s in req.sections if s.lyrics
        ),
        task_type=TaskType.compose,
        status=TrackStatus.queued,
        stage="queued",
        duration=sum(s.duration for s in req.sections),
        vocal_language=req.vocal_language,
    )
    session.add(track)
    session.commit()
    session.refresh(track)
    asyncio.create_task(compose_track(
        track.id,
        req.base_prompt,
        [s.model_dump() for s in req.sections],
        model=req.model,
        inference_steps=req.inference_steps,
        guidance_scale=req.guidance_scale,
        vocal_language=req.vocal_language,
    ))
    return track


@router.get("")
def list_songs(session: Session = Depends(get_session)):
    return session.exec(select(Track).order_by(Track.created_at.desc())).all()  # type: ignore[attr-defined]


@router.get("/{track_id}")
def get_song(track_id: str, session: Session = Depends(get_session)):
    track = session.get(Track, track_id)
    if not track:
        raise HTTPException(404, "track not found")
    return track


@router.delete("/{track_id}", status_code=204)
def delete_song(track_id: str, session: Session = Depends(get_session)):
    track = session.get(Track, track_id)
    if not track:
        raise HTTPException(404, "track not found")
    session.delete(track)
    session.commit()


@router.get("/{track_id}/audio")
async def stream_song(track_id: str, download: bool = False, session: Session = Depends(get_session)):
    track = session.get(Track, track_id)
    if not track:
        raise HTTPException(404, "track not found")
    if track.status is not TrackStatus.ready or not (track.audio_path or track.local_path):
        raise HTTPException(409, f"track is not ready (status={track.status})")
    disposition = "attachment" if download else "inline"
    safe_title = "".join(c for c in track.title if c.isalnum() or c in " -_")[:60] or track.id
    if track.local_path and os.path.exists(track.local_path):
        ext = track.local_path.rsplit(".", 1)[-1].lower()
        return FileResponse(
            track.local_path,
            media_type=_MEDIA_TYPES.get(ext, "application/octet-stream"),
            filename=f"{safe_title}.{ext}",
            content_disposition_type=disposition,
        )
    ext = track.audio_path.rsplit(".", 1)[-1].lower()
    return StreamingResponse(
        get_acestep().stream_audio(track.audio_path),
        media_type=_MEDIA_TYPES.get(ext, "application/octet-stream"),
        headers={"Content-Disposition": f'{disposition}; filename="{safe_title}.{ext}"'},
    )
