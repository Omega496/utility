"""Command line interface for clean."""

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from clean import __version__
from clean.cleaner import (
    CleanMode,
    RenameResult,
    clean_directory,
    clean_file,
    split_filename,
)


class Colors:
    GREEN = "\033[92m"
    BLUE = "\033[94m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    CYAN = "\033[96m"
    RESET = "\033[0m"


def format_message(msg: str, color: str, use_color: bool) -> str:
    if not use_color:
        return msg
    return f"{color}{msg}{Colors.RESET}"


def print_result(result: RenameResult, use_color: bool, verbose: bool, dry_run: bool) -> None:
    prefix = "[DRY RUN] " if dry_run else ""
    kind = f"[{result.item_type.upper()}] " if result.item_type == "directory" else ""

    if result.status == "renamed":
        tag = format_message("✔ RENAMED", Colors.GREEN + Colors.BOLD, use_color)
        src = result.source.name
        dst = result.target.name
        print(f"  {prefix}{tag} {kind}'{src}' -> '{dst}'")
    elif result.status == "collision_resolved":
        tag = format_message("⚠ RENAMED (collision)", Colors.YELLOW + Colors.BOLD, use_color)
        src = result.source.name
        dst = result.target.name
        print(f"  {prefix}{tag} {kind}'{src}' -> '{dst}'")
    elif result.status == "already_clean":
        if verbose:
            tag = format_message("ℹ CLEAN", Colors.BLUE, use_color)
            print(f"  {prefix}{tag} {kind}'{result.source.name}' is already compliant")
    elif result.status == "error":
        tag = format_message("✖ ERROR", Colors.RED + Colors.BOLD, use_color)
        print(f"  {prefix}{tag} {kind}'{result.source.name}': {result.error_message}")


def main(argv: Optional[List[str]] = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    # Auto-detect default mode based on command invoked:
    # Default is KAGGLE. If command contains 'sync' or 'mobile', default to SYNC.
    invoked_name = Path(sys.argv[0]).name.lower()
    default_mode = (
        CleanMode.SYNC
        if ("sync" in invoked_name or "mobile" in invoked_name)
        else CleanMode.KAGGLE
    )

    parser = argparse.ArgumentParser(
        prog="clean",
        description="Unified CLI tool to sanitize file and folder names for Kaggle uploads and Mobile/Syncthing sharing.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Modes:
  Kaggle Mode (Default):
    Strict POSIX Kaggle compliance: replaces spaces, brackets, parentheses, colons,
    and special characters with underscores, strips accents and internal dots.

  Mobile / Sync Mode (-s / -m / --sync):
    Safe cross-platform cleaning for Android & Windows: fixes colons, quotes, newlines,
    pipes, trailing spaces, and updates markdown links while keeping readable spaces.

Examples:
  clean                              # Clean current directory for Kaggle upload (Default)
  clean -n                           # Dry-run preview in current directory
  clean -r                           # Clean current directory and subdirectories recursively
  clean -s                           # Clean current directory for Mobile / Syncthing
  clean -s -r                        # Clean recursively for Mobile / Syncthing
  clean path/to/folder               # Clean a specific folder
""",
    )

    parser.add_argument(
        "paths",
        nargs="*",
        default=["."],
        help="One or more files or directories to clean (defaults to current directory '.').",
    )

    # Mode selection
    mode_group = parser.add_argument_group("Mode Options")
    mode_group.add_argument(
        "-k",
        "--kaggle",
        action="store_true",
        help="Run in Kaggle mode (strict POSIX: replaces spaces with underscores, strips accents).",
    )
    mode_group.add_argument(
        "-s",
        "-m",
        "--sync",
        "--mobile",
        action="store_true",
        help="Run in Mobile/Syncthing mode (preserves spaces, fixes Android forbidden characters).",
    )
    mode_group.add_argument(
        "--mode",
        choices=["sync", "kaggle"],
        default=None,
        help="Explicitly choose cleaning mode ('sync' or 'kaggle').",
    )

    # Behavior
    parser.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        help="Preview changes without renaming any files or folders.",
    )
    parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="Recursively process subdirectories (default: false, only current directory).",
    )
    parser.add_argument(
        "-e",
        "--ext",
        help="Comma-separated list of file extensions to include (e.g. 'pdf,txt,md,mp3,opus,wav').",
    )
    parser.add_argument(
        "--no-dirs",
        action="store_true",
        help="Only clean files; do not rename directories.",
    )
    parser.add_argument(
        "-l",
        "--lower",
        action="store_true",
        help="Convert entire filename to lowercase (Kaggle mode).",
    )
    parser.add_argument(
        "--sep",
        default="_",
        help="Replacement character for Kaggle mode (default: '_').",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show verbose output including already-compliant files.",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable ANSI colors in output.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    args = parser.parse_args(argv)

    # Determine mode
    if args.kaggle:
        mode = CleanMode.KAGGLE
    elif args.sync:
        mode = CleanMode.SYNC
    elif args.mode:
        mode = CleanMode(args.mode)
    else:
        mode = default_mode

    use_color = not args.no_color and sys.stdout.isatty()

    # Parse extensions
    extensions = None
    if args.ext:
        extensions = {ext.strip() for ext in args.ext.split(",") if ext.strip()}

    mode_label = "Kaggle Compliance" if mode == CleanMode.KAGGLE else "Mobile / Syncthing"
    scope_label = "Recursive" if args.recursive else "Current Directory Only"
    dry_label = " [DRY RUN]" if args.dry_run else ""

    header = f"Clean v{__version__} | Mode: {mode_label} | Scope: {scope_label}{dry_label}"
    print(format_message(header, Colors.CYAN + Colors.BOLD, use_color))
    print(format_message("-" * len(header), Colors.DIM, use_color))

    all_results: List[RenameResult] = []

    for path_str in args.paths:
        p = Path(path_str)
        if not p.exists():
            all_results.append(
                RenameResult(
                    source=p,
                    target=p,
                    item_type="file",
                    status="error",
                    error_message="Path does not exist",
                )
            )
            continue

        if p.is_dir():
            res = clean_directory(
                p,
                mode=mode,
                extensions=extensions,
                recursive=args.recursive,
                dry_run=args.dry_run,
                separator=args.sep,
                lowercase=args.lower,
                clean_dirs=not args.no_dirs,
            )
            all_results.extend(res)
        else:
            # Single file
            if extensions is not None:
                _, ext = split_filename(p.name)
                norm_exts = {e.lower() if e.startswith(".") else f".{e.lower()}" for e in extensions}
                if ext not in norm_exts:
                    continue

            res_single = clean_file(
                p,
                mode=mode,
                dry_run=args.dry_run,
                separator=args.sep,
                lowercase=args.lower,
            )
            all_results.append(res_single)

    renamed_count = sum(1 for r in all_results if r.status in ("renamed", "collision_resolved"))
    clean_count = sum(1 for r in all_results if r.status == "already_clean")
    error_count = sum(1 for r in all_results if r.status == "error")

    # Print results
    for r in all_results:
        print_result(r, use_color=use_color, verbose=args.verbose, dry_run=args.dry_run)

    # Print summary
    prefix = "[DRY RUN] " if args.dry_run else ""
    if all_results:
        summary = (
            f"\n{prefix}Summary: "
            f"{renamed_count} renamed, "
            f"{clean_count} already compliant, "
            f"{error_count} errors."
        )
        if renamed_count > 0:
            print(format_message(summary, Colors.BOLD, use_color))
        else:
            print(format_message(summary, Colors.DIM, use_color))
    else:
        print(f"  {prefix}No files or folders found matching criteria.")

    return 1 if error_count > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
