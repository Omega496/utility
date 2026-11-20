#!/usr/bin/env python3
"""
make_audio: Unified High-Throughput Document to Audio CLI Tool.

Supports:
- Default: Microsoft Edge TTS (multilingual: Bengali, Hindi, English, 24 kbps Opus, parallel chunking)
- Google Colab GPU Acceleration: Kokoro-TTS (--colab)
- Local Hardware Synthesis: Kokoro-TTS (--local)
- Inputs: Markdown (.md), Text (.txt), PDF (.pdf), direct string (-t), or interactive scratchpad (--temp)
"""

import argparse
import asyncio
import atexit
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import List, Optional

try:
    from pdf.cleaner import clean_document_for_tts, clean_markdown_for_tts
    from pdf.colab_tts import ColabTTS, ColabTTSError
    from pdf.edge_engine import (
        LANG_NAMES,
        detect_language,
        estimate_duration_str,
        print_voices_catalog,
        resolve_voice,
        smart_chunk_text,
        speed_to_rate_str,
        synthesize_edge_tts,
    )
    from pdf.pdf_extractor import extract_text_from_pdf
    from pdf.player import play_audio_in_terminal
    from pdf.tts import KokoroTTS
except ModuleNotFoundError:
    src_dir = Path(__file__).resolve().parent.parent
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))
    from pdf.cleaner import clean_document_for_tts, clean_markdown_for_tts
    from pdf.colab_tts import ColabTTS, ColabTTSError
    from pdf.edge_engine import (
        LANG_NAMES,
        detect_language,
        estimate_duration_str,
        print_voices_catalog,
        resolve_voice,
        smart_chunk_text,
        speed_to_rate_str,
        synthesize_edge_tts,
    )
    from pdf.pdf_extractor import extract_text_from_pdf
    from pdf.player import play_audio_in_terminal
    from pdf.tts import KokoroTTS

SUPPORTED_EXTENSIONS = {".md", ".markdown", ".txt", ".pdf"}
IGNORE_FILENAMES = {"requirements.txt", "constraints.txt"}


