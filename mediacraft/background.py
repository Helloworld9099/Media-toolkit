"""Optional local rembg background removal (ONNX inference)."""

from __future__ import annotations

from pathlib import Path
import tempfile

from PIL import Image, ImageOps

from .common import MediaCraftError, output_path, output_prefix, publish_file, source_file
from .progress import Progress


# Keep model names explicit, so mistyped models do not trigger confusing downloads.
MODELS = ("bria-rmbg", "u2netp", "u2net", "isnet-general-use", "birefnet-general", "birefnet-portrait")


def remove_background(path: str | Path, output: str | Path | None, *, model: str, force: bool) -> Path:
    source = source_file(path)
    target = output_path(output or source.with_name(output_prefix(source) + "_background_removed.png"), source, force=force)
    if target.suffix.lower() != ".png":
        raise MediaCraftError("Background removal must output PNG to preserve transparency.")
    try:
        from rembg import new_session, remove
    except ImportError as exc:
        raise MediaCraftError(
            "Background model is not installed. Run: python -m pip install -e '.[background]' "
            "inside the MediaCraft virtual environment."
        ) from exc
    try:
        with Image.open(source) as img:
            oriented = ImageOps.exif_transpose(img).convert("RGBA")
            with Progress(f"Load background model: {model}"):
                session = new_session(model)
            with Progress("Remove background"):
                result = remove(oriented, session=session)
        with tempfile.NamedTemporaryFile(dir=target.parent, suffix=".png", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        try:
            with Progress("Save transparent image"):
                result.save(tmp_path, "PNG")
                publish_file(tmp_path, target)
        finally:
            tmp_path.unlink(missing_ok=True)
    except MediaCraftError:
        raise
    except Exception as exc:
        raise MediaCraftError(f"Background removal failed: {exc}") from exc
    return target
