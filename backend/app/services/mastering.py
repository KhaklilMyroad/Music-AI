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
    # Tuned against a reference commercial master (measured: sub<60Hz dominant,
    # smooth downward tilt, integrated -12.2 LUFS, LRA ~5).
    return (
        "highpass=f=25,"
        "acompressor=threshold=-18dB:ratio=3:attack=12:release=180:makeup=3dB,"
        "bass=g=2.5:f=50:t=q:w=0.6,"          # deep sub foundation
        "equalizer=f=100:t=q:w=1.2:g=-1.5,"   # tame boomy mid-bass
        "equalizer=f=3200:t=q:w=1.4:g=1.2,"   # presence
        "treble=g=1.5:f=9000:t=s,"            # air
        "stereotools=mlev=1.0:slev=1.12,"
        f"loudnorm=I={lufs}:TP=-0.8:LRA=6,"
        "alimiter=limit=0.97:level=false"
    )


def post_production_enabled() -> bool:
    """True when the local post chain (assembly + mastering) can run."""
    global _warned_no_ffmpeg
    if not get_settings().mastering_enabled:
        return False
    if not ffmpeg_available():
        if not _warned_no_ffmpeg:
            log.warning(
                "ffmpeg not found - tracks will play unmastered. "
                "Install it (Windows: winget install ffmpeg) and restart to enable mastering."
            )
            _warned_no_ffmpeg = True
        return False
    return True


async def run_ffmpeg(*args: str) -> bool:
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", *args,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        log.error("ffmpeg failed: %s", stderr[-500:].decode(errors="ignore"))
        return False
    return True


async def download_engine_audio(engine_audio_path: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "wb") as fh:
        async for chunk in get_acestep().stream_audio(engine_audio_path):
            fh.write(chunk)
    return dest


async def master_file(track_id: str, local_input: Path) -> str | None:
    """Run the mastering chain on a local file; return the mastered path."""
    if not post_production_enabled():
        return None
    settings = get_settings()
    media_dir = Path(settings.media_dir)
    media_dir.mkdir(parents=True, exist_ok=True)
    mastered_path = media_dir / f"{track_id}.master.flac"
    ok = await run_ffmpeg(
        "-i", str(local_input),
        "-af", _filter_chain(settings.master_lufs),
        "-ar", "48000", str(mastered_path),
    )
    if ok:
        log.info("mastered %s -> %s", track_id, mastered_path.name)
        return str(mastered_path)
    return None


async def master_track(track_id: str, engine_audio_path: str) -> str | None:
    """Download the raw engine audio, master it, return the local mastered path.

    Returns None when mastering is disabled/unavailable or fails — callers keep
    streaming the raw engine audio in that case.
    """
    if not post_production_enabled():
        return None
    settings = get_settings()
    ext = engine_audio_path.rsplit(".", 1)[-1].lower() or "flac"
    raw_path = Path(settings.media_dir) / f"{track_id}.raw.{ext}"
    try:
        await download_engine_audio(engine_audio_path, raw_path)
        return await master_file(track_id, raw_path)
    except Exception:  # noqa: BLE001
        log.exception("mastering pipeline crashed for %s", track_id)
        return None
    finally:
        raw_path.unlink(missing_ok=True)
