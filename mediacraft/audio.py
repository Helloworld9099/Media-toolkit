"""Optional audio source separation: Demucs music or DBS cinematic speech/music/SFX."""

from __future__ import annotations

from pathlib import Path
import sys

from .common import (MediaCraftError, dump_json, output_prefix, require_program,
                     run_ffmpeg, run_long_command, media_duration, source_file, staged_directory)
from .progress import Progress


SCENE_MODELS = {
    "bsrnn": ("JusperLee/DBS-BSRNN-DnR", 3.0, 1.5),
    "tiger": ("JusperLee/DBS-TIGER-DnR", 6.0, 3.0),
}
MUSIC_MODELS = ("htdemucs", "htdemucs_ft", "htdemucs_6s")


def split_audio(
    path: str | Path,
    out: str | Path | None = None,
    *,
    mode: str = "scene",
    model: str | None = None,
    device: str = "cpu",
    two_stems: bool = False,
    force: bool = False,
) -> Path:
    source = source_file(path)
    if mode not in ("scene", "music"):
        raise MediaCraftError("Mode must be 'scene' or 'music'.")
    if device not in ("cpu", "cuda"):
        raise MediaCraftError("Device must be 'cpu' or 'cuda'.")
    chosen_model = model or ("bsrnn" if mode == "scene" else "htdemucs")
    if mode == "scene" and chosen_model not in SCENE_MODELS:
        raise MediaCraftError("Scene mode accepts --model bsrnn or --model tiger.")
    if mode == "music" and chosen_model not in MUSIC_MODELS:
        raise MediaCraftError(f"Music mode accepts: {', '.join(MUSIC_MODELS)}")
    if two_stems and mode != "music":
        raise MediaCraftError("--two-stems only works with --mode music.")
    output = out or source.parent
    prefix = output_prefix(source)
    ffmpeg = require_program("ffmpeg")
    with staged_directory(output, force=force, protected=source) as work:
        if mode == "scene":
            outputs = _separate_scene(source, work, model=chosen_model, device=device, ffmpeg=ffmpeg)
        else:
            outputs = _separate_music(source, work, model=chosen_model, device=device,
                                      two_stems=two_stems, ffmpeg=ffmpeg)
        renamed = []
        for name in outputs:
            target_name = f"{prefix}_{name.replace('sfx.wav', 'sound_effects.wav').replace('no_vocals.wav', 'instrumental.wav')}"
            (work / name).rename(work / target_name)
            renamed.append(target_name)
        dump_json(work / f"{prefix}_audio_manifest.json", {
            "source": str(source), "mode": mode, "model": chosen_model, "device": device,
            "outputs": sorted(renamed), "note": "AI source separation is approximate."
        })
    return Path(output).expanduser().resolve()


def _separate_music(source: Path, work: Path, *, model: str, device: str,
                    two_stems: bool, ffmpeg: str) -> list[str]:
    try:
        import demucs  # noqa: F401 - dependency probe before creating large temp WAV
    except ImportError as exc:
        raise MediaCraftError("Music splitting requires Demucs. Install: python -m pip install -e '.[music]'") from exc
    prepared = work / "prepared.wav"
    run_ffmpeg([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(source),
                "-map", "0:a:0", "-vn", "-c:a", "pcm_s16le", "-ar", "44100", "-ac", "2",
                str(prepared)], label="Prepare music audio", duration=media_duration(source))
    predictions = work / "predictions"
    cmd = [sys.executable, "-m", "demucs", "-n", model, "-d", device,
           "-o", str(predictions)]
    if two_stems:
        cmd += ["--two-stems", "vocals"]
    cmd += [str(prepared)]
    run_long_command(cmd, label=f"Separate song ({model}, {device})")
    output_folder = predictions / model / prepared.stem
    stem_files = sorted(output_folder.glob("*.wav"))
    expected = {"vocals", "no_vocals"} if two_stems else ({"vocals", "drums", "bass", "other"}
                if model != "htdemucs_6s" else {"vocals", "drums", "bass", "other", "guitar", "piano"})
    if not expected.issubset({p.stem for p in stem_files}):
        raise MediaCraftError(f"Demucs output is incomplete in {output_folder}. Found: {[p.name for p in stem_files]}")
    for p in stem_files:
        p.replace(work / p.name)
    # Remove intermediate files after exporting the stems.
    import shutil
    prepared.unlink(missing_ok=True)
    shutil.rmtree(predictions, ignore_errors=True)
    return [p.name for p in stem_files]


