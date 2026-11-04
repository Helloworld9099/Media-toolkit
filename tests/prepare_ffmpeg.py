"""Prepare platform-native FFmpeg binaries for the test runner."""
import os
from pathlib import Path
import subprocess

from static_ffmpeg.run import get_or_fetch_platform_executables_else_raise


def main() -> None:
    ffmpeg, ffprobe = (Path(value).resolve() for value in get_or_fetch_platform_executables_else_raise())
    for binary in (ffmpeg, ffprobe):
        if not binary.is_file():
            raise RuntimeError(f"Missing native media binary: {binary}")
        subprocess.run([str(binary), "-version"], check=True, capture_output=True, text=True, timeout=30)
    parents = list(dict.fromkeys((str(ffmpeg.parent), str(ffprobe.parent))))
    path_file = os.environ.get("GITHUB_PATH")
    if path_file:
        with open(path_file, "a", encoding="utf-8") as file:
            for directory in parents:
                file.write(directory + "\n")
    else:
        os.environ["PATH"] = os.pathsep.join(parents + [os.environ.get("PATH", "")])
    print(f"FFmpeg: {ffmpeg}")
    print(f"FFprobe: {ffprobe}")


if __name__ == "__main__":
    main()
