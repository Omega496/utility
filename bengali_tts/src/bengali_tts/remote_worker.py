#!/usr/bin/env python3
"""
Remote Worker Script for Bengali TTS (Indic-Speak) on Google Colab VM.
Executes on the remote Colab GPU runtime:
1. Verifies/installs required dependencies (transformers>=5, snac, soundfile, accelerate).
2. Downloads and caches bodhan-ai/indic-speak model weights via Hugging Face.
3. Loads TTS into GPU VRAM (persisting across kernel executions).
4. Synthesizes Bengali speech per chunk, joins with natural acoustic pauses,
   and encodes to target format (WAV, Opus, or MP3).
5. Returns structured JSON metrics.
"""

import json
import os
import sys
import time
import subprocess
import traceback
from pathlib import Path

# Paths on the Colab VM
WORKDIR = "/content/bengali_tts"
JOB_FILE = os.path.join(WORKDIR, "job.json")
RESULT_FILE = os.path.join(WORKDIR, "result.json")
MODEL_DIR = os.path.join(WORKDIR, "indic_speak_model")

os.makedirs(WORKDIR, exist_ok=True)


def ensure_dependencies():
    """Ensure transformers, snac, soundfile, and accelerate are installed on Colab."""
    needed = []
    try:
        import transformers
        major_ver = int(transformers.__version__.split(".")[0])
        if major_ver < 5:
            needed.append("transformers>=5")
    except Exception:
        needed.append("transformers>=5")

    try:
        import snac
    except Exception:
        needed.append("snac")

    try:
        import soundfile
    except Exception:
        needed.append("soundfile")

    try:
        import accelerate
    except Exception:
        needed.append("accelerate")

    if needed:
        print(f"[Remote Worker] Installing missing packages: {needed}...", flush=True)
        # Use uv pip if available, otherwise regular pip
        has_uv = subprocess.run(["which", "uv"], capture_output=True).returncode == 0
        if has_uv:
            cmd = ["uv", "pip", "install", "--system"] + needed
        else:
            cmd = [sys.executable, "-m", "pip", "install", "-q"] + needed
        subprocess.check_call(cmd)
        print("[Remote Worker] Dependencies successfully installed.", flush=True)


def load_model(model_id: str, hf_token: str = None):
    """Downloads model snapshot if needed and loads the TTS instance."""
    global _CACHED_TTS

    # Check if already loaded in current kernel
    if "_CACHED_TTS" in globals() and _CACHED_TTS is not None:
        print("[Remote Worker] Reusing cached TTS model in GPU memory.", flush=True)
        return _CACHED_TTS

    from huggingface_hub import snapshot_download

    # Check if model files already exist locally on VM
    weight_file = os.path.join(MODEL_DIR, "model.safetensors")
    inference_file = os.path.join(MODEL_DIR, "inference.py")

    if not (os.path.exists(weight_file) and os.path.exists(inference_file)):
        print(f"[Remote Worker] Downloading '{model_id}' snapshot...", flush=True)
        try:
            snapshot_download(
                repo_id=model_id,
                local_dir=MODEL_DIR,
                token=hf_token or None,
            )
            print("[Remote Worker] Model snapshot downloaded successfully.", flush=True)
        except Exception as e:
            err_str = str(e)
            if "403" in err_str or "restricted" in err_str.lower() or "gated" in err_str.lower():
                msg = (
                    "HUGGINGFACE_ACCESS_REQUIRED: Access to 'bodhan-ai/indic-speak' is restricted.\n"
                    "Please visit: https://huggingface.co/bodhan-ai/indic-speak\n"
                    "Log in with your Hugging Face account and accept the license terms (it is auto-approved instantly).\n"
                    "Then re-run this command."
                )
                raise PermissionError(msg) from e
            raise

    # Add model directory to sys.path so vocos and inference can be imported
    if MODEL_DIR not in sys.path:
        sys.path.insert(0, MODEL_DIR)

    from inference import TTS

    print("[Remote Worker] Loading Indic-Speak model into GPU memory...", flush=True)
    tts_instance = TTS(MODEL_DIR)
    _CACHED_TTS = tts_instance
    print("[Remote Worker] Indic-Speak loaded and ready.", flush=True)
    return _CACHED_TTS


