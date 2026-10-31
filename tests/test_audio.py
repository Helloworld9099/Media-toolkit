import json
from pathlib import Path

import pytest

from mediacraft.audio import split_audio
from mediacraft.common import MediaCraftError


def test_audio_scene_dispatch_and_manifest_without_models(monkeypatch, tmp_path):
    source = tmp_path / "tune.flac"
    source.write_bytes(b"fixture")

    def fake_separate(src, out, *, model, device, ffmpeg):
        assert src in {source, tmp_path / "other.flac"}
        assert model == "bsrnn" and device == "cpu"
        assert ffmpeg
        for name in ("speech.wav", "music.wav", "sfx.wav"):
            (out / name).write_bytes(b"mock model output")
        return ["speech.wav", "music.wav", "sfx.wav"]

    monkeypatch.setattr("mediacraft.audio._separate_scene", fake_separate)
    target = split_audio(source)
    assert target == tmp_path
    assert (target / "tune_sound_effects.wav").exists()
    m = json.loads((target / "tune_audio_manifest.json").read_text())
    assert m["model"] == "bsrnn"
    assert m["outputs"] == ["tune_music.wav", "tune_sound_effects.wav", "tune_speech.wav"]
    with pytest.raises(MediaCraftError, match="already exists"):
        split_audio(source)
    # Two inputs in the same folder cannot accidentally reuse stem filenames.
    other = tmp_path / "other.flac"
    other.write_bytes(b"fixture")
    split_audio(other)
    assert (tmp_path / "other_sound_effects.wav").is_file()
    assert (tmp_path / "tune_sound_effects.wav").read_bytes() == b"mock model output"
    # --force replaces matching files but not unrelated user files.
    notes = tmp_path / "keep-notes.txt"
    notes.write_text("important")
    split_audio(source, force=True)
    assert notes.read_text() == "important"


def test_audio_invalid_models_before_processing(tmp_path):
    source = tmp_path / "music.mp3"
    source.write_bytes(b"fixture")
    with pytest.raises(MediaCraftError, match="Scene mode accepts"):
        split_audio(source, model="htdemucs")
    with pytest.raises(MediaCraftError, match="Music mode accepts"):
        split_audio(source, mode="music", model="tiger")
    with pytest.raises(MediaCraftError, match="two-stems"):
        split_audio(source, two_stems=True)
    assert not list(tmp_path.glob("*_audio_manifest.json"))


def test_audio_explicit_destination_is_not_input_folder(monkeypatch, tmp_path):
    source = tmp_path / "tune.wav"
    source.write_bytes(b"fixture")
    def fake_separate(src, out, *, model, device, ffmpeg):
        for name in ("speech.wav", "music.wav", "sfx.wav"):
            (out / name).write_bytes(b"sample")
        return ["speech.wav", "music.wav", "sfx.wav"]
    monkeypatch.setattr("mediacraft.audio._separate_scene", fake_separate)
    out = tmp_path / "custom"
    split_audio(source, out)
    assert (out / "tune_speech.wav").exists()
    assert not (tmp_path / "tune_speech.wav").exists()
