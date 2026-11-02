"""pipx installations must use their own environment for optional engines."""
import json
from contextlib import nullcontext

from mediacraft import dependencies


def test_detects_mediacraft_pipx_environment(tmp_path, monkeypatch):
    env = tmp_path / "mediacraft-cli"
    env.mkdir()
    (env / "pipx_metadata.json").write_text(json.dumps({
        "environment": "mediacraft-cli",
        "main_package": {"package": "mediacraft-cli"},
    }), encoding="utf-8")
    monkeypatch.setattr(dependencies.sys, "prefix", str(env))
    monkeypatch.setattr(dependencies, "in_managed_install", lambda: False)
    assert dependencies.pipx_environment() == "mediacraft-cli"


def test_refuses_another_packages_pipx_environment(tmp_path, monkeypatch):
    env = tmp_path / "some-other-app"
    env.mkdir()
    (env / "pipx_metadata.json").write_text(json.dumps({
        "environment": "some-other-app",
        "main_package": {"package": "some-other-app"},
    }), encoding="utf-8")
    monkeypatch.setattr(dependencies.sys, "prefix", str(env))
    monkeypatch.setattr(dependencies, "in_managed_install", lambda: False)
    assert dependencies.pipx_environment() is None


def test_pipx_installs_optional_engine_via_inject(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(dependencies, "in_managed_install", lambda: False)
    monkeypatch.setattr(dependencies, "pipx_environment", lambda: "mediacraft-cli")
    monkeypatch.setattr(dependencies.shutil, "which", lambda name: "/usr/bin/pipx" if name == "pipx" else None)
    monkeypatch.setattr(dependencies, "installation_root", lambda: tmp_path)
    monkeypatch.setattr(dependencies, "Progress", lambda *a, **kw: nullcontext())

    class Result:
        returncode = 0

    def fake_run(command, **kwargs):
        calls.append(command)
        return Result()

    monkeypatch.setattr(dependencies.subprocess, "run", fake_run)
    dependencies._pip("rembg[cpu]>=2.0.85,<3")
    assert calls == [["/usr/bin/pipx", "inject", "mediacraft-cli", "rembg[cpu]>=2.0.85,<3"]]


def test_missing_engine_uses_pipx_in_isolated_environment(monkeypatch):
    installed = set()
    commands = []
    monkeypatch.setattr(dependencies, "in_managed_install", lambda: False)
    monkeypatch.setattr(dependencies, "pipx_environment", lambda: "mediacraft-cli")
    monkeypatch.setattr(dependencies, "find_spec", lambda name: object() if name in installed else None)

    def fake_install(*args):
        commands.append(args)
        if any(a.startswith("rembg") for a in args):
            installed.add("rembg")

    monkeypatch.setattr(dependencies, "_pip", fake_install)
    dependencies.ensure_engine("background")
    assert commands == [("rembg[cpu]>=2.0.85,<3",)]


def test_pipx_environment_with_no_metadata_is_not_trusted(tmp_path, monkeypatch):
    monkeypatch.setattr(dependencies.sys, "prefix", str(tmp_path))
    monkeypatch.setattr(dependencies, "in_managed_install", lambda: False)
    assert dependencies.pipx_environment() is None
