#!/usr/bin/env python3
"""
Batch Audio to Opus Converter (24 kHz, 24 kbps)
Safely and concurrently converts audio files in a specified folder to high-efficiency Opus speech audio.
"""

import argparse
import os
import shutil
import struct
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional, Tuple

SUPPORTED_EXTS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".wma", ".opus"}
DANGEROUS_ROOTS = {"/", "/bin", "/boot", "/dev", "/etc", "/lib", "/lib64", "/proc", "/sys", "/usr", "/var", "/run"}


def get_audio_info(filepath: Path) -> Dict[str, any]:
    """Inspect and extract detailed audio metadata including Opus header rate and bitrate."""
    info = {
        "codec": filepath.suffix.lstrip(".").lower(),
        "sample_rate": None,
        "channels": None,
        "bitrate": None,
        "duration": None,
        "size": filepath.stat().st_size if filepath.exists() else 0,
    }

    # For Opus files, extract the original recorded input sample rate from RFC 7845 OpusHead
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

    # Use ffprobe for duration and fallback stream info
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

    # Calculate precise average bitrate if duration is available
    if info["duration"] and info["duration"] > 0 and info["size"] > 0:
        info["bitrate"] = (info["size"] * 8) / (info["duration"] * 1000.0)

    return info


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


def convert_file(
    src_file: Path,
    out_dir: Optional[Path],
    in_place: bool,
    target_bitrate: str = "24k",
    target_sr: int = 24000,
) -> Dict[str, any]:
    """Convert a single audio file to 24kHz/24k Opus."""
    original_size = src_file.stat().st_size
    target_br_num = float(target_bitrate.rstrip("kK"))

    # If it's already an Opus file and already close to or under target bitrate, skip it
    if src_file.suffix.lower() == ".opus":
        meta = get_audio_info(src_file)
        br = meta.get("bitrate")
        sr = meta.get("sample_rate")
        if br is not None and br <= (target_br_num * 1.25) and sr == target_sr:
            return {
                "status": "skipped",
                "src": src_file,
                "dest": src_file,
                "orig_size": original_size,
                "new_size": original_size,
                "msg": "Already optimized 24k Opus",
            }

    # Determine destination path
    if in_place:
        dest_file = src_file.with_suffix(".opus")
        # Avoid overwriting directly during conversion
        tmp_dest = src_file.with_name(f".tmp_{src_file.stem}_{int(time.time()*1000)}.opus")
    else:
        dest_file = out_dir / f"{src_file.stem}.opus"
        tmp_dest = out_dir / f".tmp_{src_file.stem}_{int(time.time()*1000)}.opus"

    cmd = [
        "ffmpeg", "-y",
        "-i", str(src_file),
        "-ar", str(target_sr),
        "-ac", "1",
        "-c:a", "libopus",
        "-b:a", target_bitrate,
        "-vbr", "on",
        "-application", "voip",
        str(tmp_dest)
    ]

    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if tmp_dest.exists() and tmp_dest.stat().st_size > 0:
            if in_place and src_file != dest_file:
                # If original was .mp3/.wav, rename tmp to dest and remove old
                tmp_dest.replace(dest_file)
                src_file.unlink(missing_ok=True)
            else:
                tmp_dest.replace(dest_file)
            new_size = dest_file.stat().st_size
            return {
                "status": "success",
                "src": src_file,
                "dest": dest_file,
                "orig_size": original_size,
                "new_size": new_size,
                "msg": "Converted",
            }
        else:
            return {"status": "error", "src": src_file, "dest": None, "orig_size": original_size, "new_size": 0, "msg": "Empty output"}
    except Exception as e:
        tmp_dest.unlink(missing_ok=True)
        return {"status": "error", "src": src_file, "dest": None, "orig_size": original_size, "new_size": 0, "msg": str(e)}


def format_bytes(n: float) -> str:
    """Format bytes to human readable format."""
    for unit in ["B", "KB", "MB", "GB"]:
        if abs(n) < 1024.0:
            return f"{n:3.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} TB"