def synthesize_job():
    """Main worker entry point."""
    start_time = time.time()

    if not os.path.exists(JOB_FILE):
        raise FileNotFoundError(f"Job file not found at {JOB_FILE}")

    with open(JOB_FILE, "r", encoding="utf-8") as f:
        job = json.load(f)

    ensure_dependencies()

    import numpy as np
    import soundfile as sf
    import torch

    model_id = job.get("model_id", "bodhan-ai/indic-speak")
    hf_token = job.get("hf_token", None)
    chunks = job.get("chunks", [])
    speaker = job.get("speaker", "Ishita")
    style = job.get("style", "NEUTRAL")
    temperature = float(job.get("temperature", 0.6))
    top_p = float(job.get("top_p", 0.9))
    top_k = int(job.get("top_k", 50))
    max_new_tokens = int(job.get("max_new_tokens", 2520))
    pause_duration = float(job.get("pause_duration", 0.25))
    output_format = job.get("output_format", "wav").lower()
    remote_out_path = job.get("remote_out_path", os.path.join(WORKDIR, f"output.{output_format}"))

    if not chunks:
        raise ValueError("No text chunks provided in job configuration.")

    tts = load_model(model_id=model_id, hf_token=hf_token)

    sample_rate = 24000
    pause_samples = int(sample_rate * pause_duration)
    silence = np.zeros(pause_samples, dtype=np.float32)

    generated_segments = []
    print(f"[Remote Worker] Synthesizing {len(chunks)} chunk(s) with speaker '{speaker}', style '{style}'...", flush=True)

    for idx, chunk in enumerate(chunks):
        chunk_text = chunk.strip()
        if not chunk_text:
            continue

        print(f"  [{idx + 1}/{len(chunks)}] Synthesizing: {chunk_text[:50]}...", flush=True)
        wav = tts(
            text=chunk_text,
            speaker=speaker,
            style=style,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            max_new_tokens=max_new_tokens,
        )

        # Convert to numpy array
        if hasattr(wav, "cpu"):
            wav_np = wav.cpu().numpy()
        elif hasattr(wav, "numpy"):
            wav_np = wav.numpy()
        else:
            wav_np = np.array(wav, dtype=np.float32)

        wav_np = np.squeeze(wav_np)
        generated_segments.append(wav_np)

    if not generated_segments:
        raise ValueError("Synthesis yielded no audio output.")

    # Interleave with silence
    combined_audio = []
    for i, seg in enumerate(generated_segments):
        combined_audio.append(seg)
        if i < len(generated_segments) - 1 and pause_samples > 0:
            combined_audio.append(silence)

    full_audio = np.concatenate(combined_audio, axis=0)

    # Normalize audio levels
    max_val = np.max(np.abs(full_audio))
    if max_val > 0.99:
        full_audio = full_audio / max_val * 0.95

    # Intermediate WAV file
    temp_wav = os.path.join(WORKDIR, "temp_render.wav")
    sf.write(temp_wav, full_audio, samplerate=sample_rate)

    # Convert to desired output format
    if output_format == "wav":
        if os.path.exists(remote_out_path):
            os.remove(remote_out_path)
        os.rename(temp_wav, remote_out_path)
    elif output_format == "opus":
        cmd = [
            "ffmpeg", "-y", "-i", temp_wav,
            "-c:a", "libopus", "-b:a", "32k", "-vbr", "on",
            remote_out_path
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        if os.path.exists(temp_wav):
            os.remove(temp_wav)
    elif output_format == "mp3":
        cmd = [
            "ffmpeg", "-y", "-i", temp_wav,
            "-codec:a", "libmp3lame", "-b:a", "64k",
            remote_out_path
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        if os.path.exists(temp_wav):
            os.remove(temp_wav)
    else:
        # Default fallback: keep as WAV
        if os.path.exists(remote_out_path):
            os.remove(remote_out_path)
        os.rename(temp_wav, remote_out_path)

    audio_duration = float(len(full_audio) / sample_rate)
    elapsed_time = float(time.time() - start_time)

    result_data = {
        "success": True,
        "remote_output_path": remote_out_path,
        "format": output_format,
        "duration_seconds": round(audio_duration, 2),
        "elapsed_seconds": round(elapsed_time, 2),
        "chunks_processed": len(chunks),
        "speaker": speaker,
        "style": style,
        "sample_rate": sample_rate,
    }

    with open(RESULT_FILE, "w", encoding="utf-8") as f:
        json.dump(result_data, f, indent=2)

    print("__BENGALI_TTS_RESULT__:" + json.dumps(result_data), flush=True)


if __name__ == "__main__":
    try:
        synthesize_job()
    except Exception as exc:
        err_msg = str(exc)
        tb = traceback.format_exc()
        result_err = {
            "success": False,
            "error": err_msg,
            "traceback": tb,
        }
        with open(RESULT_FILE, "w", encoding="utf-8") as f:
            json.dump(result_err, f, indent=2)
        print("__BENGALI_TTS_RESULT__:" + json.dumps(result_err), flush=True)
        sys.exit(1)
