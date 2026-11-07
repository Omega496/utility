#!/usr/bin/env python3
"""
make_opus: High-efficiency Universal Audio & Google Docs TTS to Opus Converter
Converts any audio file or Google Docs TTS response (.txt) to 24 kHz, 24 kbps Opus.

Supported Inputs:
- Any audio format (.mp3, .wav, .m4a, .aac, .flac, .ogg, .wma, .opus, .webm, etc.)
- Google Docs TTS network responses (.txt containing generate_tts_response)

Usage:
  make_opus <file>                  # Convert a single file (audio or Google Docs .txt)
  make_opus .                       # Convert all files in the current folder
  make_opus -r                      # Convert all files in current folder and subfolders
  make_opus -r <folder>             # Convert all files in target folder and subfolders
  make_opus -i <file_or_dir>        # Inspect audio format, sample rate, bitrate
  txt-to-opus .                     # Alias for converting Google Docs .txt responses
"""

import argparse
import base64
import json
import os
import shutil
import struct
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional, Tuple

SUPPORTED_AUDIO_EXTS = {
    ".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg",
    ".wma", ".opus", ".webm", ".m4b", ".oga", ".aiff"
}

DANGEROUS_ROOTS = {"/", "/bin", "/boot", "/dev", "/etc", "/lib", "/lib64", "/proc", "/sys", "/usr", "/var", "/run"}


def is_gdocs_tts_txt(path: Path) -> bool:
    """Check if a .txt file is a Google Docs TTS network response."""
    if not path.is_file() or path.suffix.lower() != ".txt":
        return False
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            chunk = f.read(512).strip()
        if chunk.startswith(")]}'"):
            chunk = chunk[4:].strip()
        return "generate_tts_response" in chunk
    except Exception:
        return False


def extract_gdocs_audio_bytes(path: Path) -> Optional[bytes]:
    """Extract decoded audio bytes from a Google Docs TTS response (.txt)."""
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read().strip()
        if content.startswith(")]}'"):
            content = content[4:].strip()
        data = json.loads(content)
        if isinstance(data, list) and len(data) >= 3 and data[0] == "generate_tts_response":
            b64_audio = data[2]
            return base64.b64decode(b64_audio)
    except Exception:
        pass
    return None


def get_audio_info(filepath: Path) -> Dict[str, any]:
    """Inspect and extract audio metadata including Opus header rate and bitrate."""
    info = {
        "codec": filepath.suffix.lstrip(".").lower(),
        "sample_rate": None,
        "channels": None,
        "bitrate": None,
        "duration": None,
        "size": filepath.stat().st_size if filepath.exists() else 0,
    }

    # For Opus files, extract original sample rate from RFC 7845 OpusHead header
    if filepath.suffix.lower() == ".opus":
        try:
            with open(filepath, "rb") as f:
                header_bytes = f.read(128)
            idx = header_bytes.find(b"OpusHead")
            if idx != -1:
                version, channels, preskip, orig_sr = struct.unpack("<BBHI", header_bytes[idx+8:idx+8+8])
                info["codec"] = "opus"
                info["channels"] = channels
                info["sample_rate"] = orig_sr
        except Exception:
            pass

    # Use ffprobe for duration and stream info
    try:
        res = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "stream=codec_name,sample_rate,channels:format=duration,bit_rate",
                "-of", "default=noprint_wrappers=1",
                str(filepath)
            ],
            capture_output=True,
            text=True,
        )
        for line in res.stdout.splitlines():
            k, _, v = line.partition("=")
            v = v.strip()
            if k == "codec_name" and info["codec"] != "opus":
                info["codec"] = v
            elif k == "sample_rate" and info["sample_rate"] is None and v.isdigit():
                info["sample_rate"] = int(v)
            elif k == "channels" and info["channels"] is None and v.isdigit():
                info["channels"] = int(v)
            elif k == "duration":
                try:
                    info["duration"] = float(v)
                except ValueError:
                    pass
            elif k == "bit_rate" and v.isdigit():
                info["bitrate"] = float(v) / 1000.0
    except Exception:
        pass

    if info["duration"] and info["duration"] > 0 and info["size"] > 0:
        info["bitrate"] = (info["size"] * 8) / (info["duration"] * 1000.0)

    return info


