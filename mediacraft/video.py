"""Exact FFmpeg stream mapping for local video and audio extraction."""

from __future__ import annotations

import json
from pathlib import Path
import shutil

from .common import (MediaCraftError, dump_json, output_prefix, require_program,
                     run_command, run_ffmpeg, media_duration, source_file, staged_directory)


def probe_streams(source: Path) -> list[dict]:
    ffprobe = require_program("ffprobe")
    p = run_command([ffprobe, "-v", "error", "-show_streams", "-of", "json", str(source)], quiet=True)
    try:
        data = json.loads(p.stdout)
        return data["streams"]
    except (ValueError, KeyError, TypeError) as exc:
        raise MediaCraftError("ffprobe returned invalid stream information.") from exc


def split_video(
    path: str | Path,
    out: str | Path | None = None,
    *,
    all_audio: bool = False,
    audio_format: str = "wav",
    stem_mode: str = "none",
    model: str | None = None,
    device: str = "cpu",
    force: bool = False,
) -> Path:
    source = source_file(path)
    streams = probe_streams(source)
    videos = [s for s in streams if s.get("codec_type") == "video" and not s.get("disposition", {}).get("attached_pic")]
    audios = [s for s in streams if s.get("codec_type") == "audio"]
    if not videos:
        raise MediaCraftError("The input has no video stream. Use 'audio split' for audio-only inputs.")
    ffmpeg = require_program("ffmpeg")
    duration = media_duration(source)
    target = out or source.parent
    prefix = output_prefix(source)
    with staged_directory(target, force=force, protected=source) as work:
        picture = work / f"{prefix}_video_only.mkv"
        run_ffmpeg([
            ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(source),
            "-map", "0:V:0", "-an", "-sn", "-dn", "-c:v", "copy", str(picture),
        ], label="Extract video", duration=duration)
        records = [{"kind": "video", "file": picture.name, "stream_index": videos[0].get("index"), "codec": videos[0].get("codec_name")}]
        count = len(audios) if all_audio else min(1, len(audios))
        extracted = []
        for ordinal in range(count):
            name = f"{prefix}_audio_track_{ordinal + 1}." + ("wav" if audio_format == "wav" else "mka")
            audio_file = work / name
            args = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(source),
                    "-map", f"0:a:{ordinal}", "-vn", "-sn", "-dn"]
            if audio_format == "wav":
                args += ["-c:a", "pcm_s24le"]
            else:
                args += ["-c:a", "copy", "-f", "matroska"]
            args += [str(audio_file)]
            run_ffmpeg(args, label=f"Extract audio track {ordinal + 1}/{count}", duration=duration)
            extracted.append(audio_file)
            records.append({"kind": "audio", "file": name, "stream_index": audios[ordinal].get("index"),
                            "source_codec": audios[ordinal].get("codec_name"), "format": audio_format})
        if stem_mode != "none":
            if not extracted:
                raise MediaCraftError("This video has no audio stream to separate into stems.")
            from .audio import split_audio
            # Only first audio track is separated; --all-audio exports other tracks unchanged.
            stems_dir = work / "_intermediate_stems"
            split_audio(extracted[0], stems_dir, mode=stem_mode,
                        model=model, device=device, force=False)
            stem_manifest = stems_dir / f"{output_prefix(extracted[0])}_audio_manifest.json"
            stems = json.loads(stem_manifest.read_text(encoding="utf-8"))["outputs"]
            for filename in stems:
                # Convert "clip_audio_track_1_speech.wav" into "clip_speech.wav".
                stem = filename.removeprefix(f"{output_prefix(extracted[0])}_")
                target_name = f"{prefix}_{stem}"
                (stems_dir / filename).replace(work / target_name)
                records.append({"kind": "stem", "file": target_name, "audio_stream": 1,
                                "separation_mode": stem_mode})
            shutil.rmtree(stems_dir)
        dump_json(work / f"{prefix}_video_manifest.json", {"source": str(source), "files": records,
                                                  "audio_stems": stem_mode})
    return Path(target).expanduser().resolve()