def main():
    parser = argparse.ArgumentParser(
        description="Safely inspect or batch-convert audio files to 24 kHz, 24 kbps Opus.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("target", nargs="?", default=".", help="Target folder containing audio files, or single file to inspect (default: current directory).")
    parser.add_argument("-i", "--info", action="store_true", help="Inspect and display detailed audio specs (codec, header sample rate, bitrate, duration).")
    parser.add_argument("-o", "--output", help="Output directory (default: <dir>/converted_opus, or in-place with --in-place).")
    parser.add_argument("--in-place", action="store_true", help="Replace original files directly with .opus (destructive).")
    parser.add_argument("-r", "--recursive", action="store_true", help="Search subdirectories recursively.")
    parser.add_argument("-j", "--threads", type=int, default=os.cpu_count() or 4, help="Number of concurrent ffmpeg workers (default: all CPU cores).")
    parser.add_argument("-b", "--bitrate", default="24k", help="Bitrate for Opus encoding (default: 24k).")

    args = parser.parse_args()

    target_path = Path(args.target).resolve()

    # Handle inspection mode (-i / --info) or single-file input
    if args.info or target_path.is_file():
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
                if f.is_file() and f.suffix.lower() in SUPPORTED_EXTS and not f.name.startswith(".tmp_"):
                    meta = get_audio_info(f)
                    sr_str = f"{meta['sample_rate']} Hz" if meta["sample_rate"] else "N/A"
                    br_str = f"{meta['bitrate']:.1f}k" if meta["bitrate"] else "N/A"
                    name_str = f.name if len(f.name) <= 30 else f.name[:27] + "..."
                    print(f"{name_str:<32} {meta['codec'].upper():<8} {sr_str:<14} {br_str:<10} {format_bytes(meta['size']):<9}")
            print("=" * 75)
            return

    if not shutil.which("ffmpeg"):
        print("Error: ffmpeg is not installed or not in PATH.", file=sys.stderr)
        sys.exit(1)

    target_dir = target_path

    # Safety Guard: Never allow running on root or system directories
    if str(target_dir) in DANGEROUS_ROOTS or target_dir == Path.home():
        print(f"ERROR: Running on '{target_dir}' is blocked for system safety!", file=sys.stderr)
        print("Please specify a dedicated audio folder (e.g., ~/Music/Audiobooks, ~/Downloads/podcasts).", file=sys.stderr)
        sys.exit(1)

    if not target_dir.exists() or not target_dir.is_dir():
        print(f"Error: Directory '{target_dir}' does not exist.", file=sys.stderr)
        sys.exit(1)

    # Collect files
    pattern = "**/*" if args.recursive else "*"
    files_to_convert: List[Path] = [
        p for p in target_dir.glob(pattern)
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS and not p.name.startswith(".tmp_")
    ]

    if not files_to_convert:
        print(f"No supported audio files ({', '.join(sorted(SUPPORTED_EXTS))}) found in {target_dir}.")
        return

    # Output setup
    out_dir = None
    if not args.in_place:
        out_dir = Path(args.output).resolve() if args.output else target_dir / "converted_opus"
        out_dir.mkdir(parents=True, exist_ok=True)
        # Prevent picking up files from the output dir itself
        files_to_convert = [f for f in files_to_convert if not str(f).startswith(str(out_dir))]

    total_files = len(files_to_convert)
    print("=" * 65)
    print(f" Batch Audio to Opus Converter (24 kHz, {args.bitrate})")
    print("=" * 65)
    print(f" Target Directory : {target_dir}")
    print(f" Files Found      : {total_files}")
    print(f" Mode             : {'IN-PLACE (Replaces originals)' if args.in_place else f'Save to {out_dir}'}")
    print(f" Parallel Threads : {args.threads}")
    print("=" * 65)

    if args.in_place:
        confirm = input("WARNING: --in-place will replace original files with .opus. Proceed? [y/N]: ").strip().lower()
        if confirm != "y":
            print("Aborted by user.")
            return

    start_time = time.time()
    completed_count = 0
    total_orig_bytes = 0
    total_new_bytes = 0
    errors = 0

    with ThreadPoolExecutor(max_workers=args.threads) as executor:
        futures = {
            executor.submit(
                convert_file,
                f,
                out_dir,
                args.in_place,
                args.bitrate,
                24000,
            ): f for f in files_to_convert
        }

        for fut in as_completed(futures):
            res = fut.result()
            completed_count += 1
            total_orig_bytes += res["orig_size"]
            total_new_bytes += res["new_size"]

            pct = (completed_count / total_files) * 100
            elapsed = time.time() - start_time
            rate = completed_count / elapsed if elapsed > 0 else 0
            eta = (total_files - completed_count) / rate if rate > 0 else 0

            snippet = res["src"].name
            if len(snippet) > 35:
                snippet = snippet[:32] + "..."

            status_mark = "OK" if res["status"] in ["success", "skipped"] else "FAIL"
            if res["status"] == "error":
                errors += 1

            sys.stdout.write(
                f"\r[{pct:5.1f}%] [{completed_count:03d}/{total_files:03d}] "
                f"({status_mark}) {snippet:<35} | ETA: {eta:3.0f}s"
            )
            sys.stdout.flush()

    total_time = time.time() - start_time
    saved_bytes = total_orig_bytes - total_new_bytes
    saved_pct = (saved_bytes / total_orig_bytes * 100) if total_orig_bytes > 0 else 0

    print("\n\n" + "=" * 65)
    print(" CONVERSION SUMMARY")
    print("=" * 65)
    print(f" Total Processed  : {completed_count} files in {total_time:.1f}s ({completed_count/total_time:.1f} files/sec)")
    print(f" Errors           : {errors}")
    print(f" Original Size    : {format_bytes(total_orig_bytes)}")
    print(f" New Size         : {format_bytes(total_new_bytes)}")
    print(f" Space Saved      : {format_bytes(saved_bytes)} ({saved_pct:.1f}% reduction)")
    if out_dir and not args.in_place:
        print(f" Destination     : {out_dir}")
    print("=" * 65)


if __name__ == "__main__":
    main()
