# MediaCraft

MediaCraft is a command-line toolkit for separating audio, extracting video tracks, removing image backgrounds and exporting design elements. It runs on Windows, macOS and Linux; processing happens on your computer.

## Install

Requires Python **3.11–3.13** and internet access for the initial installation. Download or clone this repository, then run the command for your system from the project directory.

| System | Command |
| --- | --- |
| Windows 10/11 (PowerShell) | `powershell -ExecutionPolicy Bypass -File .\install.ps1` |
| macOS (Terminal) | `bash install-macos.sh` |
| Linux (Terminal) | `bash install.sh` |

On Ubuntu, you may need `sudo apt install python3-venv` first. After installation, open a new terminal and check:

```bash
mediacraft --version
mediacraft doctor
```

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

Core dependencies install with MediaCraft. Additional separation packages and models are downloaded on first use and cached for subsequent runs. Model downloads may take several gigabytes; pip's download cache is disabled to avoid retaining duplicate archives. Dependency and model downloads require contacting their respective upstream hosts.

## Uninstall

```bash
mediacraft uninstall
```

You can also run the corresponding `uninstall.ps1`, `uninstall-macos.sh` or `uninstall.sh` script from the repository. Uninstall removes the managed installation and model cache, not your source files or exported media.

For an older Linux installation that needs a clean reset, run `bash reinstall.sh`.

## Development

```bash
python -m pip install -e '.[test]'
python -m pytest -q
```

Continuous integration runs the tests on Linux, Windows and macOS. Optional model inference is not part of the automated test suite.

## License

MediaCraft is released under the [MIT License](LICENSE). Third-party packages and model weights have their own licenses.
