"""Progress bars must represent real measurements, and not overwrite CLI output."""
from __future__ import annotations

import io
from pathlib import Path
import re
import sys
import time

import pytest

from mediacraft.common import MediaCraftError, run_ffmpeg, run_long_command
from mediacraft.progress import Progress


class FakeTTY(io.StringIO):
    def isatty(self) -> bool:
        return True


def test_measured_bar_has_percentage_and_finishes_at_100():
    stream = FakeTTY()
    with Progress('Export components', total=4, stream=stream, refresh=.01) as bar:
        bar.update(1)
        bar._write_frame()
        bar.update(4)
    output = stream.getvalue()
    assert '25%' in output
    assert '[========================] 100%' in output
    assert '\r' in output
    assert 'Done' not in output or '100%' in output


def test_unknown_duration_uses_activity_bar_without_fake_percentage():
    stream = FakeTTY()
    with Progress('Load AI model', stream=stream, refresh=.01):
        time.sleep(.04)
    output = stream.getvalue()
    assert output.count('\r') >= 2
    assert 'working' in output
    assert 'Done' in output
    assert not re.search(r'\b\d+%', output)


def test_failure_does_not_claim_completion():
    stream = FakeTTY()
    with pytest.raises(RuntimeError):
        with Progress('Export', total=10, stream=stream):
            raise RuntimeError('simulate failed export')
    output = stream.getvalue()
    assert 'Failed' in output
    assert '100%' not in output


def test_redirected_output_has_readable_stage_milestones():
    stream = io.StringIO()
    with Progress('Export', total=4, stream=stream) as bar:
        for index in range(1, 5):
            bar.update(index)
    output = stream.getvalue()
    assert 'Export...' in output
    assert '25%' in output
    assert '50%' in output
    assert '75%' in output
    assert 'done' in output


def _make_ffmpeg_stub(tmp_path: Path, source: str, monkeypatch) -> str:
    """Start a Python fixture even when FFmpeg flags precede command arguments."""
    import subprocess

    executable = tmp_path / 'fake_ffmpeg.py'
    executable.write_text('import sys\n' + source, encoding='utf-8')
    real_popen = subprocess.Popen

    def portable_popen(argv, *args, **kwargs):
        if argv[0] == 'fake-ffmpeg':
            argv = [sys.executable, str(executable), *argv[1:]]
        return real_popen(argv, *args, **kwargs)

    monkeypatch.setattr('mediacraft.common.subprocess.Popen', portable_popen)
    return 'fake-ffmpeg'


def test_ffmpeg_reports_actual_processed_timestamp(tmp_path, capsys, monkeypatch):
    fake = _make_ffmpeg_stub(tmp_path, 'sys.stdout.write("out_time_us=400000\\nout_time_us=800000\\nprogress=end\\n")\n', monkeypatch)
    run_ffmpeg([fake], label='Extract audio', duration=1.0)
    output = capsys.readouterr().err
    assert 'Extract audio' in output
    assert '40%' in output
    assert '80%' in output
    assert 'done' in output


def test_ffmpeg_failure_shows_error_without_success(tmp_path, capsys, monkeypatch):
    fake = _make_ffmpeg_stub(tmp_path, 'sys.stderr.write("Test FFmpeg failure\\n")\nraise SystemExit(5)\n', monkeypatch)
    with pytest.raises(MediaCraftError, match='Test FFmpeg failure'):
        run_ffmpeg([fake], label='Video extraction', duration=3.0)
    assert 'failed' in capsys.readouterr().err.lower()


def test_generic_process_spinner_reports_failure(tmp_path, capsys, monkeypatch):
    fake = _make_ffmpeg_stub(tmp_path, 'sys.stderr.write("Model checkpoint missing\\n")\nraise SystemExit(2)\n', monkeypatch)
    with pytest.raises(MediaCraftError, match='Model checkpoint missing'):
        run_long_command([fake], label='Separate song')
    assert 'failed' in capsys.readouterr().err.lower()
