#!/usr/bin/env python3
"""
Remote Worker Script for Bengali TTS (Indic-Speak) on Google Colab VM.
Runs on the remote Colab GPU runtime:
1. Authenticates with Hugging Face Hub using the provided user token.
2. Ensures required dependencies (transformers>=5, snac, soundfile, accelerate).
3. Downloads and caches bodhan-ai/indic-speak model weights.
4. Loads TTS into GPU VRAM in bfloat16.
5. Synthesizes Bengali speech with per-chunk checkpointing (resumable across runs!).
6. Interleaves with natural acoustic pauses and encodes to Opus/WAV/MP3 via FFmpeg.
7. Prints real-time chunk progress and emits structured JSON metrics.
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
CHUNKS_DIR = os.path.join(WORKDIR, "chunks")

os.makedirs(WORKDIR, exist_ok=True)
os.makedirs(CHUNKS_DIR, exist_ok=True)

# Prevent Colab from querying UI userdata secret vault (prevents 15s hang)
os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"
os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "0"


def ensure_dependencies():
    """Ensure transformers>=5, snac, soundfile, and accelerate are installed on Colab."""
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
        has_uv = subprocess.run(["which", "uv"], capture_output=True).returncode == 0
        if has_uv:
            cmd = ["uv", "pip", "install", "--system"] + needed
        else:
            cmd = [sys.executable, "-m", "pip", "install", "-q"] + needed
        subprocess.check_call(cmd)
        print("[Remote Worker] Dependencies installed.", flush=True)


def load_model(model_id: str, hf_token: str = None):
    """Downloads model snapshot if needed and loads the TTS instance."""
    global _CACHED_TTS

    # Check if already loaded in current kernel
    if "_CACHED_TTS" in globals() and _CACHED_TTS is not None:
        print("[Remote Worker] Reusing cached TTS model in GPU memory.", flush=True)
        return _CACHED_TTS

    from huggingface_hub import login, snapshot_download

    if hf_token:
        try:
            login(token=hf_token, add_to_git_credential=False)
            os.environ["HF_TOKEN"] = hf_token
            os.environ["HUGGING_FACE_HUB_TOKEN"] = hf_token
        except Exception:
            pass

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
                    "Log in and accept the license terms (auto-approved instantly).\n"
                    "Then re-run."
                )
                raise PermissionError(msg) from e
            elif "401" in err_str:
                msg = (
                    "HUGGINGFACE_401: Unauthorized request to Hugging Face.\n"
                    "Please ensure your Hugging Face token is provided."
                )
                raise PermissionError(msg) from e
            raise

    # Add model directory to sys.path
    if MODEL_DIR not in sys.path:
        sys.path.insert(0, MODEL_DIR)

    from inference import TTS

    print("[Remote Worker] Loading Indic-Speak model into GPU memory...", flush=True)
    t0 = time.time()
    tts_instance = TTS(MODEL_DIR)
    _CACHED_TTS = tts_instance
    print(f"[Remote Worker] Indic-Speak loaded in {time.time() - t0:.1f}s and ready.", flush=True)
    return _CACHED_TTS


def synthesize_job():
    """Main worker execution function."""
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
    output_format = job.get("output_format", "opus").lower()
    remote_out_path = job.get("remote_out_path", os.path.join(WORKDIR, f"output.{output_format}"))

    if not chunks:
        raise ValueError("No text chunks provided in job configuration.")

    tts = load_model(model_id=model_id, hf_token=hf_token)

    sample_rate = 24000
    pause_samples = int(sample_rate * pause_duration)
    silence = np.zeros(pause_samples, dtype=np.float32)

    generated_segments = []
    total_chunks = len(chunks)
    print(f"\n[Remote Worker] Starting synthesis of {total_chunks} chunk(s) (Speaker: {speaker}, Style: {style})...", flush=True)

    for idx, chunk in enumerate(chunks):
        chunk_text = chunk.strip()
        if not chunk_text:
            continue

        chunk_chk_file = os.path.join(CHUNKS_DIR, f"chunk_{idx:04d}.npy")

        # Resume from checkpoint if already computed!
        if os.path.exists(chunk_chk_file) and os.path.getsize(chunk_chk_file) > 0:
            try:
                wav_np = np.load(chunk_chk_file)
                generated_segments.append(wav_np)
                print(f"  [{idx + 1}/{total_chunks}] (Cached) Reused {len(wav_np)/sample_rate:.1f}s segment.", flush=True)
                continue
            except Exception:
                pass

        snippet = chunk_text[:45].replace("\n", " ")
        print(f"  [{idx + 1}/{total_chunks}] Synthesizing ({len(chunk_text)} chars): \"{snippet}...\"", flush=True)
        t_chunk_start = time.time()

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

        # Save checkpoint immediately
        np.save(chunk_chk_file, wav_np)
        generated_segments.append(wav_np)

        chunk_dur = len(wav_np) / sample_rate
        chunk_time = time.time() - t_chunk_start
        print(f"  [{idx + 1}/{total_chunks}] ✔ Done in {chunk_time:.1f}s ({chunk_dur:.1f}s audio)", flush=True)

    if not generated_segments:
        raise ValueError("Synthesis yielded no audio output.")

    print("\n[Remote Worker] Concatenating audio segments...", flush=True)
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

    print(f"[Remote Worker] Encoding to target format: {output_format}...", flush=True)
    if output_format == "opus":
        cmd = [
            "ffmpeg", "-y", "-i", temp_wav,
            "-c:a", "libopus", "-b:a", "24k", "-vbr", "on",
            remote_out_path
        ]
        subprocess.run(cmd, check=True, capture_output=True)
    elif output_format == "mp3":
        cmd = [
            "ffmpeg", "-y", "-i", temp_wav,
            "-codec:a", "libmp3lame", "-b:a", "64k",
            remote_out_path
        ]
        subprocess.run(cmd, check=True, capture_output=True)
    else:  # wav
        if os.path.exists(remote_out_path):
            os.remove(remote_out_path)
        os.rename(temp_wav, remote_out_path)

    if os.path.exists(temp_wav) and output_format != "wav":
        os.remove(temp_wav)

    # Clean up chunk checkpoints once audio is fully built
    for f in os.listdir(CHUNKS_DIR):
        try:
            os.remove(os.path.join(CHUNKS_DIR, f))
        except Exception:
            pass

    audio_duration = float(len(full_audio) / sample_rate)
    elapsed_time = float(time.time() - start_time)

    result_data = {
        "success": True,
        "remote_output_path": remote_out_path,
        "format": output_format,
        "duration_seconds": round(audio_duration, 2),
        "elapsed_seconds": round(elapsed_time, 2),
        "chunks_processed": total_chunks,
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
