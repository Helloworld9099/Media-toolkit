import sys
import types

import numpy as np
from PIL import Image
import pytest

from mediacraft.background import remove_background
from mediacraft.common import MediaCraftError


def test_background_output_and_collision_protection(monkeypatch, tmp_path):
    source = tmp_path / "my photo.jpg"
    Image.fromarray(np.full((8, 10, 3), 200, dtype=np.uint8), "RGB").save(source)
    calls = []

    def fake_rembg(image, *, session):
        assert image.mode == "RGBA"
        calls.append(session)
        image.putalpha(0)
        return image

    monkeypatch.setitem(sys.modules, "rembg", types.SimpleNamespace(new_session=lambda name: name, remove=fake_rembg))
    target = remove_background(source, None, model="u2netp", force=False)
    assert target.name == "my_photo_background_removed.png" and calls == ["u2netp"]
    with Image.open(target) as out:
        assert out.getpixel((1, 1))[3] == 0
    with pytest.raises(MediaCraftError, match="Output exists"):
        remove_background(source, None, model="u2netp", force=False)
    with pytest.raises(MediaCraftError, match="not overwrite"):
        remove_background(source, source, model="u2netp", force=True)
