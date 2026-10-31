import json
import shutil
import subprocess
from pathlib import Path

import pytest

from mediacraft.common import MediaCraftError
from mediacraft.video import split_video, probe_streams


pytestmark = pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="requires FFmpeg")


def make_movie(path: Path, *, multiple_audio: bool = True):
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "color=c=blue:s=128x96:r=10:d=1",
           "-f", "lavfi", "-i", "sine=frequency=440:duration=1"]
    if multiple_audio:
        cmd += ["-f", "lavfi", "-i", "sine=frequency=880:duration=1"]
    cmd += ["-map", "0:v", "-map", "1:a"]
    if multiple_audio:
        cmd += ["-map", "2:a"]
    cmd += ["-c:v", "mpeg4", "-c:a", "aac", "-shortest", str(path)]
    subprocess.run(cmd, check=True)


def test_video_splits_multiple_streams_and_audio_copy(tmp_path):
    original = tmp_path / "clip with spaces.mkv"
    make_movie(original)
    target = split_video(original, all_audio=True)
    assert target == tmp_path
    assert (target / "clip_with_spaces_video_only.mkv").exists()
    assert (target / "clip_with_spaces_audio_track_1.wav").exists()
    assert (target / "clip_with_spaces_audio_track_2.wav").exists()
    assert not any(s["codec_type"] == "audio" for s in probe_streams(target / "clip_with_spaces_video_only.mkv"))
    assert len(json.loads((target / "clip_with_spaces_video_manifest.json").read_text())["files"]) == 3
    target2 = split_video(original, out=tmp_path / "copy", audio_format="copy")
    assert (target2 / "clip_with_spaces_audio_track_1.mka").exists()
    out_audio = [s for s in probe_streams(target2 / "clip_with_spaces_audio_track_1.mka") if s.get("codec_type") == "audio"]
    assert out_audio[0]["codec_name"] == "aac"
    assert not (target2 / "clip_with_spaces_audio_track_2.mka").exists()


def test_video_no_audio(tmp_path):
    original = tmp_path / "mute.mkv"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "color=c=black:s=64x64:r=1:d=1",
                    "-c:v", "mpeg4", str(original)], check=True)
    target = split_video(original)
    assert (target / "mute_video_only.mkv").exists()
    assert not list(target.glob("mute_audio_*"))
    with pytest.raises(MediaCraftError, match="no audio"):
        split_video(original, out=tmp_path / "with_stems", stem_mode="scene")
    assert not (tmp_path / "with_stems").exists()


def test_video_force_keeps_unrelated_files(tmp_path):
    original = tmp_path / "clip.mkv"
    make_movie(original, multiple_audio=False)
    target = split_video(original)
    (target / "notes.txt").write_text("do not delete")
    with pytest.raises(MediaCraftError):
        split_video(original)
    split_video(original, force=True)
    assert (target / "notes.txt").read_text() == "do not delete"


def test_video_stems_appear_flat_with_video_prefix(tmp_path, monkeypatch):
    original = tmp_path / "example.mkv"
    make_movie(original, multiple_audio=False)

    def fake_model(source, stage, *, model, device, ffmpeg):
        for name in ("speech.wav", "music.wav", "sfx.wav"):
            (stage / name).write_bytes(b"fake predicted track")
        return ["speech.wav", "music.wav", "sfx.wav"]

    monkeypatch.setattr("mediacraft.audio._separate_scene", fake_model)
    folder = split_video(original, stem_mode="scene")
    assert folder == tmp_path
    assert sorted(p.name for p in folder.glob("example_*.wav")) == [
        "example_audio_track_1.wav", "example_music.wav", "example_sound_effects.wav", "example_speech.wav"
    ]
    assert not (folder / "_intermediate_stems").exists()
    data = json.loads((folder / "example_video_manifest.json").read_text())
    assert len([entry for entry in data["files"] if entry["kind"] == "stem"]) == 3
