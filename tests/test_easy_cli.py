"""User-facing direct commands and clean output behavior."""
import json
from pathlib import Path

from mediacraft import cli


def test_no_arg_shows_commands_without_menu(capsys):
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    for name in ("removebackground", "separatesounds", "separatesong", "splitvideo", "splitdesign"):
        assert name in out
    assert "Choose a number" not in out


def test_easy_design_command_outputs_files_not_json(tmp_path, capsys):
    import shutil
    sample = Path(__file__).parent.parent / "examples/test_media/sample_layers.svg"
    target = tmp_path / "Brand Design.svg"
    shutil.copy2(sample, target)
    assert cli.main(["splitdesign", str(target)]) == 0
    assert len(list(tmp_path.glob("Brand_Design_part_*.svg"))) == 4
    assert not list(tmp_path.glob("*_manifest.json"))
    stdout = capsys.readouterr().out
    assert "Created 4 files" in stdout
    assert "Brand_Design_part_1_sun.svg" in stdout


def test_easy_video_creates_clear_names_and_no_json(tmp_path):
    import shutil
    import subprocess
    import pytest

    if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
        pytest.skip("FFmpeg is required for video integration tests")
    source = tmp_path / "family trip.mkv"
    subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "color=c=blue:s=128x96:r=10:d=1",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
        "-f", "lavfi", "-i", "sine=frequency=880:duration=1",
        "-map", "0:v", "-map", "1:a", "-map", "2:a",
        "-c:v", "mpeg4", "-c:a", "aac", "-shortest", str(source),
    ], check=True)
    assert cli.main(["splitvideo", str(source)]) == 0
    assert (tmp_path / "family_trip_video_only.mkv").exists()
    assert (tmp_path / "family_trip_audio_track_1.wav").exists()
    assert (tmp_path / "family_trip_audio_track_2.wav").exists()
    assert not list(tmp_path.glob("*_manifest.json"))


def test_no_ai_download_for_missing_input(tmp_path, monkeypatch, capsys):
    from mediacraft import dependencies
    monkeypatch.setattr(dependencies, "ensure_engine", lambda name: (_ for _ in ()).throw(AssertionError("should not download")))
    assert cli.main(["removebackground", str(tmp_path / "missing.jpg")]) == 2
    assert "Input is not a readable file" in capsys.readouterr().err


def test_cli_auto_installs_ai_before_processing(monkeypatch, tmp_path):
    from mediacraft import dependencies
    from mediacraft import audio
    calls = []
    source = tmp_path / "recording.wav"
    source.write_bytes(b"fixture")
    monkeypatch.setattr(dependencies, "ensure_engine", lambda name: calls.append(name))

    def fake_split(path, output, **kwargs):
        assert kwargs["mode"] == "scene"
        (tmp_path / "recording_speech.wav").write_bytes(b"mock")
        (tmp_path / "recording_audio_manifest.json").write_text(json.dumps({
            "outputs": ["recording_speech.wav"]
        }))
        return tmp_path

    monkeypatch.setattr(audio, "split_audio", fake_split)
    assert cli.main(["separatesounds", str(source)]) == 0
    assert calls == ["scene"]
    assert not (tmp_path / "recording_audio_manifest.json").exists()


def test_old_hyphenated_commands_are_supported(tmp_path, monkeypatch):
    from mediacraft import cli
    source = tmp_path / "test.svg"
    source.write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
    calls = []
    def fake_op(tool, path, **kwargs):
        calls.append((tool, path))
        return tmp_path
    monkeypatch.setattr(cli, "_operation", fake_op)
    monkeypatch.setattr(cli, "_show_saved", lambda *args: None)
    for old, tool in (("remove-background", "background"),
                      ("separate-sounds", "sounds"),
                      ("separate-song", "song"),
                      ("split-video", "video"),
                      ("split-design", "design")):
        assert cli.main([old, str(source)]) == 0
        assert calls[-1] == (tool, str(source))
