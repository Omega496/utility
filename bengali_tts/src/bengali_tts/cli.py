#!/usr/bin/env python3
"""
Command Line Interface for Bengali TTS (Indic-Speak) via Google Colab.
Provides the make_bengali_audio tool.
"""

import argparse
import os
import sys
import pathlib
import time
from typing import List, Optional, Set, Tuple

from bengali_tts.config import (
    DEFAULT_SESSION_NAME,
    DEFAULT_GPU,
    DEFAULT_SPEAKER,
    DEFAULT_STYLE,
    DEFAULT_TEMPERATURE,
    DEFAULT_PAUSE_DURATION,
    DEFAULT_OUTPUT_FORMAT,
    MAX_CHUNK_LENGTH,
    SUPPORTED_SPEAKERS,
    SUPPORTED_STYLES,
    SUPPORTED_EXTENSIONS,
    IGNORE_FILENAMES,
    SKIP_DIRECTORIES,
)
from bengali_tts.colab_client import BengaliTTSColabClient, HuggingFaceAccessError, ColabBengaliTTSError
from bengali_tts.text_utils import normalize_bengali_text, chunk_text


def print_speakers_table():
    """Prints a formatted table of available speakers."""
    print("\nAvailable Voices for Indic-Speak (Bengali):")
    print("=" * 75)
    print(f"{'Speaker':<12} | {'Language':<10} | {'Gender':<8} | {'Description'}")
    print("-" * 75)
    for name, meta in SUPPORTED_SPEAKERS.items():
        native_tag = " [Native]" if meta.get("native") else ""
        print(f"{name + native_tag:<12} | {meta['language']:<10} | {meta['gender']:<8} | {meta['description']}")
    print("=" * 75)
    print("Default speaker is 'Ishita' (Female native Bengali).\n")


def print_styles_list():
    """Prints available vocal emotion styles."""
    print("\nAvailable Vocal Styles / Emotions:")
    print("-" * 40)
    for s in SUPPORTED_STYLES:
        marker = " (Default)" if s == DEFAULT_STYLE else ""
        print(f" - {s}{marker}")
    print("-" * 40)
    print("Descriptive phrases are also accepted (e.g. 'explanatory, calm').\n")


def discover_files(targets: List[str], recursive: bool = False) -> List[pathlib.Path]:
    """
    Finds matching text/markdown files (.txt, .md, .markdown) from given target paths or directories.
    """
    discovered: List[pathlib.Path] = []
    seen: Set[pathlib.Path] = set()

    for target in targets:
        p = pathlib.Path(target).resolve()
        if not p.exists():
            continue

        if p.is_file():
            if p.suffix.lower() in SUPPORTED_EXTENSIONS and p.name not in IGNORE_FILENAMES:
                if p not in seen:
                    discovered.append(p)
                    seen.add(p)
        elif p.is_dir():
            if recursive:
                for root, dirs, files in os.walk(p):
                    # Filter out directories to skip
                    dirs[:] = [d for d in dirs if d not in SKIP_DIRECTORIES and not d.startswith(".")]
                    for f in sorted(files):
                        fp = pathlib.Path(root) / f
                        if fp.suffix.lower() in SUPPORTED_EXTENSIONS and fp.name not in IGNORE_FILENAMES:
                            if fp not in seen:
                                discovered.append(fp)
                                seen.add(fp)
            else:
                for entry in sorted(p.iterdir()):
                    if entry.is_file():
                        if entry.suffix.lower() in SUPPORTED_EXTENSIONS and entry.name not in IGNORE_FILENAMES:
                            if entry not in seen:
                                discovered.append(entry)
                                seen.add(entry)

    return discovered


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="make_bengali_audio",
        description="Convert Bengali text and markdown files to audio (.opus) using Indic-Speak TTS on Google Colab GPU.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Usage Examples:
  # Convert a single markdown or text file to opus (default format)
  make_bengali_audio story.md
  # -> Outputs: story.opus

  # Convert all .md and .txt files in the current folder
  make_bengali_audio .

  # Convert all .md and .txt files in the current folder and subfolders recursively
  make_bengali_audio . -r

  # Synthesize a single Bengali text string directly
  make_bengali_audio -t "আমার সোনার বাংলা, আমি তোমায় ভালোবাসি।" -o national_song.opus

  # Convert with male voice (Sourav) and emotional delivery
  make_bengali_audio chapter1.txt -s Sourav --style HAPPY

  # Check Colab session status or stop the remote VM
  make_bengali_audio --status
  make_bengali_audio --stop
