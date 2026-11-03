# Media Toolkit

Local media tools for Windows, macOS, and Linux. The command remains `mediacraft`.

## Installation

Install Python 3.11-3.13, download or clone the repository, and run the installer from its directory.

| System | Install command |
| --- | --- |
| Windows 10/11 (PowerShell) | `powershell -ExecutionPolicy Bypass -File .\install.ps1` |
| macOS (Terminal) | `bash install-macos.sh` |
| Linux (Terminal) | `bash install.sh` |

On Ubuntu, `sudo apt install python3-venv` may be required. Open a new terminal after installation.

## Commands

```text
mediacraft removebackground photo.jpg
mediacraft separatesounds recording.mp3
mediacraft separatesong music.mp3
mediacraft splitvideo clip.mp4
mediacraft splitdesign logo.svg
mediacraft convertimage photo.png webp
mediacraft convertvideo clip.mov mp4
mediacraft editimage photo.jpg --crop 10,10,400,400 --contrast 1.2
mediacraft creategif frame1.png frame2.png --fps 5
mediacraft creategif clip.mp4 --start 2 --duration 4
mediacraft collage photo1.jpg photo2.jpg photo3.jpg --columns 2
```

Image conversion supports JPG, PNG, WebP and AVIF (where Pillow supports AVIF). Video conversion supports MP4, MOV, MKV, AVI, WebM and WMV. Multiple images or videos can be converted in one command:

```text
mediacraft convertimage photo1.png photo2.png webp
mediacraft convertvideo clip1.mov clip2.mov mp4
```

Image editing supports `--crop x,y,width,height`, `--resize WIDTHxHEIGHT`, `--rotate`, `--flip horizontal|vertical`, `--brightness`, `--contrast`, `--saturation`, `--sharpness`, `--grayscale`, `--sepia` and `--blur`. For GIFs, use `--fps` and `--width`; video-to-GIF also accepts `--start` and `--duration`. For collages, use `--columns`, `--tile` and `--gap`.

Outputs are written alongside the source, with a different name. Use `-o` to choose another destination and `--force` to replace an existing output. Source media is not overwritten. Quote paths containing spaces.

## Quality and storage

MediaCraft does not include a second image or video processing runtime for these features. Image conversion, editing and collages use Pillow; video conversion and video-to-GIF use FFmpeg. Core dependencies install first; optional audio separation and background removal models download only when needed. Downloaded models are cached, and pip download caching is disabled.

PNG edits and collages are saved losslessly by default. Video conversion re-encodes its streams at quality-oriented settings; unlike `splitvideo`, it is not lossless. GIF uses a limited color palette. If your input has transparency and you export to JPEG, it is composited against white.

## Maintenance

```text
mediacraft doctor
mediacraft --help
mediacraft uninstall
```

For older Linux installations, `bash reinstall.sh` resets MediaCraft's managed installation. Uninstallation preserves user media and processed outputs.

## Development

```bash
python -m pip install -e '.[test]'
python -m pytest -q
```

CI covers Python tests and installer smoke tests on Linux, Windows and macOS. Optional inference models are not exercised by the automated suite.

## License

MediaCraft Pro CLI source is licensed under [MIT](LICENSE). Third-party processing libraries and pretrained models have their own licenses. The feature ideas from [Sacsam005/MediaCraft-PRO](https://github.com/Sacsam005/MediaCraft-PRO) were independently implemented; no code or assets were copied from that unlicensed project.
