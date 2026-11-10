"""Exercise the installed MediaCraft CLI with generated media files."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

from PIL import Image, ImageDraw


def invoke(python: Path, *args: object) -> str:
    command = [str(python), "-m", "mediacraft", *(str(value) for value in args)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=180, check=False)
    if result.returncode:
        raise RuntimeError(f"Command failed ({result.returncode}): {command}\n{result.stdout}\n{result.stderr}")
    return result.stdout


def checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python", required=True, type=Path)
    options = parser.parse_args()
    python = options.python.absolute()
    if not python.is_file():
        raise RuntimeError(f"Managed Python not found: {python}")
    for binary in ("ffmpeg", "ffprobe"):
        if not shutil.which(binary):
            raise RuntimeError(f"Native {binary} is not present on PATH")

    with tempfile.TemporaryDirectory(prefix="mediacraft-proof-") as folder:
        root = Path(folder)
        image = root / "picture.png"
        second = root / "second.png"
        preview = Image.new("RGB", (120, 80), "white")
        ImageDraw.Draw(preview).ellipse((20, 10, 100, 70), fill="navy")
        preview.save(image)
        Image.new("RGB", (120, 80), "green").save(second)
        original_hash = checksum(image)

        assert "0.7.0" in invoke(python, "--version")
        invoke(python, "doctor", "--prepare-video")

        invoke(python, "convertimage", image, "webp")
        with Image.open(root / "picture.webp") as out:
            assert out.format == "WEBP" and out.size == (120, 80)

        invoke(python, "editimage", image, "--crop", "10,10,90,60", "--resize", "90x60")
        with Image.open(root / "picture_edited.png") as out:
            assert out.size == (90, 60)

        invoke(python, "creategif", image, second, "--fps", 5)
        with Image.open(root / "picture_animated.gif") as out:
            assert out.format == "GIF" and out.n_frames == 2

        invoke(python, "collage", image, second, "--columns", 2)
        with Image.open(root / "picture_collage.png") as out:
            assert out.width > 500 and out.height > 500

        svg = root / "logo.svg"
        svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="40" height="30"><rect id="one" x="2" y="2" width="12" height="12" fill="red"/><circle id="two" cx="28" cy="15" r="8" fill="blue"/></svg>', encoding="utf-8")
        invoke(python, "splitdesign", svg)
        if not list(root.glob("logo_part_*.svg")):
            raise RuntimeError("SVG extraction produced no SVG components")

        movie = root / "clip.mkv"
        subprocess.run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", "color=c=blue:s=96x64:r=10:d=1",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
            "-shortest", "-c:v", "mpeg4", "-c:a", "aac", str(movie),
        ], check=True, capture_output=True, timeout=60)
        original_movie_hash = checksum(movie)

        invoke(python, "convertvideo", movie, "mp4")
        converted = root / "clip.mp4"
        assert converted.is_file() and converted.stat().st_size > 100
        details = subprocess.run([
            "ffprobe", "-v", "error", "-show_streams", "-of", "json", str(converted)
        ], capture_output=True, text=True, check=True, timeout=30)
        kinds = {s["codec_type"] for s in json.loads(details.stdout)["streams"]}
        assert {"video", "audio"} <= kinds

        invoke(python, "splitvideo", movie)
        assert (root / "clip_video_only.mkv").is_file()
        assert (root / "clip_audio_track_1.wav").is_file()

        invoke(python, "creategif", movie, "--fps", 8, "--duration", 1)
        with Image.open(root / "clip_animated.gif") as out:
            assert out.format == "GIF" and out.n_frames > 1

        assert checksum(image) == original_hash
        assert checksum(movie) == original_movie_hash
        print("Installed CLI: image conversion/editing, GIF, collage, SVG, video conversion/splitting and preservation passed.")


if __name__ == "__main__":
    main()
