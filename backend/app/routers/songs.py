from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select

from ..db import get_session
from ..models import TaskType, Track, TrackStatus
from ..schemas import GenerateRequest
from ..services.acestep import AceStepError, get_acestep

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
        )
    except (AceStepError, Exception) as exc:  # noqa: BLE001
        raise HTTPException(502, f"engine rejected the task: {exc}") from exc
    session.add(track)
    session.commit()
    session.refresh(track)
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
async def stream_song(track_id: str, session: Session = Depends(get_session)):
    track = session.get(Track, track_id)
    if not track:
        raise HTTPException(404, "track not found")
    if track.status is not TrackStatus.ready or not track.audio_path:
        raise HTTPException(409, f"track is not ready (status={track.status})")
    ext = track.audio_path.rsplit(".", 1)[-1].lower()
    return StreamingResponse(
        get_acestep().stream_audio(track.audio_path),
        media_type=_MEDIA_TYPES.get(ext, "application/octet-stream"),
        headers={"Content-Disposition": f'inline; filename="{track.id}.{ext}"'},
    )
