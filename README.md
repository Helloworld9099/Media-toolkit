# MediaCraft

MediaCraft is a free, open-source command-line toolkit for removing image backgrounds, separating audio into stems, extracting video and audio tracks, and splitting SVG designs. It supports Windows, macOS, and Linux, with local processing rather than uploading your files to a service.

## Install

MediaCraft requires Python **3.11-3.13** and internet access during installation. Optional AI engines and models may require additional downloads when used for the first time.

### Quick install from PyPI (pipx)

After `mediacraft-cli` is published on PyPI, install [pipx](https://pipx.pypa.io/stable/installation/) if needed, then run:

```bash
pipx install mediacraft-cli
mediacraft --version
mediacraft doctor
```

This installs the `mediacraft` command in an isolated Python environment. On first use, background removal and audio-separation commands install their optional engines into that pipx environment. Keep `pipx` available on your PATH to enable this setup. Some audio engines and model weights can require several gigabytes of storage.

For an upgrade, run `pipx upgrade mediacraft-cli`. To remove a pipx installation, run `pipx uninstall mediacraft-cli`; do not use `mediacraft uninstall` for pipx installations. Downloaded model caches may need separate cleanup.

If pipx uses an unsupported Python version, specify a supported interpreter, for example: `pipx install --python python3.12 mediacraft-cli`.

### Alternative: repository installer

The repository installers remain supported. Download or clone this repository, then run the command for your system from its directory:

| System | Command |
| --- | --- |
| Windows 10/11 (PowerShell) | `powershell -ExecutionPolicy Bypass -File .\install.ps1` |
| macOS (Terminal) | `bash install-macos.sh` |
| Linux (Terminal) | `bash install.sh` |

On Ubuntu, you may need `sudo apt install python3-venv` first. After installation, open a new terminal and run `mediacraft --version` and `mediacraft doctor`.

## Commands

| Operation | Command | Output |
| --- | --- | --- |
| Remove background | `mediacraft removebackground photo.jpg` | `photo_background_removed.png` |
| Separate dialogue, music and effects | `mediacraft separatesounds scene.mp3` | `scene_speech.wav`, `scene_music.wav`, `scene_sound_effects.wav` |
| Separate song stems | `mediacraft separatesong song.mp3` | `song_vocals.wav`, `song_drums.wav`, `song_bass.wav`, `song_other.wav` |
| Extract video and audio | `mediacraft splitvideo clip.mp4` | `clip_video_only.mkv`, `clip_audio_track_1.wav` |
| Extract design elements | `mediacraft splitdesign artwork.svg` | Separate SVG components |

Files are saved beside the input by default. Use `-o` for a different destination and `--force` to replace existing outputs:

```bash
mediacraft splitvideo "clip with spaces.mp4" -o ./tracks
mediacraft splitdesign artwork.svg --force
```

Run `mediacraft --help` for the basic commands. Advanced options are under `mediacraft audio split`, `mediacraft video split` and `mediacraft design split`.

## Notes

- **Video:** FFmpeg copies video streams without re-encoding when possible. WAV audio exports can be substantially larger than compressed inputs.
- **Audio:** Music stems use Demucs; speech/music/effects separation uses Dynamic Band Splitting. Results are estimates and may contain bleed between sources.
- **Images:** Background removal uses rembg and produces a transparent PNG.
- **Designs:** SVG files can be split into elements and groups. For flattened images, MediaCraft extracts disconnected regions, not the original editable layers.

Core dependencies install with MediaCraft. With the repository installers or pipx, missing separation engines are installed on first use and models are cached for later runs. Model downloads may take several gigabytes; dependency downloads require reaching their upstream hosts. The repository installers use private MediaCraft caches; pipx uses the normal per-user engine caches.

## Uninstall

For pipx installations:

```bash
pipx uninstall mediacraft-cli
```

For installations made with the repository installer:

```bash
mediacraft uninstall
```

You can also run the corresponding `uninstall.ps1`, `uninstall-macos.sh` or `uninstall.sh` script from the repository. The repository uninstaller removes the managed installation and its model cache, not your source files or exported media. pipx removal does not necessarily clean up external model caches.

For an older Linux installation that needs a clean reset, run `bash reinstall.sh`.

## Development

```bash
python -m pip install -e '.[test]'
python -m pytest -q
```

Continuous integration runs the tests on Linux, Windows and macOS. Optional model inference is not part of the automated test suite.

## Publishing

Maintainers: see [docs/PUBLISHING.md](docs/PUBLISHING.md) for the GitHub release and PyPI Trusted Publishing instructions.

## License

MediaCraft is released under the [MIT License](LICENSE). Third-party packages and model weights have their own licenses.
