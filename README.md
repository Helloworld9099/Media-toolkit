# MediaCraft

**Local media-processing tools for Windows, macOS, and Linux.** MediaCraft separates video and audio tracks, removes image backgrounds, separates audio sources, and exports individual design elements using the same simple commands on each platform.

## Commands

| Task | Command | Typical results |
| --- | --- | --- |
| Remove an image background | `mediacraft removebackground photo.jpg` | `photo_background_removed.png` |
| Split speech, music and sound effects | `mediacraft separatesounds scene.mp3` | `scene_speech.wav`, `scene_music.wav`, `scene_sound_effects.wav` |
| Separate song instruments | `mediacraft separatesong song.mp3` | `song_vocals.wav`, `song_drums.wav`, `song_bass.wav`, `song_other.wav` |
| Separate video from its audio | `mediacraft splitvideo clip.mp4` | `clip_video_only.mkv`, `clip_audio_track_1.wav` |
| Extract design components | `mediacraft splitdesign artwork.svg` | `artwork_part_1_*.svg`, `artwork_part_2_*.svg`, ... |

Filenames depend on the input and the audio or design elements it contains. Multiple audio tracks produce separately numbered files. Video extraction can copy video without re-encoding.

## Installation

Install **Python 3.11, 3.12, or 3.13**, then download or clone the repository and open a terminal inside the project folder.

### Windows 10/11

Open **PowerShell** in the project folder:

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

Open a new PowerShell window afterward and use the same `mediacraft` commands shown below. The Windows installer creates a private user installation and adds the launcher to your user PATH. Administrative privileges are not required for MediaCraft itself.

### macOS (Intel or Apple Silicon)

Open **Terminal** in the project folder:

```bash
bash install-macos.sh
```

Open a new Terminal window afterward. The installer adds `$HOME/.local/bin` to your shell PATH through `.zprofile`. On macOS, some optional AI packages may depend on your Python version and CPU architecture.

### Ubuntu / Linux

Requires **Python 3.11, 3.12 or 3.13** with `venv`, internet access for initial setup, and a Linux terminal. On Ubuntu, install the Python virtual-environment package if it is not already present:

```bash
sudo apt install python3-venv
```

Download or clone this repository, open a terminal inside its folder, then run:

```bash
bash install.sh
```

Open a new terminal and try:

```bash
mediacraft --version
mediacraft doctor
mediacraft --help
```

For an older or incomplete installation, use `bash reinstall.sh` from a fresh copy of the source. This removes **MediaCraft-owned** installation files and downloads before reinstalling; it does not remove your original or processed media.

## Usage

```bash
mediacraft removebackground "photo with spaces.jpg"
mediacraft separatesounds recording.wav
mediacraft separatesong music.mp3
mediacraft splitvideo movie.mkv
mediacraft splitdesign logo.svg
```

Outputs are written **beside the input file**, never inside an unexpected nested directory. Use `-o` to specify another output location. Existing outputs are protected unless you add `--force`.

```bash
mediacraft splitvideo "movie.mp4" -o ./extracted
mediacraft splitdesign "artwork.svg" --force
```

Run `mediacraft --help` for commands; advanced options are available through `mediacraft audio split`, `mediacraft video split` and `mediacraft design split`.

### Audio limitations

Audio source separation is approximate: overlapping voices, music and effects may bleed between tracks. Music separation uses Demucs; speech/music/effects mode uses DBS; background removal uses rembg. These optional processing engines and model checkpoints are downloaded on first use. Downloads can be large and processing can be slow on a CPU. MediaCraft's own Python environment and model caches are kept inside its user-owned installation directory.

## Storage and quality

MediaCraft installs core processing tools first; optional AI packages and model files are downloaded only when you first run a corresponding AI command. Downloads are cached and reused. Installation disables pip's download cache to avoid keeping duplicate package archives. When compatible CPU-only PyTorch wheels are available, MediaCraft requests them to avoid unnecessary CUDA downloads. It does **not** reduce model precision or re-encode copied video streams to save storage. AI downloads can still require substantial disk space.

## Privacy and files

MediaCraft processes your files on your machine. It does not require an account or any data sharing. Initial dependency and model downloads contact third-party package/model hosts. Do not commit private media files, generated manifests, credentials or downloaded model weights to a public repository.

## Uninstall

```bash
mediacraft uninstall
```

Alternatively, run `bash uninstall.sh` (Linux), `bash uninstall-macos.sh` (macOS), or `powershell -ExecutionPolicy Bypass -File .\uninstall.ps1` (Windows) from the repository. Uninstall deletes MediaCraft-owned application files, private dependencies and model caches, while preserving original files, exported media and shared system tools. Some caches from older installations outside the managed directory may be shared and are not automatically deleted.

## Tests

With an appropriate Python environment and FFmpeg installed:

```bash
python -m pip install -e '.[test]'
python -m pytest -q
```

Tests include synthetic media generation and mocked AI integrations. The GitHub Actions workflow tests Python on Ubuntu, Windows, and macOS. These checks do not validate optional AI model quality or replace a real Windows/macOS installation test.

## License

MediaCraft's source code is licensed under the [MIT License](LICENSE). Its dependencies and optional pretrained models have separate licenses, which may restrict commercial use. Review the relevant model terms before distributing models or using them commercially.
