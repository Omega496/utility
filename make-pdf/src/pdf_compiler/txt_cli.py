"""Command-line interface for txt_to_pdf."""

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from pdf_compiler.text_compiler import txt_to_pdf

__version__ = "0.1.0"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="txt_to_pdf",
        description="Convert a plain text file (.txt) to a clean Google Docs formatted PDF.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  txt_to_pdf notes.txt                   # Compiles notes.txt into notes.pdf
  txt_to_pdf notes.txt document.pdf      # Compiles notes.txt into document.pdf
  txt_to_pdf notes.txt -o document.pdf   # With explicit output flag
  txt_to_pdf ./docs/log.txt              # Compiles into ./docs/log.pdf
  txt_to_pdf notes.txt --no-page-numbers # Suppress footer page numbering
""",
    )

    parser.add_argument(
        "input_file",
        type=str,
        help="Path to the input text file (.txt)",
    )

    parser.add_argument(
        "output_pdf",
        nargs="?",
        default=None,
        help="Path or filename for the output PDF (defaults to same name as text file with .pdf)",
    )

    parser.add_argument(
        "-o",
        "--output",
        dest="flag_output",
        type=str,
        default=None,
        help="Alternative flag to specify output PDF path",
    )

    parser.add_argument(
        "--no-page-numbers",
        dest="show_page_numbers",
        action="store_false",
        default=True,
        help="Disable automatic page numbering in the footer",
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
        help="Suppress standard output (errors only)",
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    input_path = Path(args.input_file)
    output_target = args.flag_output or args.output_pdf

    try:
        if not input_path.exists():
            print(f"Error: Input file does not exist: '{input_path}'", file=sys.stderr)
            return 1

        if not input_path.is_file():
            print(f"Error: Input path is not a file: '{input_path}'", file=sys.stderr)
            return 1

        if args.verbose and not args.quiet:
            print(f"Reading text file: {input_path.resolve()}")

        result_pdf = txt_to_pdf(
            input_path=input_path,
            output_pdf=output_target,
            show_page_numbers=args.show_page_numbers,
        )

        if not args.quiet:
            print(f"PDF created: {result_pdf.resolve()}")

        return 0

    except Exception as err:
        print(f"Error: {err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