def _separate_scene(source: Path, work: Path, *, model: str, device: str, ffmpeg: str) -> list[str]:
    try:
        import numpy as np
        import soundfile as sf
        import torch
        from dbs.engine import separate
        from dbs.models import DBSBSRNN, DBSTIGER
    except ImportError as exc:
        raise MediaCraftError(
            "Scene splitting needs DBS. See README 'Install speech/music/SFX mode'; "
            "install the optional [scene] requirements and the official DBS GitHub package."
        ) from exc
    if device == "cuda" and not torch.cuda.is_available():
        raise MediaCraftError("CUDA requested, but PyTorch does not detect a usable CUDA GPU. Use --device cpu.")
    prepared = work / "prepared.wav"
    # The released DBS cinematic checkpoints expect mono PCM at 44100 Hz.
    run_ffmpeg([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(source),
                "-map", "0:a:0", "-vn", "-c:a", "pcm_f32le", "-ar", "44100", "-ac", "1",
                str(prepared)], label="Prepare scene audio", duration=media_duration(source))
    hub, chunk, hop = SCENE_MODELS[model]
    try:
        separator_cls = DBSBSRNN if model == "bsrnn" else DBSTIGER
        with Progress(f"Load DBS-{model.upper()} model (first use may download)"):
            separator = separator_cls.from_pretrained(hub).eval().to(device)
        with sf.SoundFile(prepared) as decoded:
            if decoded.samplerate != 44100 or decoded.channels != 1:
                raise MediaCraftError("Audio preparation failed: expected 44.1 kHz mono WAV.")
            # Bounded memory: call DBS on 60s chunks rather than load entire movie.
            # A 3s context pad reduces edge effects; it does not crossfade boundaries.
            block = 60 * 44100
            overlap = 3 * 44100
            count = int(decoded.frames)
            if count == 0:
                raise MediaCraftError("Input audio is empty.")
            writers = {stem: sf.SoundFile(work / f"{stem}.wav", mode="w", samplerate=44100,
                                          channels=1, subtype="PCM_24")
                       for stem in ("speech", "music", "sfx")}
            try:
                # Each block includes leading and trailing context. Keep only its center.
                # This avoids cumulative overlap or gaps even at unusual input durations.
                with Progress("Separate speech, music and SFX", total=count) as progress:
                    for start in range(0, count, block):
                        end = min(count, start + block)
                        context_start = max(0, start - overlap)
                        context_end = min(count, end + overlap)
                        decoded.seek(context_start)
                        samples = decoded.read(context_end - context_start, dtype="float32", always_2d=True)[:, 0]
                        mixture = torch.from_numpy(samples).view(1, 1, -1).to(device)
                        with torch.inference_mode():
                            result = separate(separator, mixture, {"mode": "chunked", "chunk_seconds": chunk,
                                                                   "hop_seconds": hop}, sample_rate=44100)[0]
                        offset = start - context_start
                        n = end - start
                        stems = {"music": result[0], "sfx": result[1], "speech": result[2]}
                        for stem, values in stems.items():
                            values = values.detach().cpu().numpy()
                            mono = np.asarray(values).reshape(-1)
                            if len(mono) < offset + n:
                                raise MediaCraftError(f"DBS returned short {stem} data.")
                            writers[stem].write(mono[offset:offset + n])
                        progress.update(end)
            finally:
                for writer in writers.values():
                    writer.close()
    except MediaCraftError:
        raise
    except Exception as exc:
        raise MediaCraftError(f"DBS scene separation failed: {exc}") from exc
    finally:
        prepared.unlink(missing_ok=True)
    return ["speech.wav", "music.wav", "sfx.wav"]
