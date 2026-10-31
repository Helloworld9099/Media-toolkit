"""Command-line interface for MediaCraft."""
from __future__ import annotations

import argparse
from importlib.util import find_spec
import json
from pathlib import Path
import subprocess
import sys

from . import __version__
from .common import MediaCraftError, output_prefix, source_file


COMMANDS = {
    "removebackground": "background",
    "separatesounds": "sounds",
    "separatesong": "song",
    "splitvideo": "video",
    "splitdesign": "design",
}

LEGACY_ALIASES = {
    "remove-background": "removebackground",
    "separate-sounds": "separatesounds",
    "separate-song": "separatesong",
    "split-video": "splitvideo",
    "split-design": "splitdesign",
}


def make_parser(*, include_legacy: bool = False) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mediacraft",
        usage="mediacraft <command> [file] [options]",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Media processing from the command line.",
        epilog=(
            "Examples:\n"
            "  mediacraft removebackground photo.jpg\n"
            "  mediacraft separatesounds recording.mp3\n"
            "  mediacraft separatesong music.mp3\n"
            "  mediacraft splitvideo clip.mp4\n"
            "  mediacraft splitdesign logo.svg\n\n"
            "Generated files are saved next to the source by default.\n"
            "Use --force only when you want to replace existing outputs."
        ),
    )
    parser.add_argument("--version", action="version", version=f"MediaCraft {__version__}")
    subcommands = parser.add_subparsers(dest="tool", title="commands")
    easy = (
        ("removebackground", "Remove an image background"),
        ("separatesounds", "Separate speech, music and sound effects"),
        ("separatesong", "Separate vocals and instruments"),
        ("splitvideo", "Create silent video and separate audio tracks"),
        ("splitdesign", "Split SVG or image objects into parts"),
    )
    for name, help_text in easy:
        command = subcommands.add_parser(name, help=help_text)
        command.add_argument("input", help="Input file path (quote paths containing spaces)")
        command.add_argument("-o", "--output", help="Optional output folder (or PNG path for background removal)")
        command.add_argument("--force", action="store_true", help="Replace MediaCraft outputs with the same names")

    health = subcommands.add_parser("doctor", help="Check installed processing tools")
    health.add_argument("--json", action="store_true")
    health.add_argument("--prepare-video", action="store_true", help=argparse.SUPPRESS)
    subcommands.add_parser("uninstall", help="Remove MediaCraft and its private downloads")
    if not include_legacy:
        return parser

    image = subcommands.add_parser("image", help="Advanced background-removal options")
    image_cmd = image.add_subparsers(dest="action", required=True)
    bg = image_cmd.add_parser("remove", help="Remove a background")
    bg.add_argument("input")
    bg.add_argument("-o", "--output")
    bg.add_argument("--model", choices=("bria-rmbg", "u2netp", "u2net", "isnet-general-use", "birefnet-general", "birefnet-portrait"), default="u2netp")
    bg.add_argument("--force", action="store_true")

    audio = subcommands.add_parser("audio", help="Advanced audio options")
    audio_cmd = audio.add_subparsers(dest="action", required=True)
    stems = audio_cmd.add_parser("split", help="Extract audio stems")
    stems.add_argument("input")
    stems.add_argument("-o", "--output")
    stems.add_argument("--mode", choices=("scene", "music"), default="scene")
    stems.add_argument("--model")
    stems.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    stems.add_argument("--two-stems", action="store_true")
    stems.add_argument("--force", action="store_true")

    video = subcommands.add_parser("video", help="Advanced video options")
    video_cmd = video.add_subparsers(dest="action", required=True)
    tracks = video_cmd.add_parser("split", help="Extract video and audio tracks")
    tracks.add_argument("input")
    tracks.add_argument("-o", "--output")
    tracks.add_argument("--all-audio", action="store_true")
    tracks.add_argument("--audio-format", choices=("wav", "copy"), default="wav")
    tracks.add_argument("--audio-stems", choices=("none", "scene", "music"), default="none")
    tracks.add_argument("--model")
    tracks.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    tracks.add_argument("--force", action="store_true")

    design = subcommands.add_parser("design", help="Advanced design options")
    design_cmd = design.add_subparsers(dest="action", required=True)
    elements = design_cmd.add_parser("split", help="Extract design objects")
    elements.add_argument("input")
    elements.add_argument("-o", "--output")
    elements.add_argument("--depth", type=int, default=1)
    elements.add_argument("--background")
    elements.add_argument("--threshold", type=int, default=28)
    elements.add_argument("--min-area", type=int, default=16)
    elements.add_argument("--max-components", type=int, default=200)
    elements.add_argument("--canvas", action="store_true")
    elements.add_argument("--force", action="store_true")
    return parser


def doctor(*, prepare_video: bool = False) -> dict[str, object]:
    import shutil

    ffmpeg = bool(shutil.which("ffmpeg"))
    ffprobe = bool(shutil.which("ffprobe"))
    if prepare_video:
        from .tools import video_tools
        video_tools()
        ffmpeg = ffprobe = True
    return {
        "python": sys.version.split()[0],
        "version": __version__,
        "required_programs": {
            "ffmpeg": ffmpeg or find_spec("static_ffmpeg") is not None,
            "ffprobe": ffprobe or find_spec("static_ffmpeg") is not None,
        },
        "required_python": {name: find_spec(name) is not None for name in ("PIL", "numpy", "cv2", "defusedxml")},
        "optional_engines": {name: find_spec(name) is not None for name in ("rembg", "demucs", "dbs", "torch", "soundfile")},
    }


