"""DBS adapter contract test with a fake model; FFmpeg and real WAV I/O are executed."""

import subprocess
import sys
import types

import numpy as np
import pytest

from mediacraft.audio import split_audio


def test_scene_integration_with_mock_checkpoint(tmp_path, monkeypatch):
    torch = pytest.importorskip('torch')
    sf = pytest.importorskip('soundfile')
    src = tmp_path / 'dialogue.wav'
    subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
                    '-f', 'lavfi', '-i', 'sine=frequency=880:duration=1.3',
                    str(src)], check=True)
    # Check the documented DBS inference contract rather than claiming a model was tested.
    class StubModel:
        @classmethod
        def from_pretrained(cls, model):
            assert model == 'JusperLee/DBS-BSRNN-DnR'
            return cls()
        def eval(self):
            return self
        def to(self, device):
            assert device == 'cpu'
            return self

    def fake_separate(model, mixture, config, *, sample_rate):
        assert isinstance(model, StubModel)
        assert mixture.shape[0] == 1 and mixture.shape[1] == 1
        assert config == {'mode': 'chunked', 'chunk_seconds': 3.0, 'hop_seconds': 1.5}
        assert sample_rate == 44100
        wave = mixture[0, 0]
        return [torch.stack([wave * 0.5, wave * 0.3, wave * 0.2], dim=0)]

    fake_pkg = types.ModuleType('dbs')
    fake_pkg.__path__ = []
    fake_engine = types.ModuleType('dbs.engine')
    fake_engine.separate = fake_separate
    fake_models = types.ModuleType('dbs.models')
    fake_models.DBSBSRNN = StubModel
    fake_models.DBSTIGER = StubModel
    monkeypatch.setitem(sys.modules, 'dbs', fake_pkg)
    monkeypatch.setitem(sys.modules, 'dbs.engine', fake_engine)
    monkeypatch.setitem(sys.modules, 'dbs.models', fake_models)
    out = split_audio(src, mode='scene')
    for stem in ('music', 'sound_effects', 'speech'):
        samples, samplerate = sf.read(out / f'dialogue_{stem}.wav', dtype='float32')
        assert samplerate == 44100
        assert 57000 <= len(samples) <= 58000
        assert np.all(np.isfinite(samples))
