"""Shared file and subprocess safety boundaries for media processors."""

from __future__ import annotations

import contextlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from collections.abc import Iterator


class MediaCraftError(Exception):
    """User-actionable failure, shown without a Python traceback."""


def source_file(path: str | Path) -> Path:
    result = Path(path).expanduser().resolve()
    if not result.is_file():
        raise MediaCraftError(f"Input is not a readable file: {result}")
    return result


def output_path(path: str | Path, source: Path, *, force: bool) -> Path:
    result = Path(path).expanduser().resolve()
    if result == source:
        raise MediaCraftError("Output must not overwrite the input file.")
    if result.exists() and not force:
        raise MediaCraftError(f"Output exists: {result} (pass --force to replace it)")
    if result.exists() and result.is_dir():
        raise MediaCraftError(f"Expected an output file, but got a directory: {result}")
    result.parent.mkdir(parents=True, exist_ok=True)
    return result


@contextlib.contextmanager
def staged_directory(path: str | Path, *, force: bool, protected: Path | None = None) -> Iterator[Path]:
    """Stage generated files, then publish into an output folder.

    Existing folders are allowed by default; *individual files* cannot be
    overwritten unless --force. Every staged file is preflighted before any
    publication, so normal validation and model errors leave outputs untouched.
    Note: filesystem errors during multi-file publication aren't atomic.
    """
    target = Path(path).expanduser().resolve()
    if target.exists() and not target.is_dir():
        raise MediaCraftError(f"Output directory path is a file: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    # If the output folder already exists, stage *inside* it. Users may have
    # write permission to a media folder but not its parent (e.g. mounted disk).
    stage_parent = target if target.is_dir() else target.parent
    stage = Path(tempfile.mkdtemp(prefix=".mediacraft-stage-", dir=stage_parent))
    try:
        yield stage
        pending: list[tuple[Path, Path]] = []
        for directory, _, files in os.walk(stage):
            relative = Path(directory).relative_to(stage)
            for file in files:
                src = Path(directory) / file
                dst = target / relative / file
                if protected is not None and dst.resolve() == protected.resolve():
                    raise MediaCraftError(f"Output would overwrite the input file: {protected}.")
                if dst.is_dir():
                    raise MediaCraftError(f"Output file conflicts with directory: {dst}")
                if (dst.exists() or dst.is_symlink()) and not force:
                    raise MediaCraftError(f"Output file already exists: {dst} (pass --force to replace it)")
                pending.append((src, dst))
        target.mkdir(parents=True, exist_ok=True)
        if pending:
            from .progress import Progress
            with Progress("Saving output files", total=len(pending)) as progress:
                for idx, (src, dst) in enumerate(pending, 1):
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    os.replace(src, dst)
                    progress.update(idx)
    finally:
        shutil.rmtree(stage, ignore_errors=True)


def publish_file(stage: Path, target: Path) -> None:
    os.replace(stage, target)


def require_program(name: str) -> str:
    if name in ("ffmpeg", "ffprobe"):
        from .tools import video_tools
        ffmpeg, ffprobe = video_tools()
        return ffmpeg if name == "ffmpeg" else ffprobe
    binary = shutil.which(name)
    if not binary:
        raise MediaCraftError(f"Required program not found: {name}")
    return binary


def run_command(argv: list[str], *, quiet: bool = False) -> subprocess.CompletedProcess[str]:
    """No shell, no interpolation and detailed FFmpeg/Demucs errors."""
    try:
        return subprocess.run(
            argv,
            check=True,
            text=True,
            capture_output=quiet,
        )
    except FileNotFoundError as exc:
        raise MediaCraftError(f"Program not found: {argv[0]}") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        if len(detail) > 1600:
            detail = detail[-1600:]
        raise MediaCraftError(f"Command failed (exit {exc.returncode}): {argv[0]}\n{detail}") from exc


def media_duration(source: Path) -> float | None:
    """Find input duration in seconds, or None for unbounded/live streams."""
    try:
        ffprobe = require_program("ffprobe")
        result = run_command([ffprobe, "-v", "error", "-show_entries", "format=duration",
                              "-of", "default=noprint_wrappers=1:nokey=1", str(source)], quiet=True)
        duration = float(result.stdout.strip())
        return duration if 0 < duration < float("inf") else None
    except (ValueError, OSError, MediaCraftError):
        return None


def run_ffmpeg(argv: list[str], *, label: str, duration: float | None = None) -> None:
    """Run FFmpeg with its actual processed-media timestamp as progress.

    FFmpeg's `out_time_ms` field is measured in microseconds (despite its name).
    Timestamps are only used when an actual source duration is known.
    stderr goes to a temporary file, so huge FFmpeg failures cannot deadlock pipes.
    """
    from .progress import Progress

    cmd = [argv[0], "-nostdin", "-nostats", "-progress", "pipe:1", *argv[1:]]
    with tempfile.TemporaryFile(mode="w+t", encoding="utf-8") as error_log:
        try:
            with Progress(label, total=duration) as progress:
                with subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                      stderr=error_log, text=True, errors="replace", bufsize=1) as process:
                    assert process.stdout is not None
                    for raw in process.stdout:
                        name, separator, value = raw.strip().partition("=")
                        if not separator or duration is None:
                            continue
                        if name in ("out_time_us", "out_time_ms"):
                            try:
                                progress.update(float(value) / 1_000_000)
                            except ValueError:
                                pass
                        elif name == "out_time":
                            try:
                                hours, minutes, seconds = value.split(":")
                                progress.update(int(hours) * 3600 + int(minutes) * 60 + float(seconds))
                            except ValueError:
                                pass
                    status = process.wait()
                    if status:
                        error_log.seek(0)
                        detail = error_log.read()[-1600:].strip()
                        raise MediaCraftError(f"FFmpeg failed (exit {status}): {detail}")
        except FileNotFoundError as exc:
            raise MediaCraftError(f"FFmpeg executable not found: {argv[0]}") from exc


def run_long_command(argv: list[str], *, label: str) -> None:
    """Display elapsed, moving activity bar for commands without progress APIs."""
    from .progress import Progress

    with tempfile.TemporaryFile(mode="w+t", encoding="utf-8") as log:
        try:
            with Progress(label):
                with subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=log,
                                      stderr=subprocess.STDOUT) as process:
                    status = process.wait()
                    if status:
                        log.seek(0)
                        detail = log.read()[-1600:].strip()
                        raise MediaCraftError(f"Command failed (exit {status}): {argv[0]}\n{detail}")
        except FileNotFoundError as exc:
            raise MediaCraftError(f"Program not found: {argv[0]}") from exc


def dump_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def safe_label(text: str, *, default: str = "element") -> str:
    text = re.sub(r"[^A-Za-z0-9_-]+", "_", text).strip("_.-")[:50]
    return text or default


def output_prefix(source: Path) -> str:
    """Filesystem-safe prefix used for every generated file of a source."""
    return safe_label(source.stem, default="media")
