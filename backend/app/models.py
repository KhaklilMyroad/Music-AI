from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import uuid4

from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TrackStatus(str, Enum):
    queued = "queued"
    generating = "generating"
    ready = "ready"
    failed = "failed"


class TaskType(str, Enum):
    text2music = "text2music"
    repaint = "repaint"
    cover = "cover"
    extract = "extract"  # generative stem separation
    complete = "complete"  # extend / continuation


class Track(SQLModel, table=True):
    id: str = Field(default_factory=lambda: uuid4().hex, primary_key=True)
    title: str = "Untitled"
    prompt: str = ""
    lyrics: str = ""
    task_type: TaskType = TaskType.text2music
    status: TrackStatus = TrackStatus.queued
    error: Optional[str] = None

    # ACE-Step engine linkage
    engine_task_id: Optional[str] = Field(default=None, index=True)
    audio_path: Optional[str] = None  # path on the engine host, streamed via our proxy
    seed: Optional[int] = None

    # Musical metadata (requested and/or detected by the engine)
    duration: Optional[float] = None
    bpm: Optional[int] = None
    key_scale: Optional[str] = None
    time_signature: Optional[str] = None
    vocal_language: Optional[str] = None

    # Studio lineage: edits/stems/extends point at their source track
    parent_id: Optional[str] = Field(default=None, foreign_key="track.id")

    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
