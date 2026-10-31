"""Exercise installer lifecycle without downloading dependencies in CI."""
import os
from pathlib import Path
import subprocess

SCRIPT = Path(__file__).parent.parent / 'install.sh'


def fake_python(tmp_path: Path) -> Path:
    p = tmp_path / 'fakepython'
    p.write_text('''#!/usr/bin/env bash
set -euo pipefail
if [[ "${1:-}" == "-c" ]]; then exit 0; fi
if [[ "${1:-}" == "-m" && "${2:-}" == "venv" ]]; then
  mkdir -p "$3/bin"
  cat > "$3/bin/python" <<'MOCK'
#!/usr/bin/env bash
set -euo pipefail
if [[ "${1:-}" == "-m" && "${2:-}" == "pip" ]]; then
  echo "pip installed" > "$HOME/pip-ran"
  exit 0
fi
if [[ "${1:-}" == "-m" && "${2:-}" == "mediacraft" ]]; then
  if [[ "${3:-}" == "doctor" || "${3:-}" == "--version" ]]; then exit 0; fi
fi
exit 1
MOCK
  chmod +x "$3/bin/python"
  exit 0
fi
exit 1
''')
    p.chmod(0o755)
    return p


def test_install_creates_only_private_files_and_owned_launcher(tmp_path):
    fake = fake_python(tmp_path)
    home = tmp_path / 'user'
    home.mkdir()
    env = os.environ.copy()
    env.update(HOME=str(home), PYTHON=str(fake))
    result = subprocess.run(['bash', str(SCRIPT)], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    root = home / '.local/share/mediacraft'
    assert (root / '.mediacraft-install').read_text().strip() == 'mediacraft-managed-install-v1'
    assert (root / 'uninstall.sh').is_file()
    launcher = home / '.local/bin/mediacraft'
    assert '# MEDIACRAFT_MANAGED_LAUNCHER' in launcher.read_text()
    assert (home / 'pip-ran').read_text().strip() == 'pip installed'
    removed = subprocess.run(['bash', str(root / 'uninstall.sh'), '--yes'], env=env,
                              capture_output=True, text=True)
    assert removed.returncode == 0, removed.stderr
    assert not root.exists()
    assert not launcher.exists()


def test_install_refuses_to_replace_unrelated_command(tmp_path):
    fake = fake_python(tmp_path)
    home = tmp_path / 'user'
    bin_dir = home / '.local/bin'
    bin_dir.mkdir(parents=True)
    (bin_dir / 'mediacraft').write_text('not mine')
    env = os.environ.copy()
    env.update(HOME=str(home), PYTHON=str(fake))
    result = subprocess.run(['bash', str(SCRIPT)], env=env, capture_output=True, text=True)
    assert result.returncode != 0
    assert (bin_dir / 'mediacraft').read_text() == 'not mine'
    assert not (home / '.local/share/mediacraft').exists()


def test_install_replaces_dangling_link_from_older_mediacraft(tmp_path):
    """v0.2 used an editable-install symlink which can become dangling."""
    fake = fake_python(tmp_path)
    home = tmp_path / 'user'
    bin_dir = home / '.local/bin'
    bin_dir.mkdir(parents=True)
    launcher = bin_dir / 'mediacraft'
    old = home / 'Downloads/MediaCraft-v0.2.0-Linux/mediacraft/.venv/bin/mediacraft'
    launcher.symlink_to(old)
    assert launcher.is_symlink() and not launcher.exists()
    env = os.environ.copy()
    env.update(HOME=str(home), PYTHON=str(fake))
    result = subprocess.run(['bash', str(SCRIPT)], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert launcher.is_file() and not launcher.is_symlink()
    assert '# MEDIACRAFT_MANAGED_LAUNCHER' in launcher.read_text()
    root = home / '.local/share/mediacraft'
    removed = subprocess.run(['bash', str(root / 'uninstall.sh'), '--yes'],
                             env=env, capture_output=True, text=True)
    assert removed.returncode == 0, removed.stderr
    assert not root.exists() and not launcher.exists()


def test_install_does_not_follow_symlink_to_current_environment(tmp_path):
    fake = fake_python(tmp_path)
    home = tmp_path / 'user'
    bin_dir = home / '.local/bin'
    bin_dir.mkdir(parents=True)
    root = home / '.local/share/mediacraft'
    entrypoint = root / 'venv/bin/mediacraft'
    entrypoint.parent.mkdir(parents=True)
    entrypoint.write_text('original pip-installed entrypoint')
    (root / '.mediacraft-install').write_text('mediacraft-managed-install-v1\n')
    launcher = bin_dir / 'mediacraft'
    launcher.symlink_to(entrypoint)
    env = os.environ.copy()
    env.update(HOME=str(home), PYTHON=str(fake))
    result = subprocess.run(['bash', str(SCRIPT)], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert not launcher.is_symlink()
    assert '# MEDIACRAFT_MANAGED_LAUNCHER' in launcher.read_text()
    assert entrypoint.read_text() == 'original pip-installed entrypoint'


def test_install_refuses_unrelated_dangling_link(tmp_path):
    fake = fake_python(tmp_path)
    home = tmp_path / 'user'
    bin_dir = home / '.local/bin'
    bin_dir.mkdir(parents=True)
    launcher = bin_dir / 'mediacraft'
    unrelated = home / 'unrelated/tool/bin/mediacraft'
    launcher.symlink_to(unrelated)
    env = os.environ.copy()
    env.update(HOME=str(home), PYTHON=str(fake))
    result = subprocess.run(['bash', str(SCRIPT)], env=env, capture_output=True, text=True)
    assert result.returncode != 0
    assert launcher.is_symlink() and launcher.readlink() == unrelated
    assert not (home / '.local/share/mediacraft').exists()
