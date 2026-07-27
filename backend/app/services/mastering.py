"""Post-generation mastering chain (the layer Suno runs and raw engines skip).

Chain: rumble cut -> glue compression -> club EQ -> stereo widening ->
loudness normalization to a club/streaming target -> true-peak limiter.
Requires ffmpeg on PATH; when missing, tracks keep the raw engine audio.
"""
import asyncio
import logging
import shutil
from pathlib import Path

from ..config import get_settings
from .acestep import get_acestep

log = logging.getLogger("crescendo.mastering")

_warned_no_ffmpeg = False


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def _filter_chain(lufs: float) -> str:
    return (
        "highpass=f=28,"
        "acompressor=threshold=-18dB:ratio=3:attack=12:release=180:makeup=3dB,"
        "equalizer=f=60:t=q:w=1.1:g=1.5,"
        "equalizer=f=3200:t=q:w=1.4:g=1.2,"
        "equalizer=f=12000:t=h:w=0.7:g=2,"
        "stereotools=mlev=1.0:slev=1.12,"
        f"loudnorm=I={lufs}:TP=-0.8:LRA=9,"
        "alimiter=limit=0.97:level=false"
    )


async def master_track(track_id: str, engine_audio_path: str) -> str | None:
    """Download the raw engine audio, master it, return the local mastered path.

    Returns None when mastering is disabled/unavailable or fails — callers keep
    streaming the raw engine audio in that case.
    """
    global _warned_no_ffmpeg
    settings = get_settings()
    if not settings.mastering_enabled:
        return None
    if not ffmpeg_available():
        if not _warned_no_ffmpeg:
            log.warning(
                "ffmpeg not found - tracks will play unmastered. "
                "Install it (Windows: winget install ffmpeg) and restart to enable mastering."
            )
            _warned_no_ffmpeg = True
        return None

    media_dir = Path(settings.media_dir)
    media_dir.mkdir(parents=True, exist_ok=True)
    ext = engine_audio_path.rsplit(".", 1)[-1].lower() or "flac"
    raw_path = media_dir / f"{track_id}.raw.{ext}"
    mastered_path = media_dir / f"{track_id}.master.flac"

    try:
        with open(raw_path, "wb") as fh:
            async for chunk in get_acestep().stream_audio(engine_audio_path):
                fh.write(chunk)

        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y", "-i", str(raw_path),
            "-af", _filter_chain(settings.master_lufs),
            "-ar", "48000", str(mastered_path),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            log.error("mastering failed for %s: %s", track_id, stderr[-500:].decode(errors="ignore"))
            return None
        log.info("mastered %s -> %s", track_id, mastered_path.name)
        return str(mastered_path)
    except Exception:  # noqa: BLE001
        log.exception("mastering pipeline crashed for %s", track_id)
        return None
    finally:
        raw_path.unlink(missing_ok=True)