def _run_uninstaller() -> int:
    from .dependencies import installation_root

    root = installation_root()
    script = root / ("uninstall.ps1" if sys.platform == "win32" else ("uninstall-macos.sh" if sys.platform == "darwin" else "uninstall.sh"))
    if not script.is_file():
        print("No installed MediaCraft uninstaller found. Use the installer package to uninstall.")
        return 1
    try:
        return subprocess.run((["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)] if sys.platform == "win32" else ["bash", str(script)]), check=False).returncode
    except OSError as exc:
        raise MediaCraftError(f"Cannot open uninstaller: {exc}") from exc


def _operation(
    tool: str, path: str, *, output: str | None = None, force: bool = False,
    model: str | None = None, mode: str | None = None, all_audio: bool = True,
    audio_format: str = "wav", audio_stems: str = "none", device: str = "cpu",
    two_stems: bool = False, depth: int = 1, background: str | None = None,
    threshold: int = 28, min_area: int = 16, max_components: int = 200,
    canvas: bool = False,
) -> Path:
    # Check input before potentially large engine downloads.
    source_file(path)
    if tool == "background":
        from .dependencies import ensure_engine
        ensure_engine("background")
        from .background import remove_background
        return remove_background(path, output, model=model or "u2netp", force=force)
    if tool in ("sounds", "song"):
        from .dependencies import ensure_engine
        actual_mode = mode or ("scene" if tool == "sounds" else "music")
        ensure_engine("scene" if actual_mode == "scene" else "music")
        from .audio import split_audio
        return split_audio(path, output, mode=actual_mode, model=model, device=device,
                           two_stems=two_stems, force=force)
    if tool == "video":
        if audio_stems != "none":
            from .dependencies import ensure_engine
            ensure_engine("scene" if audio_stems == "scene" else "music")
        from .video import split_video
        return split_video(path, output, all_audio=all_audio,
                           audio_format=audio_format, stem_mode=audio_stems,
                           model=model, device=device, force=force)
    if tool == "design":
        from .design import split_design
        return split_design(path, output, depth=depth, background=background,
                            threshold=threshold, min_area=min_area,
                            max_components=max_components, canvas=canvas,
                            force=force)
    raise MediaCraftError(f"Unknown action: {tool}")


def _show_saved(tool: str, path: str, destination: Path) -> None:
    if tool == "background":
        print(f"Saved: {destination}")
        return
    prefix = output_prefix(Path(path).expanduser().resolve())
    kind = {"sounds": "audio", "song": "audio", "video": "video", "design": "design"}[tool]
    manifest = destination / f"{prefix}_{kind}_manifest.json"
    info = json.loads(manifest.read_text(encoding="utf-8"))
    if kind == "video":
        files = [entry["file"] for entry in info["files"]]
    elif kind == "audio":
        files = info["outputs"]
    else:
        files = [entry["file"] for entry in info["components"]]
    manifest.unlink()
    print(f"Created {len(files)} files in {destination}:")
    for file in files:
        print(f"  {file}")


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    parser = make_parser(include_legacy=bool(argv and argv[0] in ("image", "audio", "video", "design")))
    if not argv:
        parser.print_help()
        return 0
    if argv[0] in LEGACY_ALIASES:
        argv = [LEGACY_ALIASES[argv[0]], *argv[1:]]
    from .dependencies import configure_private_cache
    configure_private_cache()
    try:
        args = parser.parse_args(argv)
        if args.tool is None:
            parser.print_help()
            return 0
        if args.tool == "uninstall":
            return _run_uninstaller()
        if args.tool == "doctor":
            result = doctor(prepare_video=args.prepare_video)
            if args.json:
                print(json.dumps(result, indent=2))
            elif not args.prepare_video:
                print(f"MediaCraft {result['version']}")
                for key, label in (
                    ("required_programs", "Video tools"),
                    ("required_python", "Core tools"),
                    ("optional_engines", "AI tools (downloaded when needed)"),
                ):
                    print(label + ":")
                    for name, present in result[key].items():
                        description = "Ready" if present else "On demand" if key == "optional_engines" else "Missing"
                        print(f"  {description}: {name}")
            return 0
        if args.tool in COMMANDS:
            tool = COMMANDS[args.tool]
            destination = _operation(tool, args.input, output=args.output, force=args.force)
        elif args.tool == "image":
            tool = "background"
            destination = _operation(tool, args.input, output=args.output, model=args.model, force=args.force)
        elif args.tool == "audio":
            tool = "sounds" if args.mode == "scene" else "song"
            destination = _operation(tool, args.input, output=args.output, mode=args.mode,
                                     model=args.model, device=args.device, two_stems=args.two_stems,
                                     force=args.force)
        elif args.tool == "video":
            tool = "video"
            destination = _operation(tool, args.input, output=args.output, all_audio=args.all_audio,
                                     audio_format=args.audio_format, audio_stems=args.audio_stems,
                                     model=args.model, device=args.device, force=args.force)
        elif args.tool == "design":
            tool = "design"
            destination = _operation(tool, args.input, output=args.output, depth=args.depth,
                                     background=args.background, threshold=args.threshold,
                                     min_area=args.min_area, max_components=args.max_components,
                                     canvas=args.canvas, force=args.force)
        else:
            parser.print_help()
            return 0
        _show_saved(tool, args.input, destination)
        return 0
    except MediaCraftError as exc:
        print(f"MediaCraft: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\nMediaCraft stopped.", file=sys.stderr)
        return 130
