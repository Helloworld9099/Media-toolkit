"""Optional processing dependencies and model cache paths."""
from __future__ import annotations

from importlib.util import find_spec
import json
import os
import shutil
from pathlib import Path
import subprocess
import sys

from .progress import Progress
from .platform_paths import installation_root

from .common import MediaCraftError

# Pinned DBS source archive.
DBS_ARCHIVE = (
    "https://github.com/JusperLee/Dynamic-Band-Splitting/archive/"
    "ff526463a58ee0278e7bd05c4b8bce112b743e34.zip"
)


def in_managed_install() -> bool:
    root = installation_root()
    return (root / ".mediacraft-install").is_file() and (
        Path(sys.prefix).resolve() == (root / "venv").resolve()
    )


def pipx_environment() -> str | None:
    """Return the pipx environment holding MediaCraft, if any."""
    if in_managed_install():
        return None
    try:
        metadata = json.loads(
            (Path(sys.prefix) / "pipx_metadata.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(metadata, dict):
        return None
    package = metadata.get("main_package")
    if not isinstance(package, dict):
        return None
    name = package.get("package")
    if not isinstance(name, str) or name.lower().replace("_", "-") != "mediacraft-cli":
        return None
    environment = metadata.get("environment")
    if isinstance(environment, str) and environment.strip():
        return environment.strip()
    return Path(sys.prefix).name


def configure_private_cache() -> None:
    """Set cache directories for managed installations."""
    if not in_managed_install():
        return
    root = installation_root()
    settings = {
        "REMBG_HOME": root / "models/rembg",
        "U2NET_HOME": root / "models/rembg",
        "TORCH_HOME": root / "models/torch",
        "HF_HOME": root / "models/huggingface",
        "XDG_CACHE_HOME": root / "cache",
        "NUMBA_CACHE_DIR": root / "cache/numba",
        "PIP_NO_CACHE_DIR": "1",
    }
    for name, value in settings.items():
        os.environ[name] = str(value)
    for path in (root / "models/rembg", root / "models/torch",
                 root / "models/huggingface", root / "cache/numba"):
        path.mkdir(parents=True, exist_ok=True)


def _pip(*args: str) -> None:
    if in_managed_install():
        command = [sys.executable, "-m", "pip", "install", "--disable-pip-version-check",
                   "--no-input", "--no-cache-dir", "--prefer-binary", *args]
    else:
        environment = pipx_environment()
        if environment is None:
            raise MediaCraftError("Automatic installation requires the MediaCraft installer or pipx.")
        pipx = shutil.which("pipx")
        if pipx is None:
            raise MediaCraftError(
                "pipx is not on PATH. Install pipx or use the MediaCraft installer "
                "to enable optional audio and image processing."
            )
        command = [pipx, "inject", environment, *args]
    logs = installation_root() / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    # Retain pip output for installation errors.
    log_path = logs / "latest-download.log"
    try:
        with log_path.open("w", encoding="utf-8") as report:
            with Progress("Download/install AI tools"):
                result = subprocess.run(command, check=False, stdout=report, stderr=subprocess.STDOUT)
    except OSError as exc:
        raise MediaCraftError(f"Unable to start automatic installation: {exc}") from exc
    if result.returncode:
        last_lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-8:]
        detail = "\n".join(last_lines)
        raise MediaCraftError(
            "Automatic download failed. Check your internet connection and disk space, "
            "then try again. No system packages were changed.\n"
            f"Log: {log_path}\n{detail}"
        )


def ensure_engine(engine: str) -> None:
    modules = {"background": "rembg", "music": "demucs", "scene": "dbs"}
    if engine not in modules:
        raise ValueError(f"Unknown engine: {engine}")
    if find_spec(modules[engine]) is not None:
        return
    if not in_managed_install() and pipx_environment() is None:
        raise MediaCraftError(
            "This feature needs additional tools. Use pipx to install mediacraft-cli "
            "or run the MediaCraft installer to enable safe, automatic installation."
        )
    labels = {
        "background": "Background removal",
        "music": "Vocal and instrument separation",
        "scene": "Speech, music and sound-effects separation",
    }
    print(f"\nFirst-time setup: {labels[engine]}")
    print("MediaCraft is downloading the required free tools automatically.")
    print("Audio AI downloads can be large (hundreds of MB to several GB).", flush=True)
    if engine == "background":
        _pip("rembg[cpu]>=2.0.85,<3")
    else:
        # macOS wheels are published on PyPI; the CPU-only PyTorch index is for Windows/Linux.
        if find_spec("torch") is None:
            if sys.platform == "darwin":
                _pip("torch", "torchaudio")
            else:
                _pip("torch", "torchaudio", "--index-url", "https://download.pytorch.org/whl/cpu")
        if engine == "music":
            _pip("demucs>=4.0.1,<5")
        else:
            _pip(DBS_ARCHIVE)
    import importlib
    importlib.invalidate_caches()
    if find_spec(modules[engine]) is None:
        raise MediaCraftError(f"{labels[engine]} was downloaded but could not be loaded. Try the command again.")
    print("Setup complete. Processing your file...\n", flush=True)
