#!/usr/bin/env bash
set -euo pipefail
SOURCE="$(cd "$(dirname "$0")" && pwd -P)"
ROOT="$HOME/Library/Application Support/MediaCraft"
BIN="$HOME/.local/bin"
MARKER="$ROOT/.mediacraft-install"
if [[ -e "$ROOT" ]] && [[ ! -f "$MARKER" || "$(cat "$MARKER")" != 'mediacraft-managed-install-v1' ]]; then echo "Unrecognized directory: $ROOT" >&2; exit 1; fi
PYTHON=''
for c in python3.12 python3.11 python3.13 python3; do if command -v "$c" >/dev/null && "$c" -c 'import sys; assert (3,11)<=sys.version_info[:2]<(3,14)' 2>/dev/null; then PYTHON="$c"; break; fi; done
if [[ -z "$PYTHON" ]]; then echo 'Install Python 3.11-3.13 (python.org or Homebrew) first.' >&2; exit 1; fi
mkdir -p "$ROOT" "$BIN"
printf 'mediacraft-managed-install-v1\n' > "$MARKER"
echo '[1/3] Creating private environment...'
[[ -f "$ROOT/venv/bin/python" ]] || "$PYTHON" -m venv "$ROOT/venv"
echo '[2/3] Installing core dependencies (AI tools download on first use)...'
PIP_NO_CACHE_DIR=1 "$ROOT/venv/bin/python" -m pip install --disable-pip-version-check --no-cache-dir "$SOURCE"
echo '[3/3] Installing command...'
LAUNCHER="$BIN/mediacraft"
if [[ -e "$LAUNCHER" ]] && ! grep -q '^# MEDIACRAFT_MAC_LAUNCHER$' "$LAUNCHER"; then echo "Refusing to overwrite $LAUNCHER" >&2; exit 1; fi
cat > "$LAUNCHER" <<'EOF'
#!/usr/bin/env bash
# MEDIACRAFT_MAC_LAUNCHER
ROOT="$HOME/Library/Application Support/MediaCraft"
export REMBG_HOME="$ROOT/models/rembg" U2NET_HOME="$ROOT/models/rembg" TORCH_HOME="$ROOT/models/torch" HF_HOME="$ROOT/models/huggingface" XDG_CACHE_HOME="$ROOT/cache" PIP_NO_CACHE_DIR=1
exec "$ROOT/venv/bin/python" -m mediacraft "$@"
EOF
chmod 755 "$LAUNCHER"
cp "$SOURCE/uninstall-macos.sh" "$ROOT/uninstall-macos.sh"
for profile in "$HOME/.zprofile"; do if ! grep -Fq '# MEDIACRAFT_PATH_MANAGED' "$profile" 2>/dev/null; then printf '\nexport PATH="$HOME/.local/bin:$PATH" # MEDIACRAFT_PATH_MANAGED\n' >> "$profile"; fi; done
"$LAUNCHER" --version
echo 'Done. Open a new Terminal, then run: mediacraft splitvideo clip.mp4'
