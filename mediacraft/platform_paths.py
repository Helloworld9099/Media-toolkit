"""Per-user installation and cache paths, shared across platforms."""
import os
import sys
from pathlib import Path

def installation_root():
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))) / "MediaCraft"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "MediaCraft"
    return Path.home() / ".local" / "share" / "mediacraft"