def parse_args():
    parser = argparse.ArgumentParser(
        prog="make_audio",
        description="Unified Document to Audio CLI Tool with Microsoft Edge TTS (default), Google Colab (--colab), and Local Kokoro-TTS (--local)."
    )
    parser.add_argument(
        "input",
        nargs="*",
        default=[],
        help="Path to .md, .txt, .pdf file(s) or directory (e.g. '.') to convert (default: current directory '.')",
    )
    parser.add_argument(
        "-R",
        "-r",
        "--recursive",
        action="store_true",
        default=False,
        help="Recursively scan subdirectories for convertible files.",
    )
    parser.add_argument(
        "-t",
        "--text",
        default=None,
        help="Input text string directly to synthesize and play in the terminal.",
    )
    parser.add_argument(
        "--temp",
        nargs="?",
        const="temp.md",
        default=None,
        help="Open a scratchpad document in nano (default: temp.md), convert to audio, play in terminal, and delete temporary files upon exit.",
    )
    parser.add_argument(
        "--play",
        action="store_true",
        default=False,
        help="Play audio interactively in the terminal (temporary file deleted upon close if -o is omitted).",
    )
    parser.add_argument(
        "--no-play",
        action="store_true",
        default=False,
        help="Do not automatically play audio when using -t/--text.",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Output audio filepath (.opus, .wav, or .mp3) for a single file, or destination folder for batch conversion (default: .opus at 24k).",
    )
    parser.add_argument(
        "--format",
        choices=["opus", "wav", "mp3"],
        default="opus",
        help="Audio output format (default: opus at 24k).",
    )
    parser.add_argument(
        "--bitrate",
        default="24k",
        help="Bitrate for Opus audio encoding (default: 24k).",
    )
    parser.add_argument(
        "-v",
        "--voice",
        default=None,
        help="Voice override (for Edge TTS: e.g. bn-IN-BashkarNeural; for Kokoro: e.g. af_heart).",
    )
    parser.add_argument(
        "-g",
        "--gender",
        choices=["male", "female"],
        help="Preferred voice gender (for Edge TTS).",
    )
    parser.add_argument(
        "-a",
        "--accent",
        choices=["us", "in", "gb"],
        help="Preferred English regional accent (us, in, gb).",
    )
    parser.add_argument(
        "--lang",
        choices=["bn", "hi", "en"],
        help="Explicit language override (bn, hi, en).",
    )
    parser.add_argument(
        "-s",
        "--speed",
        type=float,
        default=1.0,
        help="Speaking speed multiplier (default: 1.0). Automatically converted to rate for Edge TTS.",
    )
    parser.add_argument(
        "--rate",
        type=str,
        default=None,
        help="Explicit speed rate modifier for Edge TTS (e.g. +10%%, -15%%). Overrides -s/--speed.",
    )
    parser.add_argument(
        "-w",
        "--workers",
        type=int,
        default=4,
        help="Concurrent worker connections for Edge TTS chunk queue (default: 4).",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=2500,
        help="Character limit per audio chunk for Edge TTS (default: 2500).",
    )
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        default=False,
        help="Force re-conversion even if target .opus already exists and is up to date.",
    )
    parser.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        default=False,
        help="Preview conversion plan, chunks, and voice allocations without generating audio.",
    )
    parser.add_argument(
        "--voices",
        action="store_true",
        help="List all available voices and accents and exit.",
    )
    parser.add_argument(
        "-p",
        "--pages",
        default=None,
        help="For PDF files: page range to convert (e.g. '1', '1-3', '1,2,5'). Defaults to all pages.",
    )
    parser.add_argument(
        "-d",
        "--device",
        choices=["cuda", "cpu"],
        default=None,
        help="For local Kokoro engine: computation device (default: auto-detected CUDA/CPU).",
    )
    parser.add_argument(
        "--engine",
        choices=["edge", "colab", "local"],
        default=os.environ.get("MAKE_AUDIO_ENGINE", "edge"),
        help="TTS execution engine: 'edge' (default), 'colab' (Google Colab GPU), or 'local' (local machine Kokoro-TTS).",
    )
    parser.add_argument(
        "--colab",
        action="store_true",
        default=False,
        help="Run TTS remotely on Google Colab GPU using Kokoro-TTS.",
    )
    parser.add_argument(
        "--local",
        action="store_true",
        default=False,
        help="Run TTS locally on machine hardware using Kokoro-TTS.",
    )
    parser.add_argument(
        "--colab-session",
        default="make-audio",
        help="Google Colab session name (default: make-audio).",
    )
    parser.add_argument(
        "--colab-gpu",
        default="T4",
        help="Colab GPU accelerator variant (e.g. 'T4', 'L4', 'A100'). Default: T4.",
    )
    parser.add_argument(
        "--colab-timeout",
        type=float,
        default=600.0,
        help="Timeout in seconds for remote Colab synthesis (default: 600.0).",
    )
    parser.add_argument(
        "--keep-colab",
        action="store_true",
        default=False,
        help="Keep the Colab VM running after synthesis instead of automatically stopping it.",
    )
    parser.add_argument(
        "--stop-colab",
        action="store_true",
        help="Stop the active Colab VM session and exit immediately.",
    )
    parser.add_argument(
        "--fallback-local",
        action="store_true",
        default=True,
        help="Automatically fall back to local hardware synthesis if Google Colab fails (default: True).",
    )
    parser.add_argument(
        "--no-fallback-local",
        action="store_false",
        dest="fallback_local",
        help="Do not fall back to local hardware synthesis if Google Colab fails.",
    )
    parser.add_argument(
        "--keep-display-math",
        action="store_true",
        help="Convert display math to spoken English instead of localized referral notice.",
    )
    parser.add_argument(
        "--keep-references",
        action="store_true",
        help="For PDF files: keep the bibliography / references section (default: omitted).",
    )
    parser.add_argument(
        "--save-cleaned-text",
        action="store_true",
        default=False,
        help="Save the cleaned plain text to a .txt file (default: False).",
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Clean and display the plain text without generating audio.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed synthesis progress, chunk metrics, and connection logs.",
    )
    return parser.parse_args()


