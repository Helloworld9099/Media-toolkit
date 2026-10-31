import json
import subprocess
import sys

from mediacraft.cli import doctor, main


def test_help_and_doctor(capsys):
    assert main(["doctor", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["version"] == "0.6.0"
    assert data["required_python"]["PIL"]
    p = subprocess.run([sys.executable, "-m", "mediacraft", "--help"], capture_output=True, text=True)
    assert p.returncode == 0
    assert "design" in p.stdout
    assert "video" in p.stdout


def test_missing_input_error(tmp_path, capsys):
    assert main(["image", "remove", str(tmp_path / "missing.png")]) == 2
    assert "Input is not a readable file" in capsys.readouterr().err
