"""AI Producer: LLM services routed through an OmniRoute gateway.

OmniRoute exposes an OpenAI-compatible /chat/completions endpoint and routes each
call through its fallback chain (subscription -> API key -> cheap -> free tiers),
so lyric writing and song planning cost near-zero credits.
"""
import json
import re
from typing import Any, Optional

import httpx

from ..config import get_settings

_SONG_PLAN_SYSTEM = """You are a world-class music producer and songwriter.
Given a user's idea, design a complete song plan for a text-to-music model.
Respond with ONLY a JSON object with these keys:
  "title": short evocative title,
  "prompt": rich English style description (genre, mood, instrumentation, production,
             era, vocal timbre) — comma-separated tags, no lyrics here,
  "lyrics": full structured lyrics with [verse]/[chorus]/[bridge] section tags, in the
             user's requested language (default: the language of the user's idea),
  "bpm": integer 60-180 fitting the style,
  "key_scale": e.g. "A minor",
  "time_signature": e.g. "4/4",
  "duration": integer seconds 60-240,
  "vocal_language": ISO language name of the lyrics (e.g. "english", "hebrew").
Write lyrics that scan naturally and rhyme where idiomatic for the language."""

_LYRICS_SYSTEM = """You are an award-winning lyricist fluent in 50+ languages including
Hebrew, Arabic, Spanish and Japanese. Write complete song lyrics with [verse]/[chorus]/
[bridge] section tags. Match the requested language, theme and mood. Return ONLY lyrics."""

_ENHANCE_SYSTEM = """You turn a casual music idea into a dense, high-signal style prompt
for a text-to-music diffusion model: genre, subgenre, mood, tempo feel, instrumentation,
production texture, era, vocal character. Comma-separated tags, English, one line,
no lyrics. Return ONLY the prompt line."""


class ProducerLLM:
    def __init__(self) -> None:
        s = get_settings()
        self.base_url = s.omniroute_base_url.rstrip("/")
        self.model = s.omniroute_model
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {s.omniroute_api_key}"},
            timeout=90.0,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _chat(self, system: str, user: str, temperature: float = 0.8) -> str:
        resp = await self._client.post(
            "/chat/completions",
            json={
                "model": self.model,
                "temperature": temperature,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()

    async def plan_song(self, idea: str, language: Optional[str] = None) -> dict[str, Any]:
        user = idea if not language else f"{idea}\n\nWrite the lyrics in {language}."
        raw = await self._chat(_SONG_PLAN_SYSTEM, user)
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            raise ValueError(f"planner returned no JSON: {raw[:200]}")
        return json.loads(match.group(0))

    async def write_lyrics(self, theme: str, language: str = "english", style: str = "") -> str:
        user = f"Theme: {theme}\nLanguage: {language}"
        if style:
            user += f"\nMusical style: {style}"
        return await self._chat(_LYRICS_SYSTEM, user)

    async def enhance_prompt(self, idea: str) -> str:
        return await self._chat(_ENHANCE_SYSTEM, idea, temperature=0.6)


_llm: Optional[ProducerLLM] = None


def get_llm() -> ProducerLLM:
    global _llm
    if _llm is None:
        _llm = ProducerLLM()
    return _llm
