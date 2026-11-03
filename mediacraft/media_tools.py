"""Image, video, and animation operations."""

from __future__ import annotations

import math
import os
from pathlib import Path
import tempfile
from typing import Sequence

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

from .common import MediaCraftError, media_duration, output_path, output_prefix, require_program, run_ffmpeg, source_file


IMAGE_FORMATS = {"jpg": "JPEG", "jpeg": "JPEG", "png": "PNG", "webp": "WEBP", "avif": "AVIF"}
VIDEO_FORMATS = ("mp4", "mov", "mkv", "avi", "webm", "wmv")
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".wmv", ".m4v"}


def _image_format(filename: Path) -> str:
    suffix = filename.suffix.lower().lstrip(".")
    if suffix not in IMAGE_FORMATS:
        raise MediaCraftError(f"Unsupported image output format: .{suffix}")
    return IMAGE_FORMATS[suffix]


def _target(source: Path, output: str | Path | None, suffix: str, label: str, force: bool) -> Path:
    if output is None:
        filename = f"{output_prefix(source)}{label}.{suffix}"
        return output_path(source.with_name(filename), source, force=force)
    requested = Path(output).expanduser()
    # -o may be a file path or a directory; a missing suffix denotes a directory.
    if requested.suffix and not requested.is_dir():
        allowed = {f".{suffix}"} | ({".jpeg"} if suffix == "jpg" else set())
        if requested.suffix.lower() not in allowed:
            raise MediaCraftError(f"Output must have a .{suffix} extension.")
        return output_path(requested, source, force=force)
    return output_path(requested / f"{output_prefix(source)}{label}.{suffix}", source, force=force)


def _save_image(image: Image.Image, target: Path, *, quality: int = 95) -> Path:
    image_format = _image_format(target)
    if image_format == "AVIF" and ".avif" not in Image.registered_extensions():
        raise MediaCraftError("AVIF requires a Pillow build with AVIF support.")
    options: dict[str, object] = {}
    if image_format in ("JPEG", "WEBP", "AVIF"):
        options["quality"] = quality
    if image_format == "PNG":
        options["optimize"] = True
    if image_format == "JPEG":
        # JPEG cannot store transparency. A white backing preserves visibility.
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, "white")
        background.paste(rgba, mask=rgba.getchannel("A"))
        image = background
        options["subsampling"] = 0
    if image.info.get("icc_profile"):
        options["icc_profile"] = image.info["icc_profile"]
    with tempfile.NamedTemporaryFile(dir=target.parent, suffix=target.suffix, delete=False) as tmp:
        staged = Path(tmp.name)
    try:
        try:
            image.save(staged, format=image_format, **options)
        except (OSError, ValueError, KeyError) as exc:
            raise MediaCraftError(f"Unable to encode {image_format}: {exc}") from exc
        os.replace(staged, target)
    finally:
        staged.unlink(missing_ok=True)
    return target


def convert_image(path: str | Path, format: str, *, output: str | Path | None = None,
                  quality: int = 95, force: bool = False) -> Path:
    source = source_file(path)
    kind = format.lower().lstrip(".")
    if kind not in IMAGE_FORMATS:
        raise MediaCraftError(f"Unsupported image format: {format}")
    if not 1 <= quality <= 100:
        raise MediaCraftError("Quality must be between 1 and 100.")
    ext = "jpg" if kind == "jpeg" else kind
    target = _target(source, output, ext, "", force)
    try:
        with Image.open(source) as image:
            oriented = ImageOps.exif_transpose(image)
            oriented.load()
            return _save_image(oriented, target, quality=quality)
    except (OSError, ValueError) as exc:
        raise MediaCraftError(f"Cannot read image: {source}: {exc}") from exc


