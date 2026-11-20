#!/usr/bin/env python3
"""
Edge TTS Engine for make_audio.
High-Throughput Microsoft Edge TTS synthesis supporting Bengali, Hindi, and English
with parallel chunking, automatic retry, and 24 kbps / 24 kHz Opus output.
"""

import asyncio
import atexit
import os
import random
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import edge_tts

TEMP_DIRS: List[str] = []

VOICE_MAP = {
    "bn": {
        "male": "bn-IN-BashkarNeural",
        "female": "bn-IN-TanishaaNeural",
        "default": "bn-IN-BashkarNeural",
    },
    "hi": {
        "male": "hi-IN-MadhurNeural",
        "female": "hi-IN-SwaraNeural",
        "default": "hi-IN-MadhurNeural",
    },
    "en": {
        "us": {
            "female": "en-US-AriaNeural",
            "male": "en-US-GuyNeural",
            "default": "en-US-AriaNeural",
        },
        "in": {
            "female": "en-IN-NeerjaNeural",
            "male": "en-IN-PrabhatNeural",
            "default": "en-IN-NeerjaNeural",
        },
        "gb": {
            "female": "en-GB-SoniaNeural",
            "male": "en-GB-RyanNeural",
            "default": "en-GB-SoniaNeural",
        },
    },
}

LOCALIZED_NOTICES = {
    "en": {
        "code": "Please refer to the code example.",
        "math": "Please refer to the equation.",
    },
    "bn": {
        "code": "অনুগ্রহ করে কোড উদাহরণটি দেখুন।",
        "math": "অনুগ্রহ করে সমীকরণটি দেখুন।",
    },
    "hi": {
        "code": "कृपया कोड उदाहरण देखें।",
        "math": "कृपया समीकरण देखें।",
    },
}

LANG_NAMES = {
    "bn": "Bengali",
    "hi": "Hindi",
    "en": "English",
}


def cleanup_all_temp_dirs() -> None:
    for d in TEMP_DIRS:
        shutil.rmtree(d, ignore_errors=True)


def sig_handler(sig, frame) -> None:
    cleanup_all_temp_dirs()
    print("\n[!] Interrupted by user. Cleaned temporary files and exiting cleanly.", file=sys.stderr)
    sys.exit(130)


signal.signal(signal.SIGINT, sig_handler)
signal.signal(signal.SIGTERM, sig_handler)
atexit.register(cleanup_all_temp_dirs)


def print_voices_catalog() -> None:
    print("""
========================================================================================
                   make_audio (Edge Engine) Available Voices & Accents
========================================================================================
 Language   Locale   Gender   Voice Name                  Notes
----------------------------------------------------------------------------------------
 Bengali    bn-IN    Male     bn-IN-BashkarNeural         ★ Default for Bengali (India)
 Bengali    bn-IN    Female   bn-IN-TanishaaNeural        Bengali (India)
 Bengali    bn-BD    Male     bn-BD-PradeepNeural         Bengali (Bangladesh)
 Bengali    bn-BD    Female   bn-BD-NabanitaNeural        Bengali (Bangladesh)

 Hindi      hi-IN    Male     hi-IN-MadhurNeural          ★ Default for Hindi (India)
 Hindi      hi-IN    Female   hi-IN-SwaraNeural           Hindi (India)

 English    en-US    Female   en-US-AriaNeural            ★ Default for English (US)
 English    en-US    Male     en-US-GuyNeural             English (US)
 English    en-IN    Female   en-IN-NeerjaNeural          English (India, -a in)
 English    en-IN    Male     en-IN-PrabhatNeural         English (India, -a in)
 English    en-GB    Female   en-GB-SoniaNeural           English (UK, -a gb)
 English    en-GB    Male     en-GB-RyanNeural            English (UK, -a gb)
----------------------------------------------------------------------------------------
Flags:
  -g, --gender <male|female> : Select gender variant
  -a, --accent <us|in|gb>    : Select English accent variant
  --voice <voice_name>       : Override directly with any specific voice name
========================================================================================
""")


def detect_language(text: str, override: Optional[str] = None) -> str:
    if override:
        ov = override.lower()
        if ov in ("bn", "bengali"):
            return "bn"
        if ov in ("hi", "hindi"):
            return "hi"
        if ov in ("en", "english"):
            return "en"
        return ov

    bn_count = len(re.findall(r"[\u0980-\u09FF]", text))
    hi_count = len(re.findall(r"[\u0900-\u097F]", text))

    if bn_count > 15 and bn_count >= hi_count:
        return "bn"
    elif hi_count > 15:
        return "hi"
    return "en"


def resolve_voice(lang: str, gender: Optional[str] = None, accent: Optional[str] = None, explicit_voice: Optional[str] = None) -> str:
    if explicit_voice and explicit_voice != "af_heart":
        return explicit_voice

    gender_key = gender.lower() if gender else None
    accent_key = accent.lower() if accent else "us"

    if lang == "bn":
        if gender_key == "female":
            return VOICE_MAP["bn"]["female"]
        return VOICE_MAP["bn"]["default"]

    if lang == "hi":
        if gender_key == "female":
            return VOICE_MAP["hi"]["female"]
        return VOICE_MAP["hi"]["default"]

    # English
    en_sub = VOICE_MAP["en"].get(accent_key, VOICE_MAP["en"]["us"])
    if gender_key == "male":
        return en_sub["male"]
    elif gender_key == "female":
        return en_sub["female"]
    return en_sub["default"]


def speed_to_rate_str(speed: float) -> str:
    """Convert float speed multiplier (e.g. 1.2 -> '+20%', 0.85 -> '-15%') to Edge rate string."""
    pct = round((speed - 1.0) * 100)
    if pct >= 0:
        return f"+{pct}%"
    return f"{pct}%"