def _filter_cleaned_duplicates(files: List[Path]) -> List[Path]:
    cleaned_stems = set()
    for f in files:
        if f.stem.endswith("_cleaned"):
            cleaned_stems.add((f.parent, f.stem[:-8]))

    result = []
    for f in files:
        if (f.parent, f.stem) in cleaned_stems and not f.stem.endswith("_cleaned"):
            continue
        result.append(f)
    return result


def collect_files(input_args: List[str], recursive: bool = False) -> List[Path]:
    collected: List[Path] = []

    def _is_valid_file(f: Path) -> bool:
        if not f.is_file():
            return False
        if f.name.startswith("."):
            return False
        if f.name.lower() in IGNORE_FILENAMES:
            return False
        if f.suffix.lower() not in SUPPORTED_EXTENSIONS:
            return False
        return True

    def _should_skip_txt_duplicate(f: Path, all_dir_files: set) -> bool:
        if f.name.endswith("_cleaned.txt"):
            stem_base = f.name[:-12]
            for ext in [".md", ".markdown", ".pdf", ".txt"]:
                if f"{stem_base}{ext}" in all_dir_files:
                    return True
        return False

    for item_str in input_args:
        p = Path(item_str).resolve()
        if not p.exists():
            print(f"[!] Warning: Input path '{item_str}' does not exist, skipping.", file=sys.stderr)
            continue
        if p.is_dir():
            direct_files = [f for f in sorted(p.iterdir()) if _is_valid_file(f) and f.stat().st_size > 0]
            if recursive or not direct_files:
                found: List[Path] = []
                for root, dirs, files in os.walk(p):
                    dirs[:] = [
                        d for d in sorted(dirs)
                        if not d.startswith(".") and d not in {"__pycache__", "node_modules", "venv", ".venv", "build", "dist"}
                    ]
                    root_path = Path(root)
                    dir_file_names = set(files)
                    for fname in sorted(files):
                        f = root_path / fname
                        if _is_valid_file(f) and f.stat().st_size > 0 and not _should_skip_txt_duplicate(f, dir_file_names):
                            found.append(f)
                filtered = _filter_cleaned_duplicates(found)
                collected.extend(filtered)
            else:
                dir_file_names = {f.name for f in direct_files}
                candidate_files = [f for f in direct_files if not _should_skip_txt_duplicate(f, dir_file_names)]
                filtered = _filter_cleaned_duplicates(candidate_files)
                collected.extend(filtered)
        elif p.is_file():
            collected.append(p)

    return collected


def _run_local_synthesis(args, cleaned_text: str, output_audio_path: Path) -> Path:
    """Run audio synthesis locally using PyTorch and KokoroTTS."""
    kokoro_voice = args.voice if (args.voice and not args.voice.startswith(("bn-", "hi-", "en-"))) else "af_heart"
    tts = KokoroTTS(lang_code="a", device=args.device)

    paragraphs = [p for p in cleaned_text.split("\n\n") if p.strip()]
    total_paras = len(paragraphs)
    word_count = sum(len(p.split()) for p in paragraphs)

    if args.verbose:
        print(f"Processing {total_paras} paragraphs ({word_count} words) on {tts.device.upper()}...")

        def _progress(current: int, total: int, snippet: str):
            pct = (current / total) * 100
            clean_snippet = snippet.replace("\n", " ").strip()
            if len(clean_snippet) > 50:
                clean_snippet = clean_snippet[:47] + "..."
            sys.stdout.write(f"\r[{pct:5.1f}%] [{current:02d}/{total:02d}] Generating: \"{clean_snippet}\"")
            sys.stdout.flush()

        progress_callback = _progress
    else:
        def _progress_simple(current: int, total: int, snippet: str):
            pct = (current / total) * 100
            clean_snippet = snippet.replace("\n", " ").strip()
            if len(clean_snippet) > 40:
                clean_snippet = clean_snippet[:37] + "..."
            sys.stdout.write(f"\r[Local] [{pct:5.1f}%] [{current:02d}/{total:02d}] Generating: \"{clean_snippet}\"")
            sys.stdout.flush()

        progress_callback = _progress_simple

    final_path = tts.convert_to_audio_file(
        text=cleaned_text,
        output_path=output_audio_path,
        voice=kokoro_voice,
        speed=args.speed,
        progress_callback=progress_callback,
        bitrate=getattr(args, "bitrate", "24k"),
    )

    sys.stdout.write("\n")
    sys.stdout.flush()
    return final_path


