"""Uninstaller must never delete media or files not owned by MediaCraft."""
import os
from pathlib import Path
import subprocess

SCRIPT = Path(__file__).parent.parent / "uninstall.sh"


def _run(home: Path):
    env = os.environ.copy()
    env["HOME"] = str(home)
    return subprocess.run(["bash", str(SCRIPT), "--yes"], env=env,
                          text=True, capture_output=True)


def test_uninstall_refuses_unowned_directory(tmp_path):
    root = tmp_path / ".local/share/mediacraft"
    root.mkdir(parents=True)
    (root / "personal.txt").write_text("important")
    result = _run(tmp_path)
    assert result.returncode != 0
    assert (root / "personal.txt").read_text() == "important"


def test_uninstall_removes_only_managed_files(tmp_path):
    root = tmp_path / ".local/share/mediacraft"
    root.mkdir(parents=True)
    (root / ".mediacraft-install").write_text("mediacraft-managed-install-v1\n")
    (root / "venv").mkdir()
    (root / "models").mkdir()
    (root / "models/weights.bin").write_bytes(b"dummy model")
    bin_path = tmp_path / ".local/bin"
    bin_path.mkdir(parents=True)
    command = bin_path / "mediacraft"
    command.write_text("#!/bin/sh\n# MEDIACRAFT_MANAGED_LAUNCHER\n")
    personal = tmp_path / "Pictures/photo.jpg"
    personal.parent.mkdir()
    personal.write_bytes(b"original media")
    output = tmp_path / "Pictures/photo_background_removed.png"
    output.write_bytes(b"output media")
    result = _run(tmp_path)
    assert result.returncode == 0, result.stderr
    assert not root.exists()
    assert not command.exists()
    assert personal.read_bytes() == b"original media"
    assert output.read_bytes() == b"output media"


def test_uninstall_does_not_delete_unrelated_launcher(tmp_path):
    root = tmp_path / ".local/share/mediacraft"
    root.mkdir(parents=True)
    (root / ".mediacraft-install").write_text("mediacraft-managed-install-v1\n")
    bin_path = tmp_path / ".local/bin"
    bin_path.mkdir(parents=True)
    command = bin_path / "mediacraft"
    command.write_text("my command")
    result = _run(tmp_path)
    assert result.returncode == 0
    assert command.read_text() == "my command"


def test_uninstall_cleans_old_mediacraft_symlink(tmp_path):
    root = tmp_path / '.local/share/mediacraft'
    root.mkdir(parents=True)
    (root / '.mediacraft-install').write_text('mediacraft-managed-install-v1\n')
    link = tmp_path / '.local/bin/mediacraft'
    link.parent.mkdir(parents=True)
    old = tmp_path / 'Downloads/MediaCraft-v0.2.0-Linux/mediacraft/.venv/bin/mediacraft'
    link.symlink_to(old)
    assert link.is_symlink() and not link.exists()
    result = _run(tmp_path)
    assert result.returncode == 0, result.stderr
    assert not link.is_symlink()
    assert not root.exists()


def test_uninstall_preserves_unrelated_broken_symlink(tmp_path):
    root = tmp_path / '.local/share/mediacraft'
    root.mkdir(parents=True)
    (root / '.mediacraft-install').write_text('mediacraft-managed-install-v1\n')
    link = tmp_path / '.local/bin/mediacraft'
    link.parent.mkdir(parents=True)
    link.symlink_to(tmp_path / 'other-project/bin/mediacraft')
    result = _run(tmp_path)
    assert result.returncode == 0, result.stderr
    assert link.is_symlink()
