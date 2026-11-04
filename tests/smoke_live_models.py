"""Check first-use model installation and real CPU inference."""
import argparse
import hashlib
import math
from pathlib import Path
import struct
import subprocess
import tempfile
import wave

from PIL import Image, ImageDraw


def run(python: Path, *args: object, timeout: int = 1200) -> None:
    command = [str(python), "-m", "mediacraft", *(str(arg) for arg in args)]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"Timed out: {command}") from exc
    if result.returncode:
        raise RuntimeError(f"Command failed ({result.returncode}): {command}\n{result.stdout[-5000:]}\n{result.stderr[-5000:]}")
    print(f"Passed: {args[0]}", flush=True)


def audio(path: Path, seconds: int = 4) -> None:
    rate = 44100
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(rate)
        output.writeframes(b"".join(struct.pack("<h", int(9000 * math.sin(2 * math.pi * 440 * i / rate)))
                                   for i in range(rate * seconds)))


def validate_audio(paths: list[Path]) -> None:
    for path in paths:
        if not path.is_file() or path.stat().st_size < 1024:
            raise RuntimeError(f"No audio output: {path}")
        with wave.open(str(path), "rb") as check:
            if check.getnframes() < 1000 or check.getframerate() != 44100:
                raise RuntimeError(f"Invalid audio output: {path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--engine", choices=("background", "music", "scene", "all"), default="all")
    args = parser.parse_args()
    python = args.python.resolve()
    if not python.is_file():
        raise RuntimeError(f"Managed Python not found: {python}")
    modes = ("background", "music", "scene") if args.engine == "all" else (args.engine,)
    with tempfile.TemporaryDirectory(prefix="mediacraft-model-proof-") as name:
        root = Path(name)
        photo = root / "photo.png"
        image = Image.new("RGB", (384, 256), "#eeeeee")
        drawer = ImageDraw.Draw(image)
        drawer.ellipse((110, 25, 275, 230), fill="#1543a9")
        drawer.rectangle((170, 65, 220, 120), fill="#e6ba3a")
        image.save(photo)
        sound = root / "tone.wav"
        audio(sound)
        before = {path: hashlib.sha256(path.read_bytes()).digest() for path in (photo, sound)}
        failed = []
        for mode in modes:
            try:
                if mode == "background":
                    run(python, "removebackground", photo)
                    result = root / "photo_background_removed.png"
                    with Image.open(result) as output:
                        if output.format != "PNG" or output.mode != "RGBA" or output.size != (384, 256):
                            raise RuntimeError("Background removal did not produce an RGBA PNG")
                        print(f"Background alpha extrema: {output.getchannel('A').getextrema()}")
                elif mode == "music":
                    run(python, "separatesong", sound, timeout=1200)
                    validate_audio([root / f"tone_{stem}.wav" for stem in ("vocals", "drums", "bass", "other")])
                else:
                    run(python, "separatesounds", sound, timeout=1200)
                    validate_audio([root / f"tone_{stem}.wav" for stem in ("speech", "music", "sound_effects")])
                if any(hashlib.sha256(p.read_bytes()).digest() != expected for p, expected in before.items()):
                    raise RuntimeError("An original file was overwritten")
            except Exception as exc:
                failed.append(mode)
                print(f"FAILED {mode}: {exc}", flush=True)
        print(f"Models requested: {', '.join(modes)}; failed: {', '.join(failed) or 'none'}")
        if failed:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