def format_bytes(n: float) -> str:
    """Format bytes to human readable format."""
    for unit in ["B", "KB", "MB", "GB"]:
        if abs(n) < 1024.0:
            return f"{n:3.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} TB"


def print_audio_info(filepath: Path):
    """Print human-readable audio file specs."""
    if not filepath.exists():
        print(f"Error: File '{filepath}' does not exist.", file=sys.stderr)
        return

    meta = get_audio_info(filepath)
    sr_str = f"{meta['sample_rate']:,} Hz ({meta['sample_rate']/1000:.1f} kHz)" if meta["sample_rate"] else "Unknown"
    ch_str = f"{meta['channels']} ({'Mono' if meta['channels'] == 1 else 'Stereo' if meta['channels'] == 2 else 'Multi-channel'})" if meta["channels"] else "Unknown"
    br_str = f"{meta['bitrate']:.1f} kbps" if meta["bitrate"] else "Unknown"

    if meta["duration"]:
        mins, secs = divmod(int(meta["duration"]), 60)
        dur_str = f"{mins}m {secs:02d}s ({meta['duration']:.2f}s)"
    else:
        dur_str = "Unknown"

    print("=" * 60)
    print(f" Audio File Inspection: {filepath.name}")
    print("=" * 60)
    print(f"  Container / Codec    : {meta['codec'].upper()}")
    print(f"  Original Sample Rate : {sr_str}")
    print(f"  Channels             : {ch_str}")
    print(f"  Average Bitrate      : {br_str}")
    print(f"  Duration             : {dur_str}")
    print(f"  File Size            : {format_bytes(meta['size'])}")
    print(f"  Full Path            : {filepath.resolve()}")
    print("=" * 60)


