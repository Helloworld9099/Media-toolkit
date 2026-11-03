"""Image conversion, video conversion and composition tests."""
import json
from pathlib import Path
import shutil
import subprocess

import pytest
from PIL import Image

from mediacraft import cli, media_tools
from mediacraft.common import MediaCraftError


def image(path, color, size=(64, 48)):
    Image.new("RGBA", size, color).save(path)
    return path


def test_convert_image_formats_and_no_overwrite(tmp_path):
    source = image(tmp_path / "test.png", (200, 20, 30, 128))
    result = media_tools.convert_image(source, "jpg")
    assert result.name == "test.jpg"
    with Image.open(result) as saved:
        assert saved.format == "JPEG" and saved.size == (64, 48)
        assert saved.getpixel((0, 0))[0] > 220
    with pytest.raises(MediaCraftError, match="Output exists"):
        media_tools.convert_image(source, "jpg")
    result2 = media_tools.convert_image(source, "webp")
    with Image.open(result2) as saved:
        assert saved.format == "WEBP" and saved.size == (64, 48)
    if ".avif" in Image.registered_extensions():
        result3 = media_tools.convert_image(source, "avif")
        with Image.open(result3) as saved:
            assert saved.format == "AVIF" and saved.size == (64, 48)


def test_batch_image_cli_and_output_folder(tmp_path, capsys):
    first = image(tmp_path / "first.png", "blue")
    second = image(tmp_path / "second.png", "green")
    out = tmp_path / "converted"
    assert cli.main(["convertimage", str(first), str(second), "webp", "-o", str(out)]) == 0
    assert (out / "first.webp").is_file() and (out / "second.webp").is_file()
    assert cli.main(["convertimage", str(first), str(second), "webp", "-o", str(out)]) == 2
    assert "Output exists" in capsys.readouterr().err


def test_edit_image_preserves_source(tmp_path):
    source = image(tmp_path / "photo.png", (80, 120, 160, 200), (60, 40))
    result = media_tools.edit_image(source, crop="10,5,30,20", resize="90x60", grayscale=True)
    assert result.name == "photo_edited.png"
    with Image.open(result) as saved:
        assert saved.size == (90, 60) and saved.mode == "RGBA"
        red, green, blue, alpha = saved.getpixel((10, 10))
        assert red == green == blue and alpha == 200
    with Image.open(source) as original:
        assert original.size == (60, 40)
    jpeg = tmp_path / "edited.jpg"
    media_tools.edit_image(source, output=jpeg, brightness=1.2)
    with Image.open(jpeg) as saved:
        assert saved.format == "JPEG"


def test_edit_image_rejects_bad_arguments(tmp_path):
    source = image(tmp_path / "photo.png", "red")
    with pytest.raises(MediaCraftError, match="Choose at least one edit"):
        media_tools.edit_image(source)
    with pytest.raises(MediaCraftError, match="Crop rectangle"):
        media_tools.edit_image(source, crop="0,0,100,100")
    with pytest.raises(MediaCraftError, match="Dimensions"):
        media_tools.edit_image(source, resize="-1x123")


def test_collage_layout_and_images_unchanged(tmp_path):
    paths = [image(tmp_path / f"img{i}.png", c) for i, c in enumerate(("red", "green", "blue"))]
    result = media_tools.collage(paths, columns=2, tile=100, gap=5)
    with Image.open(result) as im:
        assert im.size == (215, 215)
        assert im.getpixel((50, 50)) == (255, 0, 0)
        assert im.getpixel((155, 50)) == (0, 128, 0)
    assert all(Path(p).is_file() for p in paths)


def test_images_to_gif(tmp_path):
    paths = [image(tmp_path / f"frame{i}.png", color) for i, color in enumerate(("red", "blue"))]
    result = media_tools.create_gif(paths, fps=5, width=120)
    with Image.open(result) as im:
        assert im.format == "GIF"
        assert im.n_frames == 2
        assert im.width == 120
        assert im.info["duration"] == 200
    assert all(p.is_file() for p in paths)


@pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="Requires FFmpeg")
def test_video_formats_and_video_to_gif(tmp_path, monkeypatch):
    # Use the system binaries instead of downloading an additional FFmpeg copy.
    monkeypatch.setattr("mediacraft.common.require_program", lambda which: shutil.which(which))
    monkeypatch.setattr("mediacraft.media_tools.require_program", lambda which: shutil.which(which))
    sample = tmp_path / "clip.mp4"
    subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
        "-i", "testsrc2=s=96x64:r=10:d=1", "-f", "lavfi",
        "-i", "sine=frequency=440:duration=1", "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-shortest", str(sample)
    ], check=True)
    for format in ("mov", "mkv", "avi", "webm", "wmv"):
        result = media_tools.convert_video(sample, format)
        assert result.is_file() and result.stat().st_size > 100
        probe = json.loads(subprocess.run([
            "ffprobe", "-v", "error", "-show_streams", "-of", "json", str(result)
        ], check=True, capture_output=True, text=True).stdout)
        assert any(stream["codec_type"] == "video" for stream in probe["streams"])
    gif = media_tools.create_gif([sample], fps=8, width=120, duration=1)
    with Image.open(gif) as image:
        assert image.format == "GIF" and image.n_frames > 1
        assert image.width == 120


def test_cli_version_and_help(capsys):
    assert cli.main([]) == 0
    help_text = capsys.readouterr().out
    for name in ("convertimage", "convertvideo", "editimage", "creategif", "collage"):
        assert name in help_text
    with pytest.raises(SystemExit) as exit_status:
        cli.main(["--version"])
    assert exit_status.value.code == 0


def test_output_path_and_force(tmp_path):
    source = image(tmp_path / "flower.png", (0, 0, 255, 200))
    explicit = tmp_path / "flower-export.jpeg"
    saved = media_tools.convert_image(source, "jpeg", output=explicit)
    assert saved == explicit
    with pytest.raises(MediaCraftError, match="Output exists"):
        media_tools.convert_image(source, "jpeg", output=explicit)
    assert media_tools.convert_image(source, "jpeg", output=explicit, force=True) == explicit


def test_conversion_error_preserves_existing_video(tmp_path, monkeypatch):
    source = tmp_path / "clip.mkv"
    source.write_bytes(b"input")
    existing = tmp_path / "clip.mp4"
    existing.write_bytes(b"original export")
    monkeypatch.setattr("mediacraft.media_tools.require_program", lambda which: "ffmpeg")
    monkeypatch.setattr("mediacraft.media_tools.media_duration", lambda source: 1.0)
    def fail(*args, **kwargs):
        raise MediaCraftError("codec unavailable")
    monkeypatch.setattr("mediacraft.media_tools.run_ffmpeg", fail)
    with pytest.raises(MediaCraftError, match="codec unavailable"):
        media_tools.convert_video(source, "mp4", force=True)
    assert existing.read_bytes() == b"original export"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["clip.mkv", "clip.mp4"]
