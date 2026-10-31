#!/usr/bin/env bash
# Reinstall the managed Linux package and its dependencies.
set -euo pipefail
SOURCE="$(cd "$(dirname "$0")" && pwd -P)"
echo '[1/2] Removing old MediaCraft installation and private downloads...'
bash "$SOURCE/uninstall.sh" --yes
echo
echo '[2/2] Installing MediaCraft...'
bash "$SOURCE/install.sh"
