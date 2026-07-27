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


class ComposeSection(BaseModel):
    name: str = Field(..., min_length=1)
    prompt: str = Field(..., min_length=1, description="Energy/production direction for this section")
    duration: float = Field(..., ge=5, le=120)
    lyrics: str = ""
    gain: float = Field(0.0, ge=-24, le=6, description="Section level in dB for the energy arc")


class ComposeRequest(BaseModel):
    title: Optional[str] = None
    base_prompt: str = Field(..., min_length=1, description="Shared style prompt for every section")
    sections: list[ComposeSection] = Field(..., min_length=2, max_length=12)
    vocal_language: Optional[str] = None
    model: Optional[str] = None
    inference_steps: Optional[int] = Field(None, ge=1, le=200)
    guidance_scale: Optional[float] = Field(None, ge=0, le=30)


class PlanRequest(BaseModel):
    idea: str = Field(..., min_length=1)
    language: Optional[str] = None


class LyricsRequest(BaseModel):
    theme: str = Field(..., min_length=1)
    language: str = "english"
    style: str = ""


class EnhanceRequest(BaseModel):
    idea: str = Field(..., min_length=1)