""",
    )

    # Positional target files/directories or direct text
    parser.add_argument(
        "inputs",
        nargs="*",
        default=[],
        help="Path to .md / .txt file(s), directory (e.g. '.'), or direct text string to convert.",
    )

    # Directory scanning options
    parser.add_argument(
        "-r", "-R", "--recursive",
        action="store_true",
        default=False,
        dest="recursive",
        help="Recursively scan subdirectories for convertible text/markdown files.",
    )

    # Direct text options
    parser.add_argument(
        "-t", "--text",
        type=str,
        default=None,
        help="Input text string directly to synthesize into speech.",
    )

    # Output options
    parser.add_argument(
        "-o", "--output",
        type=str,
        default=None,
        help="Output audio path (.opus, .wav, or .mp3) for single file, or destination folder for batch conversion. Default: <stem>.opus",
    )
    parser.add_argument(
        "--format",
        choices=["opus", "wav", "mp3"],
        default=DEFAULT_OUTPUT_FORMAT,
        help=f"Audio output format (default: {DEFAULT_OUTPUT_FORMAT}).",
    )

    # Voice & style options
    parser.add_argument(
        "-s", "--speaker",
        type=str,
        default=DEFAULT_SPEAKER,
        choices=list(SUPPORTED_SPEAKERS.keys()),
        help=f"Voice speaker profile to use (default: {DEFAULT_SPEAKER}).",
    )
    parser.add_argument(
        "--style",
        type=str,
        default=DEFAULT_STYLE,
        help=f"Vocal emotion style (e.g., NEUTRAL, HAPPY, SAD, ANGER; default: {DEFAULT_STYLE}).",
    )
    parser.add_argument(
        "--temp", "--temperature",
        type=float,
        default=DEFAULT_TEMPERATURE,
        dest="temperature",
        help=f"Sampling temperature (default: {DEFAULT_TEMPERATURE}).",
    )
    parser.add_argument(
        "--pause",
        type=float,
        default=DEFAULT_PAUSE_DURATION,
        help=f"Pause duration (seconds) between sentences/chunks (default: {DEFAULT_PAUSE_DURATION}s).",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=MAX_CHUNK_LENGTH,
        help=f"Max character length per chunk for long texts (default: {MAX_CHUNK_LENGTH}).",
    )

    # Colab environment controls
    parser.add_argument(
        "--session",
        type=str,
        default=DEFAULT_SESSION_NAME,
        help=f"Colab session name to use or connect to (default: {DEFAULT_SESSION_NAME}).",
    )
    parser.add_argument(
        "--gpu",
        type=str,
        default=DEFAULT_GPU,
        help=f"GPU accelerator type to request on Colab (default: {DEFAULT_GPU}). Set to 'None' for CPU.",
    )
    parser.add_argument(
        "--stop-after",
        action="store_true",
        help="Stop and release the Colab VM immediately after synthesis finishes.",
    )

    # Informational and lifecycle actions
    parser.add_argument(
        "--list-speakers", "--list-voices",
        action="store_true",
        dest="list_speakers",
        help="List available speaker voices and exit.",
    )
    parser.add_argument(
        "--list-styles",
        action="store_true",
        dest="list_styles",
        help="List available vocal styles/emotions and exit.",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Check the current status of the Colab VM session and exit.",
    )
    parser.add_argument(
        "--stop",
        action="store_true",
        help="Stop the designated Colab session to free compute resources and exit.",
    )

    return parser


def process_single_text(
    client: BengaliTTSColabClient,
    text: str,
    output_path: pathlib.Path,
    speaker: str,
    style: str,
    temperature: float,
    pause_duration: float,
    chunk_size: int,
    stop_session_after: bool = False,
) -> bool:
    """Processes a single text payload and downloads the audio."""
    clean_text = normalize_bengali_text(text)
    if not clean_text:
        print("  [!] Text is empty or contains no readable characters after normalization. Skipping.")
        return False

    chunks = chunk_text(clean_text, max_chunk_len=chunk_size)
    print(f"  • Text length: {len(clean_text)} chars | Chunks: {len(chunks)} | Speaker: {speaker} | Style: {style}")

    result = client.synthesize(
        chunks=chunks,
        output_path=output_path,
        speaker=speaker,
        style=style,
        temperature=temperature,
        pause_duration=pause_duration,
        stop_session_after=stop_session_after,
    )
    return True


def main():
    parser = build_parser()
    args = parser.parse_args()

    # Informational flags
    if args.list_speakers:
        print_speakers_table()
        sys.exit(0)

    if args.list_styles:
        print_styles_list()
        sys.exit(0)

    client = BengaliTTSColabClient(
        session_name=args.session,
        gpu=args.gpu if args.gpu.lower() != "none" else None,
        verbose=True,
    )

    # Lifecycle commands
    if args.status:
        stat = client.get_status()
        print(f"\n[Session '{args.session}'] Active: {stat.get('active')}")
        if stat.get("output"):
            print(f"Details:\n{stat['output']}")
        sys.exit(0)

    if args.stop:
        client.stop_session()
        sys.exit(0)

    # Case 1: Direct text passed via -t/--text flag
    if args.text:
        out_target = pathlib.Path(args.output) if args.output else pathlib.Path(f"output.{args.format}")
        print(f"\n[make_bengali_audio] Synthesizing direct text -> {out_target}")
        try:
            process_single_text(
                client=client,
                text=args.text,
                output_path=out_target,
                speaker=args.speaker,
                style=args.style,
                temperature=args.temperature,
                pause_duration=args.pause,
                chunk_size=args.chunk_size,
                stop_session_after=args.stop_after,
            )
            print("✔ Audio conversion complete!\n")
            sys.exit(0)
        except HuggingFaceAccessError as hf_err:
            print(str(hf_err), file=sys.stderr)
            sys.exit(2)
        except ColabBengaliTTSError as err:
            print(f"\n[make_bengali_audio Error] {err}", file=sys.stderr)
            sys.exit(1)

    # Case 2: Piped input from stdin
    if not args.inputs and not sys.stdin.isatty():
        stdin_content = sys.stdin.read().strip()
        if stdin_content:
            out_target = pathlib.Path(args.output) if args.output else pathlib.Path(f"output.{args.format}")
            print(f"\n[make_bengali_audio] Reading from stdin -> {out_target}")
            try:
                process_single_text(
                    client=client,
                    text=stdin_content,
                    output_path=out_target,
                    speaker=args.speaker,
                    style=args.style,
                    temperature=args.temperature,
                    pause_duration=args.pause,
                    chunk_size=args.chunk_size,
                    stop_session_after=args.stop_after,
                )
                print("✔ Audio conversion complete!\n")
                sys.exit(0)
            except HuggingFaceAccessError as hf_err:
                print(str(hf_err), file=sys.stderr)
                sys.exit(2)
            except ColabBengaliTTSError as err:
                print(f"\n[make_bengali_audio Error] {err}", file=sys.stderr)
                sys.exit(1)

    # Case 3: Positional arguments provided
    # Check if a single argument was passed and whether it's a direct text string rather than an existing file/dir
    if len(args.inputs) == 1:
        single_input = args.inputs[0]
        p_check = pathlib.Path(single_input)
        if not p_check.exists() and (" " in single_input or any("\u0980" <= c <= "\u09ff" for c in single_input)):
            # It's raw text
            out_target = pathlib.Path(args.output) if args.output else pathlib.Path(f"output.{args.format}")
            print(f"\n[make_bengali_audio] Synthesizing Bengali text string -> {out_target}")
            try:
                process_single_text(
                    client=client,
                    text=single_input,
                    output_path=out_target,
                    speaker=args.speaker,
                    style=args.style,
                    temperature=args.temperature,
                    pause_duration=args.pause,
                    chunk_size=args.chunk_size,
                    stop_session_after=args.stop_after,
                )
                print("✔ Audio conversion complete!\n")
                sys.exit(0)
            except HuggingFaceAccessError as hf_err:
                print(str(hf_err), file=sys.stderr)
                sys.exit(2)
            except ColabBengaliTTSError as err:
                print(f"\n[make_bengali_audio Error] {err}", file=sys.stderr)
                sys.exit(1)

    targets = args.inputs if args.inputs else ["."]
    files_to_process = discover_files(targets, recursive=args.recursive)

    if not files_to_process:
        print(f"\n[make_bengali_audio] No convertible text or markdown files (.txt, .md) found in: {targets}")
        print("Tip: Use -r for recursive search, or specify file paths directly.\n")
        sys.exit(0)

    print(f"\n[make_bengali_audio] Found {len(files_to_process)} file(s) to convert:")
    for idx, f in enumerate(files_to_process, 1):
        print(f"  {idx}. {f}")
    print()

    # Pre-ensure session so Colab VM is warm before batch processing
    try:
        client.ensure_session()
    except Exception as e:
        print(f"[make_bengali_audio Error] Failed to provision Colab session: {e}", file=sys.stderr)
        sys.exit(1)

    success_count = 0
    start_all = time.time()

    for idx, input_file in enumerate(files_to_process, 1):
        # Determine output file path
        if args.output and len(files_to_process) == 1:
            out_file = pathlib.Path(args.output).resolve()
        elif args.output and pathlib.Path(args.output).is_dir():
            out_dir = pathlib.Path(args.output).resolve()
            out_file = out_dir / f"{input_file.stem}.{args.format}"
        else:
            # Default: place alongside original file with .opus extension
            out_file = input_file.parent / f"{input_file.stem}.{args.format}"

        print(f"\n[{idx}/{len(files_to_process)}] Processing: {input_file.name} -> {out_file.name}")

        try:
            content = input_file.read_text(encoding="utf-8", errors="replace")
            # For the last file, apply stop_session_after if requested
            is_last = (idx == len(files_to_process))
            stop_colab = args.stop_after if is_last else False

            ok = process_single_text(
                client=client,
                text=content,
                output_path=out_file,
                speaker=args.speaker,
                style=args.style,
                temperature=args.temperature,
                pause_duration=args.pause,
                chunk_size=args.chunk_size,
                stop_session_after=stop_colab,
            )
            if ok:
                success_count += 1
        except HuggingFaceAccessError as hf_err:
            print(str(hf_err), file=sys.stderr)
            sys.exit(2)
        except ColabBengaliTTSError as err:
            print(f"  [!] Failed to synthesize {input_file.name}: {err}", file=sys.stderr)
        except Exception as e:
            print(f"  [!] Unexpected error on {input_file.name}: {e}", file=sys.stderr)

    total_time = round(time.time() - start_all, 1)
    print(f"\n=======================================================")
    print(f"✔ Completed: {success_count}/{len(files_to_process)} file(s) converted successfully in {total_time}s.")
    if not args.stop_after:
        print(f"ℹ Colab session '{args.session}' remains warm for instant future runs.")
        print(f"  (Run 'make_bengali_audio --stop' when you wish to release the VM).")
    print(f"=======================================================\n")


if __name__ == "__main__":
    main()
