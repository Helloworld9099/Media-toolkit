"""Terminal progress reporting for long-running operations."""
from __future__ import annotations

import os
import sys
import threading
import time
from typing import TextIO


FRAMES = "|/-\\"


class Progress:
    """Thread-safe progress display usable around blocking libraries/subprocesses."""

    def __init__(self, label: str, *, total: float | None = None,
                 stream: TextIO | None = None, refresh: float = 0.15):
        if total is not None and total <= 0:
            raise ValueError("total must be positive")
        self.label = label
        self.total = total
        self.stream = stream or sys.stderr
        self.refresh = refresh
        self.current = 0.0
        self.detail = ""
        self._lock = threading.Lock()
        self._started = 0.0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._frame = 0
        self._previous_length = 0
        self._last_bucket = -1
        try:
            self._tty = bool(self.stream.isatty()) and os.environ.get("MEDIACRAFT_NO_PROGRESS") != "1"
        except (AttributeError, OSError):
            self._tty = False

    def __enter__(self) -> Progress:
        self._started = time.monotonic()
        self._stop.clear()
        if self._tty:
            self._write_frame()
            self._thread = threading.Thread(target=self._ticker, name="mediacraft-progress", daemon=True)
            self._thread.start()
        else:
            print(f"MediaCraft: {self.label}...", file=self.stream, flush=True)
        return self

    def __exit__(self, kind, value, tb) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
        with self._lock:
            elapsed = time.monotonic() - self._started
            status = "Failed" if kind is not None else "Done"
            if self._tty:
                if kind is None and self.total is not None:
                    self.current = self.total
                final = self._render(elapsed, finished=True, status=status)
                self._emit(final, newline=True)
            else:
                print(f"MediaCraft: {self.label}: {status.lower()} ({self._time(elapsed)})",
                      file=self.stream, flush=True)
        return None

    @staticmethod
    def _time(seconds: float) -> str:
        secs = max(0, int(seconds))
        return f"{secs // 60:02d}:{secs % 60:02d}"

    def update(self, current: float, *, detail: str | None = None) -> None:
        with self._lock:
            self.current = max(0.0, min(current, self.total)) if self.total is not None else max(0.0, current)
            if detail is not None:
                self.detail = detail
            if not self._tty and self.total:
                bucket = min(4, int(4 * self.current / self.total))
                if bucket > self._last_bucket and bucket > 0 and bucket < 4:
                    self._last_bucket = bucket
                    print(f"MediaCraft: {self.label}: {self.current / self.total:.0%}",
                          file=self.stream, flush=True)

    def advance(self, amount: float = 1, *, detail: str | None = None) -> None:
        self.update(self.current + amount, detail=detail)

    def set_detail(self, detail: str) -> None:
        with self._lock:
            self.detail = detail

    def _render(self, elapsed: float, *, finished: bool = False, status: str = "") -> str:
        width = 24
        if self.total is None:
            if finished:
                bar = "=" * width if status == "Done" else "!" + "-" * (width - 1)
            else:
                pos = self._frame % (width - 4)
                bar = "-" * pos + "====" + "-" * (width - pos - 4)
            summary = status if finished else f"{FRAMES[self._frame % len(FRAMES)]} working"
        else:
            percent = min(1.0, max(0.0, self.current / self.total))
            completed = round(width * percent)
            bar = "=" * completed + "-" * (width - completed)
            summary = status if finished and status == "Failed" else f"{percent:.0%}"
        detail = f" - {self.detail}" if self.detail and not finished else ""
        return f"{self.label}: [{bar}] {summary} | {self._time(elapsed)}{detail}"

    def _emit(self, message: str, *, newline: bool = False) -> None:
        # Only TTY updates are overwritten; redirected logs contain separate messages.
        padding = " " * max(0, self._previous_length - len(message))
        self.stream.write("\r" + message + padding + ("\n" if newline else ""))
        self.stream.flush()
        self._previous_length = 0 if newline else len(message)

    def _write_frame(self) -> None:
        with self._lock:
            self._emit(self._render(time.monotonic() - self._started))
            self._frame += 1

    def _ticker(self) -> None:
        while not self._stop.wait(self.refresh):
            self._write_frame()
