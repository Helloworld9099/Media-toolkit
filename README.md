# MediaCraft

**Local media-processing tools for the Linux terminal.** MediaCraft allows users to seperate video and audio tracks, removes image backgrounds, separates audio sources, and exports individual design elements.

## Commands

| Task | Command | Typical results |
| --- | --- | --- |
| Remove an image background | `mediacraft removebackground photo.jpg` | `photo_background_removed.png` |
| Split speech, music and sound effects | `mediacraft separatesounds scene.mp3` | `scene_speech.wav`, `scene_music.wav`, `scene_sound_effects.wav` |
| Separate song instruments | `mediacraft separatesong song.mp3` | `song_vocals.wav`, `song_drums.wav`, `song_bass.wav`, `song_other.wav` |
| Separate video from its audio | `mediacraft splitvideo clip.mp4` | `clip_video_only.mkv`, `clip_audio_track_1.wav` |
| Extract design components | `mediacraft splitdesign artwork.svg` | `artwork_part_1_*.svg`, `artwork_part_2_*.svg`, ... |

Filenames depend on the input and the audio or design elements it contains. Multiple audio tracks produce separately numbered files. Video extraction can copy video without re-encoding.

## Installation (Ubuntu / Linux)

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

### Design limitations

For SVG input, MediaCraft exports vector elements or groups, retaining SVG definitions and styling where possible. For flattened PNG/JPG input, it extracts **disconnected foreground regions**, not the original editable Figma, Illustrator or Photoshop layers. Overlapping objects cannot be reliably recovered from a flattened image.

### Audio limitations

Audio source separation is approximate: overlapping voices, music and effects may bleed between tracks. Music separation uses Demucs; speech/music/effects mode uses DBS; background removal uses rembg. These optional processing engines and model checkpoints are downloaded on first use. Downloads can be large and processing can be slow on a CPU. MediaCraft's own Python environment and model caches are kept inside its user-owned installation directory.

## Progress display

MediaCraft shows progress for installation, model preparation and processing. FFmpeg media operations and design exports show measurable percentages when available; model loading and other unknown-duration operations show an activity indicator and elapsed time instead of a fabricated percentage.

## Privacy and files

MediaCraft processes your files on your machine. It does not require a MediaCraft account or upload media to a MediaCraft server. Initial dependency and model downloads contact third-party package/model hosts. Do not commit private media files, generated manifests, credentials or downloaded model weights to a public repository.

The repository intentionally contains source code, installation scripts, tests and a small synthetic SVG fixture. It does not contain model weights, user media, private configuration or build outputs.

## Uninstall

```bash
mediacraft uninstall
```

Alternatively, run `bash uninstall.sh` from the repository. Uninstall deletes MediaCraft-owned application files, private dependencies and model caches, while preserving original files, exported media and shared system tools. Some caches from older installations outside the managed directory may be shared and are not automatically deleted.

## Tests

With an appropriate Python environment and FFmpeg installed:

```bash
python -m pip install -e '.[test]'
python -m pytest -q
```

Tests include synthetic media generation and mocked AI integrations. Passing them does not establish the quality of separately downloaded production models.

## License

MediaCraft's source code is licensed under the [MIT License](LICENSE). Its dependencies and optional pretrained models have separate licenses, which may restrict commercial use. Review the relevant model terms before distributing models or using them commercially.
