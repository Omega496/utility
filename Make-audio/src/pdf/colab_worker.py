#!/usr/bin/env python3
"""
Colab Worker Script for Kokoro TTS.

This script executes remotely on the Google Colab VM.
It reads /content/make_audio_job.json, initializes Kokoro TTS
with CUDA GPU acceleration, synthesizes the audio, and writes
/content/make_audio_output.wav.
"""

import json
import logging
import os
import shutil
import subprocess
import sys
import time
import warnings
from contextlib import contextmanager
from pathlib import Path

# Silence external warnings and logs
warnings.filterwarnings("ignore")
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"
os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "0"
os.environ["HF_TOKEN"] = ""  # Prevent querying Colab userdata secrets vault (prevents 10s hang)

logging.getLogger("transformers").setLevel(logging.ERROR)
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
logging.getLogger("phonemizer").setLevel(logging.ERROR)
logging.getLogger("kokoro").setLevel(logging.ERROR)


@contextmanager
def suppress_fd():
    """Context manager to completely suppress low-level C/Rust stdout and stderr."""
    null_fd = os.open(os.devnull, os.O_RDWR)
    save_stdout = os.dup(1)
    save_stderr = os.dup(2)
    try:
        os.dup2(null_fd, 1)
        os.dup2(null_fd, 2)
        yield
    finally:
        os.dup2(save_stdout, 1)
        os.dup2(save_stderr, 2)
        os.close(null_fd)
        os.close(save_stdout)
        os.close(save_stderr)


with suppress_fd():
    try:
        import espeakng_loader
        from phonemizer.backend.espeak.wrapper import EspeakWrapper
        EspeakWrapper.set_library(espeakng_loader.get_library_path())
        EspeakWrapper.set_data_path(espeakng_loader.get_data_path())
    except Exception:
        pass

    import numpy as np
    import soundfile as sf
    import torch
    from kokoro import KPipeline


def run_worker():
    job_file = Path("/content/make_audio_job.json")
    if not job_file.exists():
        print(f"[colab-worker] ERROR: Job file not found at {job_file}", file=sys.stderr)
        sys.exit(1)

    with open(job_file, "r", encoding="utf-8") as f:
        job = json.load(f)

    text = job.get("text", "").strip()
    voice = job.get("voice", "af_heart")
    speed = float(job.get("speed", 1.0))
    pause_between_paragraphs = float(job.get("pause_between_paragraphs", 0.25))
    output_path = Path(job.get("output_path", "/content/make_audio_output.opus"))
    bitrate = str(job.get("bitrate", "24k"))
    verbose = job.get("verbose", False)

    if not text:
        print("[colab-worker] ERROR: Input text is empty.", file=sys.stderr)
        sys.exit(1)

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    total_paras = len(paragraphs)
    word_count = sum(len(p.split()) for p in paragraphs)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    if verbose:
        print(f"[colab-worker] Compute device: {device.upper()}")
        if device == "cuda":
            print(f"[colab-worker] GPU: {torch.cuda.get_device_name(0)}")
        print(f"[colab-worker] Initializing Kokoro pipeline (voice: {voice}, speed: {speed})...")

    with suppress_fd():
        pipeline = KPipeline(lang_code="a", repo_id="hexgrad/Kokoro-82M", device=device)

    sample_rate = 24000
    silence_samples = int(sample_rate * pause_between_paragraphs)
    silence = np.zeros(silence_samples, dtype=np.float32) if silence_samples > 0 else None

    if verbose:
        print(f"[colab-worker] Synthesizing {total_paras} paragraphs ({word_count} words)...")

    all_chunks = []
    start_synth = time.time()

    for p_idx, paragraph in enumerate(paragraphs, 1):
        clean_snippet = paragraph.replace("\n", " ").strip()
        if len(clean_snippet) > 60:
            clean_snippet = clean_snippet[:57] + "..."
        pct = (p_idx / total_paras) * 100
        print(f"[colab-worker] [{pct:5.1f}%] [{p_idx:02d}/{total_paras:02d}] Generating: \"{clean_snippet}\"", flush=True)

        with suppress_fd():
            generator = pipeline(
                paragraph,
                voice=voice,
                speed=speed,
                split_pattern=r"\n+",
            )
            para_chunks = []
            for res in generator:
                if res.audio is not None:
                    if isinstance(res.audio, torch.Tensor):
                        chunk_np = res.audio.detach().cpu().numpy()
                    else:
                        chunk_np = np.array(res.audio, dtype=np.float32)
                    para_chunks.append(chunk_np)

        if para_chunks:
            all_chunks.append(np.concatenate(para_chunks, axis=0))
            if silence is not None and p_idx < total_paras:
                all_chunks.append(silence)

    if not all_chunks:
        final_audio = np.zeros(0, dtype=np.float32)
    else:
        final_audio = np.concatenate(all_chunks, axis=0)

    duration_sec = len(final_audio) / sample_rate
    elapsed = time.time() - start_synth
    rtf = elapsed / duration_sec if duration_sec > 0 else 0

    output_path.parent.mkdir(parents=True, exist_ok=True)
    suffix = output_path.suffix.lower()
    if not suffix:
        output_path = output_path.with_suffix(".opus")
        suffix = ".opus"

    if suffix == ".opus":
        temp_wav = output_path.with_suffix(".temp.wav")
        with suppress_fd():
            sf.write(str(temp_wav), final_audio, sample_rate)
        encoded = False
        if shutil.which("ffmpeg"):
            try:
                subprocess.run(
                    [
                        "ffmpeg", "-y",
                        "-i", str(temp_wav),
                        "-c:a", "libopus",
                        "-b:a", bitrate,
                        "-vbr", "on",
                        "-application", "voip",
                        str(output_path),
                    ],
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                encoded = True
            except (subprocess.SubprocessError, FileNotFoundError):
                encoded = False
            finally:
                temp_wav.unlink(missing_ok=True)

        if not encoded:
            try:
                with suppress_fd():
                    sf.write(str(output_path), final_audio, sample_rate, format="OGG", subtype="OPUS")
            except Exception:
                temp_wav.rename(output_path.with_suffix(".wav"))
                output_path = output_path.with_suffix(".wav")

    elif suffix == ".mp3":
        temp_wav = output_path.with_suffix(".temp.wav")
        with suppress_fd():
            sf.write(str(temp_wav), final_audio, sample_rate)
        if shutil.which("ffmpeg"):
            try:
                subprocess.run(
                    ["ffmpeg", "-y", "-i", str(temp_wav), "-b:a", "192k", str(output_path)],
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                temp_wav.unlink(missing_ok=True)
            except (subprocess.SubprocessError, FileNotFoundError):
                temp_wav.rename(output_path.with_suffix(".wav"))
                output_path = output_path.with_suffix(".wav")
        else:
            temp_wav.rename(output_path.with_suffix(".wav"))
            output_path = output_path.with_suffix(".wav")

    elif suffix == ".wav":
        with suppress_fd():
            sf.write(str(output_path), final_audio, sample_rate)

    else:
        with suppress_fd():
            sf.write(str(output_path), final_audio, sample_rate)

    if verbose:
        print(f"[colab-worker] Synthesis completed in {elapsed:.2f}s (audio duration: {duration_sec:.1f}s, RTF: {rtf:.3f})")
        print(f"[colab-worker] Audio saved to: {output_path}")

    print("[colab-worker] SUCCESS", flush=True)


if __name__ == "__main__":
    run_worker()