def convert_video(path: str | Path, format: str, *, output: str | Path | None = None,
                  force: bool = False) -> Path:
    source = source_file(path)
    kind = format.lower().lstrip(".")
    if kind not in VIDEO_FORMATS:
        raise MediaCraftError(f"Unsupported video format: {format}")
    target = _target(source, output, kind, "", force)
    ffmpeg = require_program("ffmpeg")
    params = {
        "mp4": ["-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart"],
        "mov": ["-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k"],
        "mkv": ["-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k"],
        "webm": ["-c:v", "libvpx-vp9", "-crf", "25", "-b:v", "0", "-c:a", "libopus", "-b:a", "160k"],
        "avi": ["-c:v", "mpeg4", "-q:v", "2", "-c:a", "libmp3lame", "-q:a", "2"],
        "wmv": ["-c:v", "wmv2", "-q:v", "2", "-c:a", "wmav2", "-b:a", "192k"],
    }
    with tempfile.NamedTemporaryFile(dir=target.parent, suffix=target.suffix, delete=False) as tmp:
        stage = Path(tmp.name)
    try:
        argv = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(source),
                "-map", "0:v:0", "-map", "0:a?", *params[kind], str(stage)]
        run_ffmpeg(argv, label=f"Convert video to {kind.upper()}", duration=media_duration(source))
        os.replace(stage, target)
    finally:
        stage.unlink(missing_ok=True)
    return target


def _dimensions(spec: str) -> tuple[int, int]:
    try:
        width, height = (int(value) for value in spec.lower().split("x"))
    except (ValueError, TypeError) as exc:
        raise MediaCraftError("Dimensions must be WIDTHxHEIGHT, e.g. 1280x720.") from exc
    if not (1 <= width <= 16000 and 1 <= height <= 16000 and width * height <= 100_000_000):
        raise MediaCraftError("Dimensions must be positive and no larger than 100 megapixels.")
    return width, height


def edit_image(path: str | Path, *, output: str | Path | None = None,
               crop: str | None = None, resize: str | None = None, rotate: float | None = None,
               flip: str | None = None, brightness: float = 1.0, contrast: float = 1.0,
               saturation: float = 1.0, sharpness: float = 1.0, grayscale: bool = False,
               sepia: bool = False, blur: float = 0, force: bool = False) -> Path:
    source = source_file(path)
    if not (crop or resize or rotate is not None or flip or grayscale or sepia or blur or
            any(v != 1 for v in (brightness, contrast, saturation, sharpness))):
        raise MediaCraftError("Choose at least one edit, e.g. --resize 1280x720 or --contrast 1.2.")
    if any(not math.isfinite(v) or v < 0 for v in (brightness, contrast, saturation, sharpness, blur)):
        raise MediaCraftError("Image adjustments must be nonnegative finite values.")
    if output and Path(output).suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".avif"}:
        target = output_path(output, source, force=force)
    else:
        target = _target(source, output, "png", "_edited", force)
    try:
        with Image.open(source) as original:
            image = ImageOps.exif_transpose(original).convert("RGBA")
            if crop:
                try:
                    x, y, width, height = (int(v.strip()) for v in crop.split(","))
                except ValueError as exc:
                    raise MediaCraftError("Crop must be x,y,width,height.") from exc
                if x < 0 or y < 0 or width <= 0 or height <= 0 or x + width > image.width or y + height > image.height:
                    raise MediaCraftError("Crop rectangle must fit inside the image.")
                image = image.crop((x, y, x + width, y + height))
            if resize:
                image = image.resize(_dimensions(resize), Image.Resampling.LANCZOS)
            if rotate is not None:
                if not math.isfinite(rotate):
                    raise MediaCraftError("Rotation must be a finite number.")
                image = image.rotate(rotate, resample=Image.Resampling.BICUBIC, expand=True)
            if flip == "horizontal":
                image = ImageOps.mirror(image)
            elif flip == "vertical":
                image = ImageOps.flip(image)
            if brightness != 1:
                image = ImageEnhance.Brightness(image).enhance(brightness)
            if contrast != 1:
                image = ImageEnhance.Contrast(image).enhance(contrast)
            if saturation != 1:
                image = ImageEnhance.Color(image).enhance(saturation)
            if sharpness != 1:
                image = ImageEnhance.Sharpness(image).enhance(sharpness)
            if grayscale:
                alpha = image.getchannel("A")
                image = ImageOps.grayscale(image).convert("RGBA")
                image.putalpha(alpha)
            if sepia:
                alpha = image.getchannel("A")
                gray = ImageOps.grayscale(image)
                image = ImageOps.colorize(gray, "#302018", "#f1d0a0").convert("RGBA")
                image.putalpha(alpha)
            if blur:
                image = image.filter(ImageFilter.GaussianBlur(radius=blur))
            return _save_image(image, target)
    except (OSError, ValueError) as exc:
        raise MediaCraftError(f"Cannot edit image: {exc}") from exc