def convert_single_file(
    src_file: Path,
    out_dir: Optional[Path] = None,
    out_file: Optional[Path] = None,
    bitrate: str = "24k",
    sample_rate: int = 24000,
    delete_source: bool = True,
) -> Dict[str, any]:
    """
    Convert a single audio file or Google Docs TTS response (.txt) to 24kHz/24k Opus.
    """
    original_size = src_file.stat().st_size
    target_br_num = float(bitrate.rstrip("kK"))

    # Determine destination file path
    if out_file:
        dest_file = out_file
    elif out_dir:
        dest_file = out_dir / f"{src_file.stem}.opus"
    else:
        dest_file = src_file.with_suffix(".opus")

    # If source is already .opus and destination would be the same file:
    if src_file.suffix.lower() == ".opus" and src_file.resolve() == dest_file.resolve():
        meta = get_audio_info(src_file)
        br = meta.get("bitrate")
        sr = meta.get("sample_rate")
        if br is not None and br <= (target_br_num * 1.25) and sr == sample_rate:
            return {
                "status": "skipped",
                "src": src_file,
                "dest": dest_file,
                "orig_size": original_size,
                "new_size": original_size,
                "msg": "Already optimized 24k Opus",
            }

    # Safe atomic temporary file
    tmp_dest = dest_file.with_name(f".tmp_{src_file.stem}_{int(time.time() * 1000)}.opus")
    tmp_dest.parent.mkdir(parents=True, exist_ok=True)

    # Branch 1: Google Docs TTS response (.txt)
    if src_file.suffix.lower() == ".txt":
        audio_bytes = extract_gdocs_audio_bytes(src_file)
        if not audio_bytes:
            return {
                "status": "error",
                "src": src_file,
                "dest": None,
                "orig_size": original_size,
                "new_size": 0,
                "msg": "Not a valid Google Docs TTS response (.txt)",
            }

        cmd = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", "pipe:0",
            "-ar", str(sample_rate),
            "-ac", "1",
            "-c:a", "libopus",
            "-b:a", bitrate,
            "-vbr", "on",
            "-application", "voip",
            str(tmp_dest)
        ]

        try:
            proc = subprocess.run(cmd, input=audio_bytes, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            if proc.returncode != 0 or not tmp_dest.exists() or tmp_dest.stat().st_size == 0:
                err_msg = proc.stderr.decode("utf-8", errors="ignore").strip() if proc.stderr else "FFmpeg failed"
                tmp_dest.unlink(missing_ok=True)
                return {"status": "error", "src": src_file, "dest": None, "orig_size": original_size, "new_size": 0, "msg": err_msg}

            tmp_dest.replace(dest_file)
            if delete_source and src_file != dest_file:
                src_file.unlink(missing_ok=True)

            return {
                "status": "success",
                "src": src_file,
                "dest": dest_file,
                "orig_size": original_size,
                "new_size": dest_file.stat().st_size,
                "msg": "Converted (GDocs TTS)",
            }
        except Exception as e:
            tmp_dest.unlink(missing_ok=True)
            return {"status": "error", "src": src_file, "dest": None, "orig_size": original_size, "new_size": 0, "msg": str(e)}

    # Branch 2: Standard Audio File
    else:
        cmd = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", str(src_file),
            "-ar", str(sample_rate),
            "-ac", "1",
            "-c:a", "libopus",
            "-b:a", bitrate,
            "-vbr", "on",
            "-application", "voip",
            str(tmp_dest)
        ]

        try:
            proc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            if proc.returncode != 0 or not tmp_dest.exists() or tmp_dest.stat().st_size == 0:
                err_msg = proc.stderr.decode("utf-8", errors="ignore").strip() if proc.stderr else "FFmpeg failed"
                tmp_dest.unlink(missing_ok=True)
                return {"status": "error", "src": src_file, "dest": None, "orig_size": original_size, "new_size": 0, "msg": err_msg}

            tmp_dest.replace(dest_file)
            if delete_source and src_file != dest_file:
                src_file.unlink(missing_ok=True)

            return {
                "status": "success",
                "src": src_file,
                "dest": dest_file,
                "orig_size": original_size,
                "new_size": dest_file.stat().st_size,
                "msg": "Converted",
            }
        except Exception as e:
            tmp_dest.unlink(missing_ok=True)
            return {"status": "error", "src": src_file, "dest": None, "orig_size": original_size, "new_size": 0, "msg": str(e)}


def collect_target_files(target_path: Path, recursive: bool = False) -> List[Path]:
    """Collect all valid audio files and Google Docs TTS .txt files."""
    if target_path.is_file():
        # Single file
        ext = target_path.suffix.lower()
        if ext in SUPPORTED_AUDIO_EXTS:
            return [target_path]
        if ext == ".txt":
            if is_gdocs_tts_txt(target_path):
                return [target_path]
            else:
                print(f"[Notice] '{target_path.name}' is a plain text file, not a Google Docs TTS response.", file=sys.stderr)
                print("         For plain text/markdown TTS, use 'make_audio <file>'.", file=sys.stderr)
                return []
        print(f"[Warning] Unsupported file format '{ext}' for '{target_path.name}'.", file=sys.stderr)
        return []

    # Directory
    pattern = "**/*" if recursive else "*"
    candidates = []
    for p in sorted(target_path.glob(pattern)):
        if not p.is_file() or p.name.startswith(".tmp_"):
            continue
        ext = p.suffix.lower()
        if ext in SUPPORTED_AUDIO_EXTS:
            candidates.append(p)
        elif ext == ".txt" and is_gdocs_tts_txt(p):
            candidates.append(p)

    return candidates


