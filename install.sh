#!/usr/bin/env bash
# One-command installation. No root privileges, apt, global pip, or system changes.
set -euo pipefail
SOURCE="$(cd "$(dirname "$0")" && pwd -P)"
ROOT="$HOME/.local/share/mediacraft"
BIN="$HOME/.local/bin"
LAUNCHER="$BIN/mediacraft"
MARKER="$ROOT/.mediacraft-install"
PYTHON="${PYTHON:-}"
if [[ -z "$PYTHON" ]]; then
  for candidate in python3 python3.13 python3.12 python3.11; do
    if command -v "$candidate" >/dev/null 2>&1 &&
       "$candidate" -c 'import sys; assert (3,11) <= sys.version_info[:2] < (3,14)' 2>/dev/null; then
      PYTHON="$candidate"
      break
    fi
  done
fi
if [[ -z "$PYTHON" ]] || ! "$PYTHON" -c 'import sys; assert (3,11) <= sys.version_info[:2] < (3,14)' 2>/dev/null; then
  echo 'MediaCraft needs Python 3.11, 3.12 or 3.13.' >&2
  echo 'Install a supported Python version with venv and rerun bash install.sh.' >&2
  exit 1
fi
if [[ -e "$ROOT" || -L "$ROOT" ]] && [[ ! -f "$MARKER" || -L "$ROOT" || -L "$MARKER" || "$(cat "$MARKER" 2>/dev/null)" != 'mediacraft-managed-install-v1' ]]; then
  echo "Refusing to modify an unrecognized folder: $ROOT" >&2
  exit 1
fi
if [[ -e "$LAUNCHER" || -L "$LAUNCHER" ]]; then
  if [[ -L "$LAUNCHER" ]]; then
    old="$(readlink "$LAUNCHER")"
    if [[ "$old" != "$ROOT/venv/bin/mediacraft" && "$old" != */mediacraft/.venv/bin/mediacraft ]]; then
      echo "A different command already uses $LAUNCHER; refusing to overwrite it." >&2
      exit 1
    fi
  elif ! grep -q '^# MEDIACRAFT_MANAGED_LAUNCHER$' "$LAUNCHER"; then
    echo "A different command already uses $LAUNCHER; refusing to overwrite it." >&2
    exit 1
  fi
