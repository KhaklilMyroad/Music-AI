"""Async client for the ACE-Step 1.5 REST engine (`uv run acestep-api`, default :8001).

Endpoint reference: ACE-Step-1.5/docs/en/API.md
  POST /release_task   -> {task_id, ...}      (task_type: text2music|repaint|cover|extract|complete)
  POST /query_result   -> per-task {status: 0 queued, 1 completed, 2 failed, result: json string}
  GET  /v1/audio?path= -> audio bytes
  GET  /v1/models, GET /v1/stats, GET /health
"""
import json
import time
from typing import Any, AsyncIterator, Optional

import httpx

from ..config import get_settings


class AceStepError(RuntimeError):
    pass


def _engine_relative(path: Optional[str]) -> Optional[str]:
    """Engine security rules reject absolute src paths unless they're in the
    system temp dir, but accept paths relative to the engine's working dir.
    Generated audio always lands under <engine>/.cache/acestep/, so slice from
    the .cache segment to produce an accepted relative path."""
    if not path:
        return path
    normalized = path.replace("\\", "/")
    idx = normalized.find(".cache/")
    if idx > 0:
        return normalized[idx:]
    return path


class AceStepClient:
    def __init__(self, base_url: Optional[str] = None, timeout: float = 120.0):
        settings = get_settings()
        self.base_url = (base_url or settings.acestep_api_url).rstrip("/")
        self.default_model = settings.acestep_model
        self.default_audio_format = settings.acestep_audio_format
        self._loaded_model_cache: tuple[float, Optional[str]] = (0.0, None)
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=timeout)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def health(self) -> bool:
        try:
            resp = await self._client.get("/health")
            return resp.status_code == 200
        except httpx.HTTPError:
            return False

    async def loaded_model(self) -> Optional[str]:
        """The DiT model configured on the engine (from /health), cached 60s."""
        ts, cached = self._loaded_model_cache
        if cached and time.monotonic() - ts < 60:
            return cached
        try:
            resp = await self._client.get("/health")
            data = resp.json()
            payload = data.get("data", data) if isinstance(data, dict) else {}
            model = payload.get("loaded_model")
        except Exception:  # noqa: BLE001
            model = None
        if model:
            self._loaded_model_cache = (time.monotonic(), model)
        return model

    async def _family(self) -> str:
        """Model family prefix matching what the engine actually runs, so we
        never ask an XL engine for a 2B model (or vice versa)."""
        loaded = await self.loaded_model()
        return "acestep-v15-xl" if loaded and "-xl-" in loaded else "acestep-v15"

    async def quality_model(self, quality: str) -> tuple[str, Optional[int]]:
        """Map a quality tier to (model, inference_steps) for this engine."""
        family = await self._family()
        if quality == "pro":
            return f"{family}-sft", 50
        return f"{family}-turbo", None

    async def base_model(self) -> str:
        """The base model of the engine's family (only one supporting extract/complete)."""
        return f"{await self._family()}-base"

    async def models(self) -> Any:
        resp = await self._client.get("/v1/models")
        resp.raise_for_status()
        return resp.json()

    async def stats(self) -> Any:
        resp = await self._client.get("/v1/stats")
        resp.raise_for_status()
        return resp.json()

    async def release_task(
        self,
        *,
        task_type: str = "text2music",
        prompt: str = "",
        lyrics: str = "",
        audio_duration: Optional[float] = None,
        bpm: Optional[int] = None,
        key_scale: Optional[str] = None,
        time_signature: Optional[str] = None,
        vocal_language: Optional[str] = None,
        batch_size: int = 1,
        seed: Optional[int] = None,
        audio_format: Optional[str] = None,
        thinking: bool = True,
        model: Optional[str] = None,
        inference_steps: Optional[int] = None,
        guidance_scale: Optional[float] = None,
        src_audio_path: Optional[str] = None,
        repainting_start: Optional[float] = None,
        repainting_end: Optional[float] = None,
        audio_cover_strength: Optional[float] = None,
        repaint_mode: Optional[str] = None,
        repaint_strength: Optional[float] = None,
        repaint_wav_crossfade_sec: Optional[float] = None,
    ) -> str:
        """Submit a generation/edit task. Returns the engine task_id."""
        payload: dict[str, Any] = {
            "task_type": task_type,
            "prompt": prompt,
            "lyrics": lyrics,
            "thinking": thinking,
            "model": model or self.default_model,
            "audio_format": audio_format or self.default_audio_format,
            "batch_size": max(1, min(batch_size, 8)),
        }
        optional = {
            "inference_steps": inference_steps,
            "guidance_scale": guidance_scale,
            "audio_duration": audio_duration,
            "bpm": bpm,
            "key_scale": key_scale,
            "time_signature": time_signature,
            "vocal_language": vocal_language,
            "seed": seed,
            "src_audio_path": _engine_relative(src_audio_path),
            "repainting_start": repainting_start,
            "repainting_end": repainting_end,
            "audio_cover_strength": audio_cover_strength,
            "repaint_mode": repaint_mode,
            "repaint_strength": repaint_strength,
            "repaint_wav_crossfade_sec": repaint_wav_crossfade_sec,
        }
        payload.update({k: v for k, v in optional.items() if v is not None})

        resp = await self._client.post("/release_task", json=payload)
        if resp.status_code >= 400:
            raise AceStepError(
                f"engine returned {resp.status_code} for {payload.get('task_type')}: "
                f"{resp.text[:400]}"
            )
        data = resp.json()
        task_id = data.get("task_id") or data.get("data", {}).get("task_id")
        if not task_id:
            raise AceStepError(f"engine did not return a task_id: {data}")
        return str(task_id)

    async def query_results(self, task_ids: list[str]) -> dict[str, dict[str, Any]]:
        """Poll task states. Returns {task_id: {status, result}} with result parsed."""
        resp = await self._client.post("/query_result", json={"task_id_list": task_ids})
        resp.raise_for_status()
        data = resp.json()
        items = data if isinstance(data, list) else data.get("data", data.get("results", []))
        out: dict[str, dict[str, Any]] = {}
        for item in items or []:
            if not isinstance(item, dict) or "task_id" not in item:
                continue
            result = item.get("result")
            if isinstance(result, str):
                try:
                    result = json.loads(result)
                except (ValueError, TypeError):
                    result = {"raw": result}
            out[str(item["task_id"])] = {"status": item.get("status"), "result": result}
        return out

    async def stream_audio(self, path: str) -> AsyncIterator[bytes]:
        """Stream an audio file from the engine host by its path."""
        async with self._client.stream("GET", "/v1/audio", params={"path": path}) as resp:
            resp.raise_for_status()
            async for chunk in resp.aiter_bytes():
                yield chunk


_client: Optional[AceStepClient] = None


def get_acestep() -> AceStepClient:
    global _client
    if _client is None:
        _client = AceStepClient()
    return _client
