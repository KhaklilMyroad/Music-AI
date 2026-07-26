"""AI Producer endpoints — LLM calls routed through OmniRoute to minimize credit spend."""
from fastapi import APIRouter, HTTPException

from ..schemas import EnhanceRequest, LyricsRequest, PlanRequest
from ..services.llm import get_llm

router = APIRouter(prefix="/api/copilot", tags=["copilot"])


@router.post("/plan")
async def plan_song(req: PlanRequest):
    try:
        return await get_llm().plan_song(req.idea, req.language)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"producer LLM failed: {exc}") from exc


@router.post("/lyrics")
async def write_lyrics(req: LyricsRequest):
    try:
        return {"lyrics": await get_llm().write_lyrics(req.theme, req.language, req.style)}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"producer LLM failed: {exc}") from exc


@router.post("/enhance")
async def enhance_prompt(req: EnhanceRequest):
    try:
        return {"prompt": await get_llm().enhance_prompt(req.idea)}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"producer LLM failed: {exc}") from exc