def create_gif(paths: Sequence[str | Path], *, output: str | Path | None = None,
               fps: int = 10, width: int = 480, start: float = 0,
               duration: float = 5, force: bool = False) -> Path:
    if not paths:
        raise MediaCraftError("Provide at least one image or video.")
    if not (1 <= fps <= 30 and 16 <= width <= 1920 and 0 <= start <= 100_000 and 0 < duration <= 300):
        raise MediaCraftError("Use 1-30 FPS, width 16-1920, start >= 0, and duration 0-300 seconds.")
    sources = [source_file(x) for x in paths]
    first = sources[0]
    target = _target(first, output, "gif", "_animated", force)
    if len(sources) == 1 and first.suffix.lower() in VIDEO_EXTENSIONS:
        ffmpeg = require_program("ffmpeg")
        filter_graph = (f"[0:v]fps={fps},scale={width}:-1:flags=lanczos,split[a][b];"
                        "[a]palettegen=stats_mode=full[p];"
                        "[b][p]paletteuse=dither=sierra2_4a[v]")
        with tempfile.NamedTemporaryFile(dir=target.parent, suffix=".gif", delete=False) as tmp:
            stage = Path(tmp.name)
        try:
            argv = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-ss", str(start),
                    "-t", str(duration), "-i", str(first), "-filter_complex", filter_graph,
                    "-map", "[v]", "-an", "-loop", "0", str(stage)]
            run_ffmpeg(argv, label="Create GIF", duration=duration)
            os.replace(stage, target)
        finally:
            stage.unlink(missing_ok=True)
        return target
    if any(x.suffix.lower() in VIDEO_EXTENSIONS for x in sources):
        raise MediaCraftError("GIFs from video require exactly one video input.")
    frames: list[Image.Image] = []
    try:
        for source in sources:
            with Image.open(source) as im:
                frame = ImageOps.exif_transpose(im).convert("RGBA")
                frame.thumbnail((width, 1920), Image.Resampling.LANCZOS)
                frames.append(frame)
        canvas_size = (width, max(frame.height for frame in frames))
        composed = []
        for frame in frames:
            canvas = Image.new("RGB", canvas_size, "white")
            canvas.paste(frame, ((canvas.width - frame.width) // 2, (canvas.height - frame.height) // 2), frame)
            composed.append(canvas.quantize(colors=256, method=Image.Quantize.MEDIANCUT))
        with tempfile.NamedTemporaryFile(dir=target.parent, suffix=".gif", delete=False) as tmp:
            stage = Path(tmp.name)
        try:
            composed[0].save(stage, save_all=True, append_images=composed[1:],
                             duration=max(20, round(1000 / fps)), loop=0, optimize=True, disposal=2)
            os.replace(stage, target)
        finally:
            stage.unlink(missing_ok=True)
        return target
    except (OSError, ValueError) as exc:
        raise MediaCraftError(f"Cannot create GIF: {exc}") from exc
    finally:
        for frame in frames:
            frame.close()


def collage(paths: Sequence[str | Path], *, output: str | Path | None = None,
            columns: int = 2, tile: int = 500, gap: int = 8, force: bool = False) -> Path:
    if len(paths) < 2:
        raise MediaCraftError("Provide at least two images for a collage.")
    if not (1 <= columns <= 10 and 64 <= tile <= 2048 and 0 <= gap <= 256):
        raise MediaCraftError("Use 1-10 columns, tile size 64-2048, and gap 0-256.")
    sources = [source_file(x) for x in paths]
    target = _target(sources[0], output, "png", "_collage", force)
    cols = min(columns, len(sources))
    rows = math.ceil(len(sources) / cols)
    canvas = Image.new("RGB", (cols * tile + (cols + 1) * gap,
                               rows * tile + (rows + 1) * gap), "white")
    try:
        for i, source in enumerate(sources):
            with Image.open(source) as original:
                thumb = ImageOps.exif_transpose(original).convert("RGBA")
                thumb.thumbnail((tile, tile), Image.Resampling.LANCZOS)
                col = i % cols
                row = i // cols
                x = gap + col * (tile + gap) + (tile - thumb.width) // 2
                y = gap + row * (tile + gap) + (tile - thumb.height) // 2
                canvas.paste(thumb, (x, y), thumb)
        return _save_image(canvas, target)
    except (OSError, ValueError) as exc:
        raise MediaCraftError(f"Cannot create collage: {exc}") from exc
    finally:
        canvas.close()