def main():
    parser = argparse.ArgumentParser(
        prog="make_opus",
        description="Convert any audio file or Google Docs TTS response (.txt) to 24 kHz, 24 kbps Opus.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  make_opus audio.mp3               # Convert single file -> audio.opus
  make_opus chapter_6_i.txt         # Convert Google Docs TTS .txt -> chapter_6_i.opus
  make_opus .                       # Convert all audio & GDocs .txt in current folder
  make_opus -r                      # Convert current folder and all subfolders recursively
  make_opus /path/to/folder -r      # Convert specified folder and subfolders recursively
  make_opus -i file.opus            # Inspect audio specs (sample rate, bitrate, duration)
  txt-to-opus .                     # Convert all Google Docs .txt files in folder
""",
    )
    parser.add_argument(
        "target",
        nargs="?",
        default=".",
        help="Audio file or folder to convert (default: current directory '.').",
    )
    parser.add_argument(
        "-r", "--recursive",
        action="store_true",
        help="Search and convert files in subdirectories recursively.",
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="Output destination file or directory.",
    )
    parser.add_argument(
        "-b", "--bitrate",
        default="24k",
        help="Target Opus bitrate (default: 24k).",
    )
    parser.add_argument(
        "--sr", "--sample-rate",
        type=int,
        default=24000,
        help="Target sample rate in Hz (default: 24000 Hz / 24 kHz).",
    )
    parser.add_argument(
        "-j", "--threads",
        type=int,
        default=os.cpu_count() or 4,
        help="Number of concurrent conversion threads (default: CPU cores).",
    )
    parser.add_argument(
        "-k", "--keep", "--keep-source",
        dest="delete_source",
        action="store_false",
        default=True,
        help="Keep original file after conversion (by default, original files are automatically deleted upon successful conversion).",
    )
    parser.add_argument(
        "--delete-source",
        dest="delete_source",
        action="store_true",
        default=True,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "-i", "--info",
        action="store_true",
        help="Inspect and display detailed audio properties without converting.",
    )

    args = parser.parse_args()

    # Pre-check ffmpeg
    if not shutil.which("ffmpeg"):
        print("Error: 'ffmpeg' is required but not found in PATH.", file=sys.stderr)
        sys.exit(1)

    target_path = Path(args.target).resolve()

    # Safety Guard against dangerous system roots
    if str(target_path) in DANGEROUS_ROOTS or target_path == Path.home():
        print(f"ERROR: Running on '{target_path}' is blocked for system safety!", file=sys.stderr)
        print("Please specify a specific audio directory or file.", file=sys.stderr)
        sys.exit(1)

    # Info inspection mode
    if args.info:
        if target_path.is_file():
            print_audio_info(target_path)
            return
        elif target_path.is_dir():
            print("=" * 75)
            print(f" Directory Audio Inspection: {target_path}")
            print(f"{'Filename':<32} {'Codec':<8} {'Sample Rate':<14} {'Bitrate':<10} {'Size':<9}")
            print("-" * 75)
            pattern = "**/*" if args.recursive else "*"
            for f in sorted(target_path.glob(pattern)):
                if f.is_file() and (f.suffix.lower() in SUPPORTED_AUDIO_EXTS or is_gdocs_tts_txt(f)):
                    meta = get_audio_info(f)
                    sr_str = f"{meta['sample_rate']} Hz" if meta["sample_rate"] else "N/A"
                    br_str = f"{meta['bitrate']:.1f}k" if meta["bitrate"] else "N/A"
                    name_str = f.name if len(f.name) <= 30 else f.name[:27] + "..."
                    print(f"{name_str:<32} {meta['codec'].upper():<8} {sr_str:<14} {br_str:<10} {format_bytes(meta['size']):<9}")
            print("=" * 75)
            return
        else:
            print(f"Error: Target '{target_path}' does not exist.", file=sys.stderr)
            sys.exit(1)

    # Collect files
    if not target_path.exists():
        print(f"Error: File or directory '{target_path}' does not exist.", file=sys.stderr)
        sys.exit(1)

    files_to_convert = collect_target_files(target_path, recursive=args.recursive)
    if not files_to_convert:
        if target_path.is_dir():
            print(f"No audio files or Google Docs TTS .txt files found in '{target_path}'.")
        return

    # Single-file conversion mode
    if target_path.is_file():
        src = files_to_convert[0]
        out_f = Path(args.output).resolve() if args.output and not Path(args.output).is_dir() else None
        out_d = Path(args.output).resolve() if args.output and Path(args.output).is_dir() else None

        print(f"Converting: {src.name} -> 24 kHz, {args.bitrate} Opus ...")
        res = convert_single_file(
            src_file=src,
            out_dir=out_d,
            out_file=out_f,
            bitrate=args.bitrate,
            sample_rate=args.sr,
            delete_source=args.delete_source,
        )
        if res["status"] == "success":
            saved = res["orig_size"] - res["new_size"]
            pct = (saved / res["orig_size"] * 100) if res["orig_size"] > 0 else 0
            print(f"✓ Created: {res['dest'].name} ({format_bytes(res['new_size'])}) [Saved {format_bytes(saved)}, -{pct:.1f}%]")
            if args.delete_source and src.resolve() != res["dest"].resolve():
                print(f"  Deleted original: {src.name}")
        elif res["status"] == "skipped":
            print(f"✓ {src.name} is already an optimized 24k Opus file.")
        else:
            print(f"✗ Failed: {res['msg']}", file=sys.stderr)
            sys.exit(1)
        return

    # Batch conversion mode
    out_dir = Path(args.output).resolve() if args.output else None
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
        # Avoid circular processing
        files_to_convert = [f for f in files_to_convert if not str(f).startswith(str(out_dir))]

    total_files = len(files_to_convert)
    print("=" * 65)
    print(f" make_opus : Universal 24 kHz, {args.bitrate} Opus Converter")
    print("=" * 65)
    print(f" Target Directory : {target_path}")
    print(f" Files Found      : {total_files}")
    print(f" Mode             : {'Recursive' if args.recursive else 'Current Directory'}")
    print(f" Threads          : {args.threads}")
    if out_dir:
        print(f" Output Folder    : {out_dir}")
    print("=" * 65)

    start_time = time.time()
    completed = 0
    total_orig = 0
    total_new = 0
    errors = 0
    skipped = 0

    with ThreadPoolExecutor(max_workers=args.threads) as executor:
        futures = {
            executor.submit(
                convert_single_file,
                f,
                out_dir,
                None,
                args.bitrate,
                args.sr,
                args.delete_source,
            ): f for f in files_to_convert
        }

        for fut in as_completed(futures):
            res = fut.result()
            completed += 1
            total_orig += res["orig_size"]
            total_new += res["new_size"]

            pct = (completed / total_files) * 100
            elapsed = time.time() - start_time
            rate = completed / elapsed if elapsed > 0 else 0
            eta = (total_files - completed) / rate if rate > 0 else 0

            snippet = res["src"].name
            if len(snippet) > 32:
                snippet = snippet[:29] + "..."

            if res["status"] == "success":
                mark = "OK"
            elif res["status"] == "skipped":
                mark = "SKIP"
                skipped += 1
            else:
                mark = "FAIL"
                errors += 1

            sys.stdout.write(
                f"\r[{pct:5.1f}%] [{completed:03d}/{total_files:03d}] "
                f"({mark}) {snippet:<32} | ETA: {eta:3.0f}s"
            )
            sys.stdout.flush()

    total_time = time.time() - start_time
    saved_bytes = total_orig - total_new
    saved_pct = (saved_bytes / total_orig * 100) if total_orig > 0 else 0

    print("\n\n" + "=" * 65)
    print(" SUMMARY")
    print("=" * 65)
    print(f" Total Processed  : {completed} files in {total_time:.1f}s ({completed/total_time:.1f} files/sec)")
    print(f" Converted        : {completed - errors - skipped}")
    print(f" Skipped          : {skipped}")
    print(f" Errors           : {errors}")
    print(f" Original Size    : {format_bytes(total_orig)}")
    print(f" Opus Output Size : {format_bytes(total_new)}")
    print(f" Space Saved      : {format_bytes(saved_bytes)} ({saved_pct:.1f}% reduction)")
    if args.delete_source:
        print(" Originals        : Cleaned up (deleted automatically)")
    else:
        print(" Originals        : Kept (--keep flag)")
    print("=" * 65)


if __name__ == "__main__":
    main()
