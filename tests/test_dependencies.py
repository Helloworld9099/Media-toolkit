"""Automatic engine setup only runs in an app-owned virtual environment."""
import pytest
from mediacraft import dependencies
from mediacraft.common import MediaCraftError


def test_engine_absent_and_not_managed_never_calls_pip(monkeypatch):
    monkeypatch.setattr(dependencies, 'find_spec', lambda name: None)
    monkeypatch.setattr(dependencies, 'in_managed_install', lambda: False)
    monkeypatch.setattr(dependencies, '_pip', lambda *a: (_ for _ in ()).throw(AssertionError('pip invoked')))
    with pytest.raises(MediaCraftError, match='installer'):
        dependencies.ensure_engine('background')


def test_engine_is_installed_automatically_when_owned(monkeypatch):
    installed = set()
    monkeypatch.setattr(dependencies, 'find_spec', lambda name: name in installed)
    monkeypatch.setattr(dependencies, 'in_managed_install', lambda: True)
    def fake_pip(*args):
        assert 'rembg[cpu]>=2.0.85,<3' in args
        installed.add('rembg')
    monkeypatch.setattr(dependencies, '_pip', fake_pip)
    dependencies.ensure_engine('background')
    dependencies.ensure_engine('background')
