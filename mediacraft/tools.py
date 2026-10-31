"""MediaCraft-managed video binary discovery with system-tool fallback."""
from __future__ import annotations

from pathlib import Path
from functools import lru_cache
import shutil

from .common import MediaCraftError
from .progress import Progress


@lru_cache(maxsize=1)
def video_tools() -> tuple[str, str]:
    try:
        from static_ffmpeg.run import get_or_fetch_platform_executables_else_raise
        with Progress("Prepare FFmpeg tools (download if needed)"):
            ffmpeg, ffprobe = get_or_fetch_platform_executables_else_raise()
        if Path(ffmpeg).is_file() and Path(ffprobe).is_file():
            return str(ffmpeg), str(ffprobe)
    except Exception as exc:
        if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
            raise MediaCraftError(
                f"Video tools could not be downloaded ({exc}). "
                "Connect to the internet and retry the command."
            ) from exc
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if ffmpeg and ffprobe:
        return ffmpeg, ffprobe
    raise MediaCraftError("Video tools unavailable. Run MediaCraft installer again with internet access.")