def smart_chunk_text(text: str, max_chars: int = 2500) -> List[str]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    paragraphs = text.split("\n\n")
    chunks: List[str] = []
    current_chunk: List[str] = []
    current_len = 0

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        if len(para) > max_chars:
            sentences = re.split(r"(?<=[.!?।\n])\s+", para)
            for s in sentences:
                s = s.strip()
                if not s:
                    continue
                if current_len + len(s) + 1 > max_chars and current_chunk:
                    chunks.append(" ".join(current_chunk))
                    current_chunk = [s]
                    current_len = len(s)
                else:
                    current_chunk.append(s)
                    current_len += len(s) + 1
        else:
            if current_len + len(para) + 2 > max_chars and current_chunk:
                chunks.append("\n\n".join(current_chunk))
                current_chunk = [para]
                current_len = len(para)
            else:
                current_chunk.append(para)
                current_len += len(para) + 2

    if current_chunk:
        chunks.append("\n\n".join(current_chunk))

    return chunks


async def synthesize_chunk_with_retry(
    chunk_text: str,
    voice: str,
    rate: str,
    output_mp3: Path,
    sem: asyncio.Semaphore,
    max_retries: int = 3,
    verbose: bool = False,
    chunk_label: str = ""
) -> None:
    async with sem:
        for attempt in range(1, max_retries + 1):
            try:
                communicate = edge_tts.Communicate(text=chunk_text, voice=voice, rate=rate)
                await communicate.save(str(output_mp3))
                if verbose:
                    print(f"    ↳ {chunk_label} generated ({output_mp3.stat().st_size} bytes)")
                return
            except Exception as e:
                if attempt == max_retries:
                    raise RuntimeError(f"Chunk failed after {max_retries} attempts: {e}")
                delay = (2 ** attempt) + random.uniform(0.1, 0.5)
                if verbose:
                    print(f"    [!] {chunk_label} retry {attempt}/{max_retries} in {delay:.1f}s ({e})")
                await asyncio.sleep(delay)


def assemble_audio(chunk_files: List[Path], output_path: Path, output_format: str = "opus", bitrate: str = "24k") -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fmt = output_format.lower().lstrip(".")
    
    # Configure ffmpeg encoding based on desired output format
    if fmt == "opus":
        codec_args = ["-c:a", "libopus", "-b:a", bitrate, "-ar", "24000", "-ac", "1"]
    elif fmt == "mp3":
        codec_args = ["-c:a", "libmp3lame", "-b:a", "64k", "-ar", "24000", "-ac", "1"]
    elif fmt == "wav":
        codec_args = ["-c:a", "pcm_s16le", "-ar", "24000", "-ac", "1"]
    else:
        codec_args = ["-c:a", "libopus", "-b:a", bitrate, "-ar", "24000", "-ac", "1"]

    if len(chunk_files) == 1:
        cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(chunk_files[0])] + codec_args + [str(output_path)]
    else:
        manifest = chunk_files[0].parent / "concat_list.txt"
        with open(manifest, "w", encoding="utf-8") as f:
            for p in chunk_files:
                f.write(f"file '{p.resolve()}'\n")
        cmd = ["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(manifest)] + codec_args + [str(output_path)]

    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if res.returncode != 0:
        err = res.stderr.decode("utf-8", errors="ignore").strip()
        raise RuntimeError(f"FFmpeg encoding error: {err}")


def estimate_duration_str(char_count: int) -> str:
    seconds = max(1, int(char_count / 15))
    if seconds < 60:
        return f"~{seconds}s"
    mins = seconds // 60
    rem = seconds % 60
    return f"~{mins}m {rem}s"


async def synthesize_edge_tts(
    text: str,
    output_path: Path,
    voice: Optional[str] = None,
    lang: Optional[str] = None,
    gender: Optional[str] = None,
    accent: Optional[str] = None,
    rate: str = "+0%",
    workers: int = 4,
    chunk_size: int = 2500,
    output_format: str = "opus",
    bitrate: str = "24k",
    verbose: bool = False
) -> Tuple[Path, str, str]:
    """
    Synthesize text to output_path using Edge TTS with chunking and concurrency.
    Returns: (output_path, resolved_voice, resolved_lang)
    """
    detected_lang = detect_language(text, override=lang)
    resolved_voice = resolve_voice(detected_lang, gender=gender, accent=accent, explicit_voice=voice)
    chunks = smart_chunk_text(text, max_chars=chunk_size)

    if not chunks:
        raise ValueError("No readable text provided for synthesis.")

    temp_dir = tempfile.mkdtemp(prefix="make_audio_edge_")
    TEMP_DIRS.append(temp_dir)
    temp_dir_path = Path(temp_dir)
    sem = asyncio.Semaphore(workers)

    try:
        chunk_files = []
        chunk_tasks = []
        for idx, chunk in enumerate(chunks):
            chunk_file = temp_dir_path / f"chunk_{idx:04d}.mp3"
            chunk_files.append(chunk_file)
            label = f"[{idx+1}/{len(chunks)}]"
            chunk_tasks.append(
                synthesize_chunk_with_retry(
                    chunk,
                    resolved_voice,
                    rate,
                    chunk_file,
                    sem,
                    max_retries=3,
                    verbose=verbose,
                    chunk_label=label
                )
            )

        await asyncio.gather(*chunk_tasks)
        assemble_audio(chunk_files, output_path, output_format=output_format, bitrate=bitrate)
        return output_path, resolved_voice, detected_lang
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
        if temp_dir in TEMP_DIRS:
            TEMP_DIRS.remove(temp_dir)
