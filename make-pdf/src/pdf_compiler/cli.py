"""Command-line interface for pdf-compiler."""

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from pdf_compiler.compiler import (
    SUPPORTED_EXTENSIONS,
    compile_folder,
    compile_images,
    find_image_files,
)

__version__ = "0.1.0"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="image_to_pdf",
        description="Compile images into a single PDF document with smart sorting and clean formatting.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  image_to_pdf "Grade_Cards.pdf"              # Compile images in current folder into Grade_Cards.pdf
  image_to_pdf ./images -o document.pdf       # Compile images from ./images into document.pdf
  image_to_pdf ./images grades.pdf            # Compile ./images into grades.pdf
  image_to_pdf -i ./scans -o report.pdf       # Explicit input and output flags
  image_to_pdf --sort alpha -o sorted.pdf     # Sort alphabetically instead of naturally
  image_to_pdf --quality 85 -o compressed.pdf # Apply compression quality
""",
    )

    parser.add_argument(
        "positional_args",
        nargs="*",
        metavar="PATH",
        help="Input folder/image or output PDF filename (e.g. 'image_to_pdf document.pdf' or 'image_to_pdf ./folder output.pdf')",
    )

    parser.add_argument(
        "-i",
        "--input",
        dest="input_path",
        type=str,
        default=None,
        help="Path to the folder containing images or specific image files (default: current directory)",
    )

    parser.add_argument(
        "-o",
        "--output",
        dest="output_path",
        type=str,
        default=None,
        help="Path or name of the output PDF file (default: output.pdf)",
    )

    parser.add_argument(
        "--sort",
        dest="sort_mode",
        choices=["natural", "alpha", "none"],
        default="natural",
        help="Image sort mode: 'natural' (e.g. page2 before page10), 'alpha' (lexicographical), or 'none' (default: natural)",
    )

    parser.add_argument(
        "--reverse",
        action="store_true",
        help="Reverse image ordering",
    )

    parser.add_argument(
        "--quality",
        type=int,
        default=None,
        help="Compression quality (1-100) for output PDF",
    )

    parser.add_argument(
        "--no-optimize",
        dest="optimize",
        action="store_false",
        default=True,
        help="Disable Pillow PDF stream optimization",
    )

    parser.add_argument(
        "--no-exif",
        dest="auto_rotate",
        action="store_false",
        default=True,
        help="Disable automatic EXIF orientation adjustment",
    )

    parser.add_argument(
        "--skip-corrupted",
        action="store_true",
        help="Skip unreadable or corrupted images instead of halting",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show detailed progress information",
    )

    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress all standard output (errors only)",
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    return parser


def parse_paths(
    positional_args: List[str],
    flag_input: Optional[str],
    flag_output: Optional[str],
) -> tuple[Path, Path]:
    """Resolve input folder/path and output PDF path from flags and positional arguments."""
    input_path = Path(flag_input) if flag_input else None
    output_path = Path(flag_output) if flag_output else None

    if len(positional_args) == 1:
        arg = positional_args[0]
        arg_path = Path(arg)

        if output_path is None and input_path is None:
            # If the single arg ends with .pdf, treat as output
            if arg.lower().endswith(".pdf"):
                output_path = arg_path
                input_path = Path.cwd()
            elif arg_path.is_dir():
                input_path = arg_path
                output_path = Path(f"{arg_path.name or 'output'}.pdf")
            else:
                # User passed something like "my_result" without .pdf extension
                output_path = Path(f"{arg}.pdf")
                input_path = Path.cwd()
        elif input_path is None:
            input_path = arg_path
        elif output_path is None:
            output_path = arg_path

    elif len(positional_args) >= 2:
        if input_path is None:
            input_path = Path(positional_args[0])
        if output_path is None:
            output_path = Path(positional_args[1])

    # Defaults if still unspecified
    if input_path is None:
        input_path = Path.cwd()
    if output_path is None:
        output_path = Path("output.pdf")

    if not output_path.name.lower().endswith(".pdf"):
        output_path = output_path.with_suffix(".pdf")

    return input_path, output_path


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        input_path, output_path = parse_paths(
            positional_args=args.positional_args,
            flag_input=args.input_path,
            flag_output=args.output_path,
        )

        if not input_path.exists():
            print(f"Error: Input path does not exist: '{input_path}'", file=sys.stderr)
            return 1

        if input_path.is_dir():
            image_files = find_image_files(
                folder_path=input_path,
                sort_mode=args.sort_mode,
                reverse=args.reverse,
            )
        elif input_path.is_file():
            image_files = [input_path]
        else:
            print(f"Error: Invalid input path: '{input_path}'", file=sys.stderr)
            return 1

        if not image_files:
            supported = ", ".join(SUPPORTED_EXTENSIONS)
            print(
                f"Error: No images found in '{input_path}'.\nSupported extensions: {supported}",
                file=sys.stderr,
            )
            return 1

        if args.verbose and not args.quiet:
            print(f"Found {len(image_files)} image(s) to compile:")
            for idx, img in enumerate(image_files, 1):
                print(f"  [{idx}/{len(image_files)}] {img.name}")
            print(f"Target PDF: {output_path.resolve()}")

        result = compile_images(
            image_paths=image_files,
            output_pdf=output_path,
            auto_rotate=args.auto_rotate,
            quality=args.quality,
            optimize=args.optimize,
            skip_corrupted=args.skip_corrupted,
        )

        if not args.quiet:
            print(f"PDF created: {result.resolve()}")

        return 0

    except Exception as err:
        print(f"Error: {err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
