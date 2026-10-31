"""Regression tests for removing the broken 0.3.x install before reinstalling."""
from __future__ import annotations

import pytest
import sys

pytestmark = pytest.mark.skipif(
    sys.platform != "linux",
    reason="Linux Bash installer lifecycle is tested on Linux; platform installers have separate smoke tests",
)


import os
from pathlib import Path
import subprocess

from test_installer import fake_python

SOURCE = Path(__file__).resolve().parent.parent


def _run(script: str, home: Path, *, python: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["HOME"] = str(home)
    if python is not None:
        env["PYTHON"] = str(python)
    return subprocess.run(["bash", str(SOURCE / script)], env=env, text=True,
                          capture_output=True, check=False)


def test_clean_reinstall_removes_old_models_but_keeps_media(tmp_path):
    home = tmp_path / "user"
    home.mkdir()
    fake = fake_python(tmp_path)
    root = home / ".local/share/mediacraft"
    root.mkdir(parents=True)
    (root / ".mediacraft-install").write_text("mediacraft-managed-install-v1\n")
    (root / "models").mkdir()
    (root / "models/speech-model.bin").write_bytes(b"old weights")
    (root / "cache").mkdir()
    (root / "cache/old.cache").write_bytes(b"cache")
    old_launcher = home / ".local/bin/mediacraft"
    old_launcher.parent.mkdir(parents=True)
    old_launcher.symlink_to(root / "venv/bin/mediacraft")
    photos = home / "Pictures"
    photos.mkdir()
    (photos / "photo.jpg").write_bytes(b"original image")
    (photos / "photo_background_removed.png").write_bytes(b"output image")

    result = _run("reinstall.sh", home, python=fake)
    assert result.returncode == 0, result.stdout + result.stderr
    assert not (root / "models/speech-model.bin").exists()
    assert not (root / "cache/old.cache").exists()
    assert (root / "venv/bin/python").is_file()
    assert old_launcher.is_file() and not old_launcher.is_symlink()
    assert "# MEDIACRAFT_MANAGED_LAUNCHER" in old_launcher.read_text()
    assert (photos / "photo.jpg").read_bytes() == b"original image"
    assert (photos / "photo_background_removed.png").read_bytes() == b"output image"
    assert "MEDIACRAFT_PATH_MANAGED" in (home / ".bashrc").read_text()

    uninstall = _run("uninstall.sh", home)
    # Interactive confirmation is required if --yes is omitted.
    assert uninstall.returncode != 0
    result = subprocess.run(["bash", str(SOURCE / "uninstall.sh"), "--yes"],
                            env={**os.environ, "HOME": str(home)}, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert not root.exists() and not old_launcher.exists()
    assert (photos / "photo.jpg").exists()
    assert "MEDIACRAFT_PATH_MANAGED" not in (home / ".bashrc").read_text()


def test_cleanup_removes_recognized_v02_venv_but_not_user_files(tmp_path):
    home = tmp_path / "user"
    home.mkdir()
    old_source = home / "Downloads/MediaCraft-v0.2.0-Linux/mediacraft"
    venv = old_source / ".venv"
    (venv / "bin").mkdir(parents=True)
    (venv / "pyvenv.cfg").write_text("home = /usr/bin/python3")
    (venv / "bin/mediacraft").write_text("#!/bin/sh\n")
    (old_source / "my-photo.png").write_bytes(b"preserve me")
    link = home / ".local/bin/mediacraft"
    link.parent.mkdir(parents=True)
    link.symlink_to(venv / "bin/mediacraft")
    result = subprocess.run(["bash", str(SOURCE / "uninstall.sh"), "--yes"],
                            env={**os.environ, "HOME": str(home)}, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert not venv.exists()
    assert not link.is_symlink()
    assert (old_source / "my-photo.png").read_bytes() == b"preserve me"


def test_reinstall_refuses_to_delete_unrecognized_folder(tmp_path):
    home = tmp_path / "user"
    home.mkdir()
    fake = fake_python(tmp_path)
    unknown = home / ".local/share/mediacraft"
    unknown.mkdir(parents=True)
    (unknown / "important.txt").write_text("user data")
    result = _run("reinstall.sh", home, python=fake)
    assert result.returncode != 0
    assert (unknown / "important.txt").read_text() == "user data"
    assert not (home / ".local/bin/mediacraft").exists()


def test_installer_does_not_duplicate_existing_bash_path(tmp_path):
    home = tmp_path / "user"
    home.mkdir()
    (home / ".bashrc").write_text('export PATH="$HOME/.local/bin:$PATH"\n# keep my work\n')
    fake = fake_python(tmp_path)
    result = _run("install.sh", home, python=fake)
    assert result.returncode == 0, result.stdout + result.stderr
    text = (home / ".bashrc").read_text()
    assert text.count('export PATH="$HOME/.local/bin:$PATH"') == 1
    assert "# keep my work" in text
    result = subprocess.run(["bash", str(SOURCE / "uninstall.sh"), "--yes"],
                            env={**os.environ, "HOME": str(home)}, capture_output=True, text=True)
    assert result.returncode == 0
    assert (home / ".bashrc").read_text() == text
