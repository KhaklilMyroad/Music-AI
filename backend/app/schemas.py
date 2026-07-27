from typing import Optional

from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    title: Optional[str] = None
    prompt: str = Field(..., min_length=1, description="Style description / tags")
    lyrics: str = ""
    duration: Optional[float] = Field(None, ge=10, le=600)
    bpm: Optional[int] = Field(None, ge=30, le=300)
    key_scale: Optional[str] = None
    time_signature: Optional[str] = None
    vocal_language: Optional[str] = None
    batch_size: int = Field(1, ge=1, le=8, description="Parallel takes (engine max 8)")
    seed: Optional[int] = None
    model: Optional[str] = Field(None, description="DiT model, e.g. acestep-v15-sft for quality")
    inference_steps: Optional[int] = Field(None, ge=1, le=200)
    guidance_scale: Optional[float] = Field(None, ge=0, le=30)


class RepaintRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    start: float = Field(..., ge=0)
    end: float = Field(..., gt=0)


class CoverRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    strength: float = Field(0.7, ge=0.0, le=1.0)


class ExtendRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    duration: Optional[float] = Field(None, ge=10, le=600)


class PlanRequest(BaseModel):
    idea: str = Field(..., min_length=1)
    language: Optional[str] = None


class LyricsRequest(BaseModel):
    theme: str = Field(..., min_length=1)
    language: str = "english"
    style: str = ""


class EnhanceRequest(BaseModel):
    idea: str = Field(..., min_length=1)
