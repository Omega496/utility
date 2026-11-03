"""Command-line interface for md_to_pdf."""

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from pdf_compiler.text_compiler import md_to_pdf

__version__ = "0.1.0"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="md_to_pdf",
        description="Convert a Markdown file (.md) to a clean Google Docs formatted PDF.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  md_to_pdf README.md                   # Compiles README.md into README.pdf
  md_to_pdf document.md result.pdf      # Compiles document.md into result.pdf
  md_to_pdf doc.md -o output.pdf        # With explicit output flag
  md_to_pdf ./docs/guide.md             # Compiles into ./docs/guide.pdf
  md_to_pdf doc.md --no-page-numbers    # Suppress footer page numbering
""",
    )

    parser.add_argument(
        "input_file",
        type=str,
        help="Path to the input Markdown file (.md)",
    )

    parser.add_argument(
        "output_pdf",
        nargs="?",
        default=None,
        help="Path or filename for the output PDF (defaults to same name as markdown file with .pdf)",
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
            print(f"Reading markdown file: {input_path.resolve()}")

        result_pdf = md_to_pdf(
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