fi
mkdir -p "$ROOT" "$BIN" "$ROOT/models" "$ROOT/cache"
printf 'mediacraft-managed-install-v1\n' > "$MARKER"
# Indeterminate animation: installer/AI package time cannot be predicted.
# The pip log is retained for actionable error diagnostics.
run_with_progress() {
  local label="$1"
  shift
  local log="$ROOT/logs/installer.log"
  mkdir -p "$ROOT/logs"
  echo "$label"
  "$@" > "$log" 2>&1 &
  local task_pid=$!
  local frames=('| ' '/ ' '- ' '\\ ')
  local n=0
  local start=$SECONDS
  local elapsed=0
  if [[ -t 2 ]]; then
    while kill -0 "$task_pid" 2>/dev/null; do
      elapsed=$((SECONDS - start))
      local pos=$(( n % 18 ))
      local left="" right=""
      printf -v left '%*s' "$pos" ''
      printf -v right '%*s' "$((18 - pos))" ''
      left=${left// /-}
      right=${right// /-}
      printf '\r  [%-18s] %s %02d:%02d (elapsed)' "${left}====${right}" "${frames[n % 4]}" "$((elapsed / 60))" "$((elapsed % 60))" >&2
      n=$(( n + 1 ))
      sleep 0.15
    done
    printf '\r%80s\r' '' >&2
  fi
  local code=0
  wait "$task_pid" || code=$?
  elapsed=$((SECONDS - start))
  if [[ "$code" != 0 ]]; then
    echo "  [FAILED] ${label} (${elapsed}s). Details: $log" >&2
    tail -n 20 "$log" >&2
    return "$code"
  fi
  echo "  [==================] Done (${elapsed}s)"
}

if [[ ! -f "$ROOT/venv/bin/python" ]]; then
  echo "[1/3] Setting up MediaCraft's private Python environment..."
  if ! run_with_progress "Creating Python environment" "$PYTHON" -m venv "$ROOT/venv"; then
    echo 'Python virtual environments are unavailable. On Ubuntu install python3-venv and rerun bash install.sh.' >&2
    exit 1
  fi
fi
export PIP_NO_INPUT=1 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
export XDG_CACHE_HOME="$ROOT/cache"
echo '[2/3] Downloading and installing MediaCraft tools...'
run_with_progress "Installing MediaCraft dependencies" \
  "$ROOT/venv/bin/python" -m pip install --progress-bar off --prefer-binary --no-cache-dir "$SOURCE"
cp "$SOURCE/uninstall.sh" "$ROOT/uninstall.sh"
chmod 755 "$ROOT/uninstall.sh"
# Launcher manages all model caches within the private installation directory.
# Write a complete launcher to a new file and atomically replace the old path.
# Do not redirect into $LAUNCHER: that follows stale symlinks left by v0.2.
# It can also overwrite the virtualenv's pip-generated entry point.
TMP_LAUNCHER="$(mktemp "$BIN/.mediacraft-launcher.XXXXXXXX")"
trap 'rm -f -- "$TMP_LAUNCHER"' EXIT
cat > "$TMP_LAUNCHER" <<'LAUNCH'
#!/usr/bin/env bash
# MEDIACRAFT_MANAGED_LAUNCHER
set -euo pipefail
export MEDIACRAFT_HOME="$HOME/.local/share/mediacraft"
export REMBG_HOME="$MEDIACRAFT_HOME/models/rembg"
export U2NET_HOME="$REMBG_HOME"
export TORCH_HOME="$MEDIACRAFT_HOME/models/torch"
export HF_HOME="$MEDIACRAFT_HOME/models/huggingface"
export XDG_CACHE_HOME="$MEDIACRAFT_HOME/cache"
export PIP_NO_CACHE_DIR=1
export NUMBA_CACHE_DIR="$MEDIACRAFT_HOME/cache/numba"
mkdir -p "$REMBG_HOME" "$TORCH_HOME" "$HF_HOME" "$NUMBA_CACHE_DIR"
exec "$MEDIACRAFT_HOME/venv/bin/python" -m mediacraft "$@"
LAUNCH
chmod 755 "$TMP_LAUNCHER"
mv -fT -- "$TMP_LAUNCHER" "$LAUNCHER"
trap - EXIT
echo '[3/3] Preparing MediaCraft video tools (FFmpeg + FFprobe)...'
# static-ffmpeg installs both binaries inside the private virtual environment.
# A pre-existing system binary can be used if the platform binary is inaccessible.
if ! run_with_progress "Preparing FFmpeg/FFprobe" "$LAUNCHER" doctor --prepare-video; then
  echo 'Warning: FFmpeg could not be downloaded. MediaCraft will retry automatically when needed.' >&2
fi
# Install a persistent PATH entry only when the user does not already have one.
# This changes only a clearly tagged, reversible line in the user's Bash profile.
BASHRC="$HOME/.bashrc"
if ! grep -Fq 'export PATH="$HOME/.local/bin:$PATH"' "$BASHRC" 2>/dev/null; then
  printf '\nexport PATH="$HOME/.local/bin:$PATH" # MEDIACRAFT_PATH_MANAGED\n' >> "$BASHRC"
fi
# Verify launcher at installation time, not after the user discovers a broken command.
if ! "$LAUNCHER" --version >/dev/null 2>&1; then
  echo 'MediaCraft launcher failed its installation check. The installation is incomplete.' >&2
  exit 1
fi
echo
echo 'MediaCraft installed successfully.'
echo 'Open a NEW terminal, then use commands like:'
echo '  mediacraft removebackground photo.jpg'
echo '  mediacraft splitvideo clip.mp4'
echo '  mediacraft splitdesign logo.svg'
echo '  mediacraft --help'
if [[ ":$PATH:" != *":$BIN:"* ]]; then
  echo 'To use it in THIS terminal without reopening, run:'
  echo '  source ~/.bashrc'
fi
echo 'Run mediacraft uninstall to remove MediaCraft and its private downloads.'
