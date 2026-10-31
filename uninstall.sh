#!/usr/bin/env bash
# Remove managed MediaCraft files from the current user account.
set -euo pipefail
ROOT="$HOME/.local/share/mediacraft"
LAUNCHER="$HOME/.local/bin/mediacraft"
MARKER="$ROOT/.mediacraft-install"

# Display activity while removing downloaded models and packages.
remove_with_progress() {
  local path="$1"
  echo "Removing MediaCraft private files: $path"
  rm -rf -- "$path" &
  local pid=$! index=0
  local start=$SECONDS
  if [[ -t 2 ]]; then
    while kill -0 "$pid" 2>/dev/null; do
      local pos=$((index % 19)) left="" right=""
      printf -v left '%*s' "$pos" ''
      printf -v right '%*s' "$((19 - pos))" ''
      left=${left// /-}
      right=${right// /-}
      printf '\r  [%-23s] working %02d:%02d' "${left}====${right}" \
        "$(((SECONDS - start) / 60))" "$(((SECONDS - start) % 60))" >&2
      index=$((index + 1))
      sleep 0.15
    done
    printf '\r%80s\r' '' >&2
  fi
  wait "$pid"
  echo "  [=======================] Done"
}

# Check the installation marker before deleting files.
if [[ -e "$ROOT" || -L "$ROOT" ]]; then
  if [[ -L "$ROOT" || -L "$MARKER" || ! -f "$MARKER" ]] ||
     [[ "$(cat "$MARKER" 2>/dev/null)" != 'mediacraft-managed-install-v1' ]]; then
    echo "Cannot verify ownership of $ROOT. Nothing was removed." >&2
    exit 1
  fi
fi

owns_launcher=0
if [[ -L "$LAUNCHER" ]]; then
  old="$(readlink "$LAUNCHER")"
  case "$old" in
    "$ROOT/venv/bin/mediacraft"|*/mediacraft/.venv/bin/mediacraft)
      owns_launcher=1 ;;
  esac
elif [[ -f "$LAUNCHER" && ! -L "$LAUNCHER" ]] &&
     grep -Fqx '# MEDIACRAFT_MANAGED_LAUNCHER' "$LAUNCHER" 2>/dev/null; then
  owns_launcher=1
fi

if [[ "${1:-}" != '--yes' ]] && [[ -d "$ROOT" || "$owns_launcher" == 1 ]]; then
  echo "Remove MediaCraft's app, private downloads, models and caches?"
  echo "Remove: $ROOT"
  echo "Keep: original media, processed files, downloads/ZIPs and system packages."
  read -r -p 'Type REMOVE to confirm: ' answer || exit 1
  [[ "$answer" == 'REMOVE' ]] || { echo 'Cancelled.'; exit 0; }
fi

if [[ "$owns_launcher" == 1 ]]; then
  rm -- "$LAUNCHER"
  echo 'Removed MediaCraft command launcher.'
fi
if [[ -d "$ROOT" ]]; then
  remove_with_progress "$ROOT"
  echo 'Removed private MediaCraft app, Python dependencies, models and caches.'
fi

# v0.2 used a local venv in its *extracted source folder*. Clean only
# recognizable MediaCraft venvs, not the source folder or nearby user media.
for old_env in \
  "$HOME/Downloads/MediaCraft-v0.2.0-Linux/mediacraft/.venv" \
  "$HOME/Downloads/MediaCraft-v0.2.0-Linux/.venv"; do
  if [[ -d "$old_env" && ! -L "$old_env" && -f "$old_env/pyvenv.cfg" && -f "$old_env/bin/mediacraft" ]]; then
    remove_with_progress "$old_env"
    echo "Removed old MediaCraft 0.2 environment: $old_env"
  fi
done

# Remove only a line this installer added. Preserve user's other shell edits.
if [[ -f "$HOME/.bashrc" && ! -L "$HOME/.bashrc" ]] &&
   grep -Fq '# MEDIACRAFT_PATH_MANAGED' "$HOME/.bashrc"; then
  sed -i '/^export PATH="\$HOME\/\.local\/bin:\$PATH" # MEDIACRAFT_PATH_MANAGED$/d' "$HOME/.bashrc"
fi

echo 'MediaCraft cleanup complete. Original and processed media were not touched.'
