import json
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
from PIL import Image
import pytest

from mediacraft.common import MediaCraftError
from mediacraft.design import split_design


def test_svg_separates_groups_and_preserves_defs(tmp_path):
    content = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 200">
        <defs><linearGradient id="glow"><stop stop-color="red"/></linearGradient></defs>
        <g id="upper" transform="translate(8 12)"><circle id="ball" r="10" fill="url(#glow)"/></g>
        <g id="lower"><rect id="square" width="25" height="25"/></g>
    </svg>'''
    source = tmp_path / "sample.svg"
    source.write_text(content)
    result = split_design(source, None)
    assert result == tmp_path
    manifest = json.loads((result / "sample_design_manifest.json").read_text())
    assert len(manifest["components"]) == 2
    svg1 = ET.parse(result / manifest["components"][0]["file"]).getroot()
    assert svg1.get("viewBox") == "0 0 400 200"
    output = (result / manifest["components"][0]["file"]).read_text()
    assert "linearGradient" in output and "translate(8 12)" in output
    assert "ball" in output and "square" not in output
    assert len(list(result.glob("sample_part_*.svg"))) == 2
    with pytest.raises(MediaCraftError, match="already exists"):
        split_design(source, None)
    # User-added files are not removed with --force.
    (result / "user-notes.txt").write_text("keep")
    split_design(source, None, force=True)
    assert (result / "user-notes.txt").read_text() == "keep"


def test_svg_nested_depth(tmp_path):
    source = tmp_path / "wrap.svg"
    source.write_text('''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><g id="all" transform="scale(2)"><rect id="a" x="1" width="5"/><circle id="b" r="2"/></g></svg>''')
    target = split_design(source, None, depth=2)
    assert len(list(target.glob("wrap_part_*.svg"))) == 2
    first = list(sorted(target.glob("wrap_part_*.svg")))[0].read_text()
    assert 'scale(2)' in first
    assert 'id="a"' in first and 'id="b"' not in first


def test_svg_rejects_entity_expansion(tmp_path):
    source = tmp_path / "untrusted.svg"
    source.write_text('''<!DOCTYPE svg [<!ENTITY boom "EXPAND">]><svg xmlns="http://www.w3.org/2000/svg"><text>&boom;</text></svg>''')
    with pytest.raises(MediaCraftError, match="Cannot safely read"):
        split_design(source, None)


def test_raster_opaque_corner_background_and_crop(tmp_path):
    rgb = np.full((100, 140, 3), 255, dtype=np.uint8)
    rgb[12:29, 17:38, :] = [20, 0, 80]
    rgb[50:80, 88:110, :] = [0, 100, 0]
    source = tmp_path / "shapes.png"
    Image.fromarray(rgb, "RGB").save(source)
    target = split_design(source, None)
    data = json.loads((target / "shapes_design_manifest.json").read_text())
    assert data["detection"]["method"] == "corner_color"
    assert len(data["components"]) == 2
    assert data["components"][0]["bbox_xywh"] == [17, 12, 21, 17]
    with Image.open(target / data["components"][0]["file"]) as im:
        assert im.mode == "RGBA" and im.size == (21, 17)
        assert im.getpixel((0, 0))[3] == 255


def test_raster_alpha_and_canvas(tmp_path):
    source = tmp_path / "transparent.png"
    rgba = np.zeros((70, 80, 4), dtype=np.uint8)
    rgba[4:15, 4:20, :] = [200, 50, 10, 255]
    rgba[30:45, 50:63, :] = [10, 50, 200, 255]
    Image.fromarray(rgba, "RGBA").save(source)
    target = split_design(source, None, canvas=True)
    data = json.loads((target / "transparent_design_manifest.json").read_text())
    assert len(data["components"]) == 2
    with Image.open(target / "transparent_object_1.png") as im:
        assert im.size == (80, 70)
        assert im.getpixel((60, 40))[3] == 0


def test_flat_raster_ambiguous_background(tmp_path):
    source = tmp_path / "multibg.png"
    rgb = np.full((30, 30, 3), 255, dtype=np.uint8)
    rgb[0, 0] = [0, 0, 0]
    rgb[-1, -1] = [0, 0, 0]
    Image.fromarray(rgb).save(source)
    with pytest.raises(MediaCraftError, match="four corners"):
        split_design(source, None)
    assert not list(tmp_path.glob("multibg_object_*.png"))


def test_raster_max_components_and_force_no_partial(tmp_path):
    source = tmp_path / "many.png"
    rgb = np.full((80, 80, 3), 255, dtype=np.uint8)
    for y in (10, 30, 50):
        for x in (10, 30, 50):
            rgb[y:y + 5, x:x + 5] = 0
    Image.fromarray(rgb).save(source)
    with pytest.raises(MediaCraftError, match="above --max-components"):
        split_design(source, None, max_components=3, min_area=10)
    assert not list(tmp_path.glob("many_object_*.png"))


def test_svg_strips_obvious_active_content(tmp_path):
    src = tmp_path / "potentially-hostile.svg"
    src.write_text('''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10" onload="alert(1)">
      <script>alert(2)</script>
      <g id="safe" onclick="alert(3)"><rect width="10" height="10"/>
        <foreignObject><body xmlns="http://www.w3.org/1999/xhtml" onload="alert(4)">danger</body></foreignObject>
        <image href="javascript:alert(5)" width="5" height="5" />
      </g>
    </svg>''')
    dest = split_design(src, None)
    file = next(dest.glob("potentially-hostile_part_*.svg"))
    text = file.read_text()
    for unsafe in ("<script", "alert", "foreignObject", "onload", "onclick", "javascript:"):
        assert unsafe not in text
    assert '<ns0:rect' in text or '<rect' in text


def test_force_cannot_overwrite_input_when_output_dir_is_source_folder(tmp_path):
    from mediacraft.common import staged_directory
    src = tmp_path / 'component_001.png'
    src.write_bytes(b'original file')
    with pytest.raises(MediaCraftError, match='overwrite the input'):
        with staged_directory(tmp_path, force=True, protected=src) as stage:
            (stage / 'component_001.png').write_bytes(b'clobber')
            (stage / 'manifest.json').write_text('{"bogus":1}')
    assert src.read_bytes() == b'original file'
    assert not (tmp_path / 'manifest.json').exists()
