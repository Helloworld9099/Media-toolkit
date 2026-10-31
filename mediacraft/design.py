"""SVG element export and raster component extraction."""

from __future__ import annotations

import copy
from pathlib import Path

from defusedxml import ElementTree as SafeET
import cv2
import numpy as np
from PIL import Image, ImageOps
from xml.etree import ElementTree as ET

from .common import (MediaCraftError, dump_json, output_prefix, safe_label,
                     source_file, staged_directory)
from .progress import Progress


SVG_NS = "http://www.w3.org/2000/svg"
DRAWABLE = {
    "g", "path", "rect", "circle", "ellipse", "polygon", "polyline", "line",
    "text", "image", "use", "switch",
}


def _svg_tag(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1] if isinstance(element.tag, str) else ""


def _drawable_children(element: ET.Element) -> list[ET.Element]:
    return [child for child in element if _svg_tag(child) in DRAWABLE]


def _paths_at_depth(node: ET.Element, depth: int, prefix: tuple[int, ...] = ()) -> list[tuple[int, ...]]:
    children = _drawable_children(node)
    if depth == 1:
        return [prefix + (n,) for n in range(len(children))]
    result = []
    for i, child in enumerate(children):
        if _svg_tag(child) in ("g", "switch"):
            result += _paths_at_depth(child, depth - 1, prefix + (i,))
    return result


def _follow_path(root: ET.Element, path: tuple[int, ...]) -> ET.Element:
    node = root
    for i in path:
        node = _drawable_children(node)[i]
    return node


def _prune_to(root: ET.Element, path: tuple[int, ...]) -> None:
    node = root
    for index in path:
        drawable = _drawable_children(node)
        if index >= len(drawable):
            raise MediaCraftError("SVG changed while processing layers.")
        keep = drawable[index]
        for sibling in drawable:
            if sibling is not keep:
                node.remove(sibling)
        # Everything in metadata/defs/styles is kept so references remain valid.
        node = keep


def _strip_active_svg_content(root: ET.Element) -> None:
    """Remove scripts and event handlers from SVG exports.

    External references are retained, so exported SVGs are not safe to
    embed directly in untrusted web pages.
    """
    for node in root.iter():
        for child in list(node):
            if _svg_tag(child).lower() in ("script", "foreignobject"):
                node.remove(child)
        for attr in list(node.attrib):
            short = attr.rsplit("}", 1)[-1].lower()
            value = node.attrib[attr].strip().lower()
            if short.startswith("on") or (short == "href" and value.startswith(("javascript:", "data:text/html"))):
                del node.attrib[attr]


def split_svg(source: Path, stage: Path, *, depth: int, prefix: str) -> dict:
    try:
        with Progress("Read SVG design"):
            tree = SafeET.parse(source)
            root = tree.getroot()
            _strip_active_svg_content(root)
    except Exception as exc:
        raise MediaCraftError(f"Cannot safely read SVG: {exc}") from exc
    if _svg_tag(root) != "svg":
        raise MediaCraftError("Input XML is not an SVG document.")
    if depth < 1 or depth > 8:
        raise MediaCraftError("SVG --depth must be between 1 and 8.")
    paths = _paths_at_depth(root, depth)
    if not paths:
        raise MediaCraftError(f"No drawable elements at SVG depth {depth}. Try --depth 1.")
    if len(paths) > 500:
        raise MediaCraftError("SVG contains more than 500 components at this depth; pick a smaller --depth.")
    ET.register_namespace("", SVG_NS)
    entries = []
    with Progress("Export SVG components", total=len(paths)) as progress:
        for i, path in enumerate(paths, 1):
            original = _follow_path(root, path)
            tag = _svg_tag(original)
            label = safe_label(original.get("id", "") or tag)
            filename = f"{prefix}_part_{i}_{label}.svg"
            export_root = copy.deepcopy(root)
            _prune_to(export_root, path)
            ET.ElementTree(export_root).write(stage / filename, encoding="utf-8", xml_declaration=True)
            entries.append({"file": filename, "id": original.get("id"), "tag": tag,
                            "drawable_path": list(path)})
            progress.update(i)
    return {"type": "svg", "original_dimensions": {"viewBox": root.get("viewBox"),
             "width": root.get("width"), "height": root.get("height")},
             "depth": depth, "components": entries,
             "note": "Vector components retain their SVG canvas and referenced styles/defs."}


def _parse_hex_rgb(color: str) -> np.ndarray:
    value = color.lstrip("#")
    if len(value) != 6 or any(c not in "0123456789abcdefABCDEF" for c in value):
        raise MediaCraftError("--background must be a six-digit hex RGB color such as '#ffffff'.")
    return np.array([int(value[i:i + 2], 16) for i in (0, 2, 4)], dtype=np.int16)


