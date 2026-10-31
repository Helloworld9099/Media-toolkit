#!/usr/bin/env bash
set -euo pipefail
ROOT="$HOME/Library/Application Support/MediaCraft"
MARKER="$ROOT/.mediacraft-install"
[[ -f "$MARKER" && "$(cat "$MARKER")" == 'mediacraft-managed-install-v1' ]] || { echo 'Unrecognized installation; refusing to delete' >&2; exit 1; }
LAUNCHER="$HOME/.local/bin/mediacraft"
if [[ -f "$LAUNCHER" ]] && grep -q '^# MEDIACRAFT_MAC_LAUNCHER$' "$LAUNCHER"; then rm -f "$LAUNCHER"; fi
rm -rf -- "$ROOT"
echo 'MediaCraft removed. Original and generated media preserved.'