def main():
    args = parse_args()

    # Route engine shortcuts
    if args.colab:
        args.engine = "colab"
    elif args.local:
        args.engine = "local"

    # Display voice catalog if requested
    if args.voices:
        print_voices_catalog()
        return

    # Handle quick command: stop colab session
    if args.stop_colab:
        ColabTTS.stop_session(args.colab_session, verbose=args.verbose)
        return

    # Check if -t was passed with a filename intended for temporary scratchpad
    if args.text and (args.text.endswith((".txt", ".md")) and "\n" not in args.text and " " not in args.text and not Path(args.text).exists()):
        args.temp = args.text
        args.text = None

    # Check input arguments
    active_modes = [bool(args.input), bool(args.text), bool(args.temp)]
    if sum(active_modes) == 0:
        candidate_files = collect_files(["."], recursive=getattr(args, "recursive", False))
        if candidate_files:
            args.input = ["."]
            active_modes = [True, False, False]
        else:
            print("Error: Input file(s), directory, -t/--text, or --temp is required.", file=sys.stderr)
            print("Usage: make_audio [files_or_dirs...] [options]", file=sys.stderr)
            print("       make_audio -t \"some text to speak\" [options]", file=sys.stderr)
            print("       make_audio --temp [temp.md] [options]", file=sys.stderr)
            sys.exit(1)

    if sum(active_modes) > 1:
        print("Error: Cannot specify multiple input modes simultaneously (choose files, -t/--text, or --temp).", file=sys.stderr)
        sys.exit(1)

    # Compute rate string for Edge TTS
    effective_rate = args.rate if args.rate else speed_to_rate_str(args.speed)

    colab_instance = None
    if args.engine == "colab":
        colab_instance = ColabTTS(
            session_name=args.colab_session,
            gpu=args.colab_gpu,
            timeout=args.colab_timeout,
            verbose=args.verbose,
        )

    try:
        # Handle scratchpad editor mode (--temp)
        if args.temp:
            temp_filename = args.temp
            temp_doc_path = (Path.cwd() / temp_filename).resolve()

            editor = os.environ.get("EDITOR") or shutil.which("nano") or shutil.which("vim") or "nano"
            if not shutil.which(editor):
                print(f"Error: Editor '{editor}' not found. Please install nano.", file=sys.stderr)
                sys.exit(1)

            temp_doc_path.touch(exist_ok=True)
            atexit.register(lambda p=temp_doc_path: p.unlink(missing_ok=True))

            print(f"Opening scratchpad '{temp_doc_path.name}' in {Path(editor).name}...")
            print("Tip: Paste text, save with Ctrl+O and Enter, then exit with Ctrl+X.\n")
            time.sleep(1.0)

            temp_audio_file = None
            try:
                subprocess.run([editor, str(temp_doc_path)], check=False)
                if not temp_doc_path.exists():
                    print("Scratchpad was cancelled or not saved.")
                    return

                try:
                    raw_text = temp_doc_path.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    raw_text = temp_doc_path.read_text(encoding="latin-1")

                cleaned_text, detected_lang = clean_document_for_tts(
                    raw_text,
                    lang=args.lang,
                    keep_display_math=args.keep_display_math,
                )

                if not cleaned_text.strip():
                    print(f"Scratchpad '{temp_doc_path.name}' is empty. Cancelled.")
                    return

                if args.save_cleaned_text:
                    text_output_path = Path.cwd() / f"{temp_doc_path.stem}_cleaned.txt"
                    text_output_path.write_text(cleaned_text, encoding="utf-8")
                    if args.verbose:
                        print(f"Cleaned plain text saved to: {text_output_path}")

                if args.preview:
                    print("\n" + "=" * 50)
                    print(f"CLEANED TEXT PREVIEW: {temp_doc_path.name}")
                    print("=" * 50)
                    print(cleaned_text)
                    print("=" * 50)
                    return

                default_ext = f".{args.format.lstrip('.')}"
                if args.output:
                    output_audio_path = Path(args.output).resolve()
                    if output_audio_path.is_dir():
                        output_audio_path = output_audio_path / f"{temp_doc_path.stem}{default_ext}"
                    elif not output_audio_path.suffix:
                        output_audio_path = output_audio_path.with_suffix(default_ext)
                    is_audio_temp = False
                else:
                    tmp = tempfile.NamedTemporaryFile(suffix=f"_{temp_doc_path.stem}{default_ext}", delete=False)
                    output_audio_path = Path(tmp.name)
                    tmp.close()
                    temp_audio_file = output_audio_path
                    is_audio_temp = True
                    atexit.register(lambda p=output_audio_path: p.unlink(missing_ok=True))

                engine_str = f" (engine: {args.engine})" if args.verbose else ""
                print(f"Synthesizing audio{engine_str}...")

                text_format = output_audio_path.suffix.lstrip(".") if output_audio_path.suffix else args.format
                if args.engine == "edge":
                    final_path, resolved_voice, _ = asyncio.run(
                        synthesize_edge_tts(
                            text=cleaned_text,
                            output_path=output_audio_path,
                            voice=args.voice,
                            lang=detected_lang,
                            gender=args.gender,
                            accent=args.accent,
                            rate=effective_rate,
                            workers=args.workers,
                            chunk_size=args.chunk_size,
                            output_format=text_format,
                            bitrate=getattr(args, "bitrate", "24k"),
                            verbose=args.verbose,
                        )
                    )
                elif args.engine == "colab":
                    try:
                        kokoro_voice = args.voice if (args.voice and not args.voice.startswith(("bn-", "hi-", "en-"))) else "af_heart"
                        final_path = colab_instance.convert_to_audio_file(
                            text=cleaned_text,
                            output_path=output_audio_path,
                            voice=kokoro_voice,
                            speed=args.speed,
                            stop_session_after=False,
                            bitrate=getattr(args, "bitrate", "24k"),
                        )
                    except Exception as e:
                        if args.fallback_local:
                            print(f"\n[make_audio] Colab error: {e}", file=sys.stderr)
                            print("[make_audio] Falling back to local Kokoro-TTS engine...", file=sys.stderr)
                            final_path = _run_local_synthesis(args, cleaned_text, output_audio_path)
                        else:
                            raise
                else:
                    final_path = _run_local_synthesis(args, cleaned_text, output_audio_path)

                if not is_audio_temp:
                    print(f"Audio file saved to: {final_path}")

                if not args.no_play:
                    play_audio_in_terminal(final_path, title=temp_doc_path.name)
            finally:
                if temp_doc_path and temp_doc_path.exists():
                    temp_doc_path.unlink(missing_ok=True)
                if temp_audio_file and temp_audio_file.exists():
                    temp_audio_file.unlink(missing_ok=True)
            return

        # Handle direct text input (-t / --text)
        if args.text:
            cleaned_text, detected_lang = clean_document_for_tts(
                args.text,
                lang=args.lang,
                keep_display_math=args.keep_display_math,
            )

            if not cleaned_text.strip():
                print("Error: Text is empty after cleaning.", file=sys.stderr)
                sys.exit(1)

            if args.save_cleaned_text:
                if args.output:
                    text_output_path = Path(args.output).with_suffix(".txt")
                else:
                    text_output_path = Path.cwd() / "text_cleaned.txt"
                text_output_path.write_text(cleaned_text, encoding="utf-8")
                if args.verbose:
                    print(f"Cleaned plain text saved to: {text_output_path}")

            if args.preview:
                print("\n" + "=" * 50)
                print("CLEANED TEXT PREVIEW:")
                print("=" * 50)
                print(cleaned_text)
                print("=" * 50)
                return

            default_ext = f".{args.format.lstrip('.')}"
            temp_audio_file = None

            if args.output:
                output_audio_path = Path(args.output).resolve()
                if output_audio_path.is_dir():
                    output_audio_path = output_audio_path / f"text_output{default_ext}"
                elif not output_audio_path.suffix:
                    output_audio_path = output_audio_path.with_suffix(default_ext)
                is_temporary = False
            else:
                tmp = tempfile.NamedTemporaryFile(suffix=default_ext, delete=False)
                output_audio_path = Path(tmp.name)
                tmp.close()
                temp_audio_file = output_audio_path
                is_temporary = True
                atexit.register(lambda p=output_audio_path: p.unlink(missing_ok=True))

            try:
                engine_str = f" (engine: {args.engine})" if args.verbose else ""
                if args.verbose:
                    print(f"Synthesizing text{engine_str}...")

                text_format = output_audio_path.suffix.lstrip(".") if output_audio_path.suffix else args.format
                if args.engine == "edge":
                    final_path, resolved_voice, _ = asyncio.run(
                        synthesize_edge_tts(
                            text=cleaned_text,
                            output_path=output_audio_path,
                            voice=args.voice,
                            lang=detected_lang,
                            gender=args.gender,
                            accent=args.accent,
                            rate=effective_rate,
                            workers=args.workers,
                            chunk_size=args.chunk_size,
                            output_format=text_format,
                            bitrate=getattr(args, "bitrate", "24k"),
                            verbose=args.verbose,
                        )
                    )
                elif args.engine == "colab":
                    try:
                        kokoro_voice = args.voice if (args.voice and not args.voice.startswith(("bn-", "hi-", "en-"))) else "af_heart"
                        final_path = colab_instance.convert_to_audio_file(
                            text=cleaned_text,
                            output_path=output_audio_path,
                            voice=kokoro_voice,
                            speed=args.speed,
                            stop_session_after=False,
                            bitrate=getattr(args, "bitrate", "24k"),
                        )
                    except Exception as e:
                        if args.fallback_local:
                            print(f"\n[make_audio] Colab error: {e}", file=sys.stderr)
                            print("[make_audio] Falling back to local Kokoro-TTS engine...", file=sys.stderr)
                            final_path = _run_local_synthesis(args, cleaned_text, output_audio_path)
                        else:
                            raise
                else:
                    final_path = _run_local_synthesis(args, cleaned_text, output_audio_path)

                if not is_temporary:
                    print(f"Audio file saved to: {final_path}")

                if not args.no_play:
                    snippet = args.text[:60] + "..." if len(args.text) > 60 else args.text
                    play_audio_in_terminal(final_path, title=snippet)
            finally:
                if is_temporary and temp_audio_file and temp_audio_file.exists():
                    temp_audio_file.unlink(missing_ok=True)
            return

        # Handle file / directory targets
        files_to_process = collect_files(args.input, recursive=getattr(args, "recursive", False))
        if not files_to_process:
            print(f"Error: No convertible files ({', '.join(sorted(SUPPORTED_EXTENSIONS))}) found in specified target(s).", file=sys.stderr)
            sys.exit(1)

        default_ext = f".{args.format.lstrip('.')}"
        plans = []
        base_dir = Path.cwd()
        output_dir = Path(args.output).resolve() if args.output else None

        is_batch = len(files_to_process) > 1 or (len(args.input) == 1 and Path(args.input[0]).is_dir())

        # Build plan for each file
        for f in files_to_process:
            is_temp_file = False
            if output_dir:
                if is_batch:
                    if output_dir.suffix and not output_dir.is_dir():
                        out_audio = output_dir.parent / f"{f.stem}{output_dir.suffix}"
                    else:
                        output_dir.mkdir(parents=True, exist_ok=True)
                        out_audio = output_dir / f"{f.stem}{default_ext}"
                else:
                    if output_dir.is_dir():
                        output_dir.mkdir(parents=True, exist_ok=True)
                        out_audio = output_dir / f"{f.stem}{default_ext}"
                    elif output_dir.suffix:
                        out_audio = output_dir
                    else:
                        out_audio = output_dir.with_suffix(default_ext)
            elif args.play:
                tmp = tempfile.NamedTemporaryFile(suffix=f"_{f.stem}{default_ext}", delete=False)
                out_audio = Path(tmp.name)
                tmp.close()
                atexit.register(lambda p=out_audio: p.unlink(missing_ok=True))
                is_temp_file = True
            else:
                out_audio = f.with_suffix(default_ext)
                is_temp_file = False

            # Skip check if not forced
            if not args.force and not args.play and out_audio.exists():
                if out_audio.stat().st_mtime >= f.stat().st_mtime:
                    plans.append({"file": f, "status": "skipped", "out_path": out_audio})
                    continue

            # Extract raw text
            try:
                if f.suffix.lower() == ".pdf":
                    raw_text = extract_text_from_pdf(
                        pdf_path=f,
                        page_range=args.pages,
                        skip_references=not args.keep_references,
                    )
                else:
                    raw_text = f.read_text(encoding="utf-8", errors="replace")
            except Exception as e:
                plans.append({"file": f, "status": "error", "error": f"Read error: {e}", "out_path": out_audio})
                continue

            cleaned_text, detected_lang = clean_document_for_tts(
                raw_text,
                lang=args.lang,
                keep_display_math=args.keep_display_math,
            )

            if not cleaned_text.strip():
                plans.append({"file": f, "status": "error", "error": "Empty text after cleaning", "out_path": out_audio})
                continue

            resolved_voice = resolve_voice(
                detected_lang,
                gender=args.gender,
                accent=args.accent,
                explicit_voice=args.voice
            )
            chunks = smart_chunk_text(cleaned_text, max_chars=args.chunk_size)

            plans.append({
                "file": f,
                "status": "ready",
                "lang": detected_lang,
                "voice": resolved_voice,
                "cleaned_text": cleaned_text,
                "chunks": chunks,
                "out_path": out_audio,
                "is_temporary": is_temp_file,
                "char_count": len(cleaned_text)
            })

        # Dry-run inspection
        if args.dry_run:
            print(f"\n🔍 [Dry-Run] Discovered {len(plans)} target(s) for engine '{args.engine}':")
            for idx, p in enumerate(plans, 1):
                fname = p["file"].name
                out_name = p["out_path"].name
                if p["status"] == "skipped":
                    print(f"  ⏭ [{idx}/{len(plans)}] {fname} -> {out_name} (Skipped: output already current)")
                elif p["status"] == "error":
                    print(f"  ✖ [{idx}/{len(plans)}] {fname} -> Error: {p['error']}")
                else:
                    lang_disp = LANG_NAMES.get(p["lang"], p["lang"])
                    chunk_str = f"{len(p['chunks'])} chunk" if len(p['chunks']) == 1 else f"{len(p['chunks'])} chunks"
                    dur = estimate_duration_str(p["char_count"])
                    print(f"  ✔ [{idx}/{len(plans)}] {fname} -> {out_name} | {lang_disp} | {p['voice']} | {chunk_str} ({dur})")
            print("\n✨ Dry run complete. No audio generated.\n")
            return

        # Preview mode
        if args.preview:
            for p in plans:
                if p["status"] == "ready":
                    print("\n" + "=" * 50)
                    print(f"CLEANED TEXT PREVIEW: {p['file'].name}")
                    print("=" * 50)
                    print(p["cleaned_text"])
                    print("=" * 50)
            return

        ready_plans = [p for p in plans if p["status"] == "ready"]
        total_targets = len(plans)

        if not ready_plans:
            print("✨ All files are up to date. Use -f / --force to re-encode.")
            return

        start_time = time.time()

        # Engine execution: Edge TTS
        if args.engine == "edge":
            print(f"Converting {len(ready_plans)} file(s) using {args.workers} workers (total targets: {total_targets})...")
            for idx, p in enumerate(plans, 1):
                if p["status"] == "skipped":
                    print(f"  ⏭ [{idx}/{total_targets}] {p['file'].name} -> {p['out_path'].name} (Skipped: up to date)")

            for idx, p in enumerate(plans, 1):
                if p["status"] != "ready":
                    continue

                f_path = p["file"]
                out_path = p["out_path"]
                cleaned_text = p["cleaned_text"]
                detected_lang = p["lang"]
                lang_disp = LANG_NAMES.get(detected_lang, detected_lang)
                chunks = p["chunks"]
                chunk_str = f"{len(chunks)} chunk" if len(chunks) == 1 else f"{len(chunks)} chunks"
                dur = estimate_duration_str(p["char_count"])

                if args.save_cleaned_text:
                    clean_txt_path = out_path.with_name(f"{f_path.stem}_cleaned.txt")
                    clean_txt_path.write_text(cleaned_text, encoding="utf-8")

                try:
                    file_format = out_path.suffix.lstrip(".") if out_path.suffix else args.format
                    final_path, resolved_voice, _ = asyncio.run(
                        synthesize_edge_tts(
                            text=cleaned_text,
                            output_path=out_path,
                            voice=args.voice,
                            lang=detected_lang,
                            gender=args.gender,
                            accent=args.accent,
                            rate=effective_rate,
                            workers=args.workers,
                            chunk_size=args.chunk_size,
                            output_format=file_format,
                            bitrate=getattr(args, "bitrate", "24k"),
                            verbose=args.verbose,
                        )
                    )
                    if not p.get("is_temporary"):
                        print(f"  ✔ [{idx}/{total_targets}] {f_path.name} -> {out_path.name}   ({lang_disp} | {chunk_str} | {dur})")

                    if args.play:
                        play_audio_in_terminal(final_path, title=f_path.name)
                except Exception as e:
                    print(f"  ✖ [{idx}/{total_targets}] {f_path.name} -> Failed: {e}", file=sys.stderr)
                finally:
                    if p.get("is_temporary") and out_path.exists():
                        out_path.unlink(missing_ok=True)

            elapsed = time.time() - start_time
            print(f"✨ Completed in {elapsed:.1f}s. All audio encoded to {args.bitrate} Opus.")

        # Engine execution: Colab or Local Kokoro
        else:
            engine_label = "Google Colab" if args.engine == "colab" else "Local Kokoro"
            print(f"Converting {len(ready_plans)} file(s) via {engine_label}...")

            for idx, p in enumerate(plans, 1):
                if p["status"] != "ready":
                    continue

                f_path = p["file"]
                out_path = p["out_path"]
                cleaned_text = p["cleaned_text"]

                if args.save_cleaned_text:
                    clean_txt_path = out_path.with_name(f"{f_path.stem}_cleaned.txt")
                    clean_txt_path.write_text(cleaned_text, encoding="utf-8")

                print(f"\n[{idx}/{total_targets}] Converting: {f_path.name} ({engine_label})")
                try:
                    if args.engine == "colab":
                        try:
                            kokoro_voice = args.voice if (args.voice and not args.voice.startswith(("bn-", "hi-", "en-"))) else "af_heart"
                            final_path = colab_instance.convert_to_audio_file(
                                text=cleaned_text,
                                output_path=out_path,
                                voice=kokoro_voice,
                                speed=args.speed,
                                stop_session_after=False,
                                bitrate=getattr(args, "bitrate", "24k"),
                            )
                        except Exception as e:
                            if args.fallback_local:
                                print(f"\n[make_audio] Colab error: {e}", file=sys.stderr)
                                print("[make_audio] Falling back to local Kokoro-TTS...", file=sys.stderr)
                                final_path = _run_local_synthesis(args, cleaned_text, out_path)
                            else:
                                raise
                    else:
                        final_path = _run_local_synthesis(args, cleaned_text, out_path)

                    if not p.get("is_temporary"):
                        print(f"Audio file saved to: {final_path}")
                    if args.play:
                        play_audio_in_terminal(final_path, title=f_path.name)
                except Exception as e:
                    print(f"✖ Failed on {f_path.name}: {e}", file=sys.stderr)
                finally:
                    if p.get("is_temporary") and out_path.exists():
                        out_path.unlink(missing_ok=True)

    except KeyboardInterrupt:
        print("\n[make_audio] Interrupted by user. Exiting cleanly.", file=sys.stderr)
        sys.exit(130)
    finally:
        if args.engine == "colab" and colab_instance and not args.keep_colab:
            ColabTTS.stop_session(args.colab_session, verbose=args.verbose)


if __name__ == "__main__":
    main()
