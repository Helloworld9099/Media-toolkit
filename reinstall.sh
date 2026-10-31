#!/usr/bin/env bash
# Use this from a fresh ZIP to clean a broken older MediaCraft installation,
# then install the direct-command version. Never delete user media.
set -euo pipefail
SOURCE="$(cd "$(dirname "$0")" && pwd -P)"
echo '[1/2] Removing old MediaCraft installation and private downloads...'
bash "$SOURCE/uninstall.sh" --yes
echo
echo '[2/2] Installing MediaCraft with simple direct commands...'
bash "$SOURCE/install.sh"