def split_raster(source: Path, stage: Path, *, background: str | None,
                 threshold: int, min_area: int, canvas: bool, max_components: int,
                 prefix: str) -> dict:
    if not 0 <= threshold <= 255:
        raise MediaCraftError("--threshold must be 0..255")
    if min_area < 1 or max_components < 1:
        raise MediaCraftError("--min-area and --max-components must be positive integers.")
    try:
        with Progress("Read image design"):
            with Image.open(source) as image:
                base = ImageOps.exif_transpose(image).convert("RGBA")
    except Exception as exc:
        raise MediaCraftError(f"Unable to open raster design: {exc}") from exc
    rgba = np.array(base)
    height, width = rgba.shape[:2]
    if width * height > 40_000_000:
        raise MediaCraftError("Raster exceeds 40 million pixels. Resize it before splitting.")
    alpha = rgba[:, :, 3]
    rgb = rgba[:, :, :3]
    has_transparent_pixels = bool((alpha < 255).any())
    if background is not None:
        bg = _parse_hex_rgb(background)
        distance = np.max(np.abs(rgb.astype(np.int16) - bg[None, None, :]), axis=2)
        mask = distance > threshold
        if has_transparent_pixels:
            mask &= alpha > 0
        detection = {"method": "chosen_background", "rgb": bg.tolist(), "threshold": threshold}
    elif has_transparent_pixels:
        mask = alpha > threshold
        detection = {"method": "alpha", "threshold": threshold}
    else:
        corners = np.array([rgb[0, 0], rgb[0, -1], rgb[-1, 0], rgb[-1, -1]], dtype=np.int16)
        bg = np.median(corners, axis=0).astype(np.int16)
        if int(np.max(np.abs(corners - bg))) > threshold:
            raise MediaCraftError(
                "The four corners have different colors, so background detection is ambiguous. "
                "Pass --background '#RRGGBB' for flat-color designs, or use 'image remove' "
                "for photographic backgrounds."
            )
        distance = np.max(np.abs(rgb.astype(np.int16) - bg[None, None, :]), axis=2)
        mask = distance > threshold
        detection = {"method": "corner_color", "rgb": bg.tolist(), "threshold": threshold}
    # OpenCV's O(n) connected components works well on disjoint icons/logos.
    with Progress("Find separate image objects"):
        n_labels, labels, stats, _ = cv2.connectedComponentsWithStats(
            np.ascontiguousarray(mask.astype(np.uint8)), connectivity=8)
    components = []
    for label_id in range(1, n_labels):
        x, y, w, h, area = (int(v) for v in stats[label_id])
        if area >= min_area:
            components.append((label_id, x, y, w, h, area))
    components.sort(key=lambda c: (c[2], c[1]))
    if not components:
        raise MediaCraftError("No distinct foreground components found. Lower --min-area/--threshold or set --background.")
    if len(components) > max_components:
        raise MediaCraftError(
            f"Found {len(components)} regions, above --max-components={max_components}. "
            "Raise --min-area to ignore tiny specks; flat images cannot always recover semantic layers."
        )
    entries = []
    with Progress("Export image components", total=len(components)) as progress:
        for i, (label_id, x, y, w, h, area) in enumerate(components, 1):
            if canvas:
                crop = rgba.copy()
                region_mask = labels == label_id
                crop[:, :, 3] = np.where(region_mask, crop[:, :, 3], 0)
            else:
                crop = rgba[y:y + h, x:x + w].copy()
                region_mask = labels[y:y + h, x:x + w] == label_id
                crop[:, :, 3] = np.where(region_mask, crop[:, :, 3], 0)
            filename = f"{prefix}_object_{i}.png"
            Image.fromarray(crop, "RGBA").save(stage / filename)
            entries.append({"file": filename, "bbox_xywh": [x, y, w, h], "pixels": area})
            progress.update(i)
    return {"type": "raster", "image_size": [width, height], "detection": detection,
            "canvas": canvas, "components": entries,
            "note": "Connected regions only. Touching and overlapping shapes are not independent editable design layers."}


def split_design(path: str | Path, out: str | Path | None, *, depth: int = 1,
                 background: str | None = None, threshold: int = 28, min_area: int = 16,
                 canvas: bool = False, max_components: int = 200, force: bool = False) -> Path:
    source = source_file(path)
    target = out or source.parent
    prefix = output_prefix(source)
    with staged_directory(target, force=force, protected=source) as stage:
        if source.suffix.lower() == ".svg":
            if background is not None or canvas:
                raise MediaCraftError("--background and --canvas only apply to raster images.")
            manifest = split_svg(source, stage, depth=depth, prefix=prefix)
        elif source.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".tif"):
            if depth != 1:
                raise MediaCraftError("--depth only applies to SVG files.")
            manifest = split_raster(source, stage, background=background, threshold=threshold,
                                   min_area=min_area, canvas=canvas, max_components=max_components,
                                   prefix=prefix)
        else:
            raise MediaCraftError("Supported design inputs: SVG, PNG, JPG, WEBP, BMP, TIFF.")
        manifest["source"] = str(source)
        dump_json(stage / f"{prefix}_design_manifest.json", manifest)
    return Path(target).expanduser().resolve()
