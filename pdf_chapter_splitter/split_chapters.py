#!/home/heathcliff/Documents/utility/.venv/bin/python
"""
split_by_page_ranges.py

Split a PDF into chapters based on:
  Mode A: Automatic PDF Bookmarks / Table of Contents (if available)
  Mode B: User-defined chapter names and page ranges [(start, end), ...]

Features:
  - AUTO BOOK-NAME FROM PATH: If BOOK_NAME is empty (""), it is automatically
    extracted from the PDF file's name (e.g. '/path/to/Deep Learning.pdf' -> 'deep_learning').
  - AUTO-BOOKMARKS: Automatically extracts chapter names and page ranges from
    the PDF outline when enabled.
  - PAGE_OFFSET: Compensates when the PDF viewer page is ahead of printed book
    numbers (used in manual mode).
  - Kaggle dataset filename sanitization:
      * Lowercase ASCII (a-z, 0-9)
      * Underscore (_) or hyphen (-) delimiters
      * Eliminates invalid characters, spaces, and duplicate delimiters.
  - Optional chapter number and book name prefixes.
"""

import os
import re
import sys
import unicodedata
from argparse import ArgumentParser
from pathlib import Path
from typing import List, Optional, Tuple

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None
import pymupdf

def kaggle_slugify(text: str, delimiter: str = "_") -> str:
    """
    Sanitizes text to meet Kaggle dataset file naming standards:
      - Normalizes unicode characters to ASCII
      - Converts to lowercase
      - Replaces spaces and non-alphanumeric characters with delimiter
      - Collapses multiple delimiters into one
      - Strips leading and trailing delimiters
    """
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_text = ascii_text.lower()
    clean = re.sub(r"[^a-z0-9]+", delimiter, ascii_text)
    clean = re.sub(rf"{re.escape(delimiter)}+", delimiter, clean)
    return clean.strip(delimiter)


def build_kaggle_filename(
    chapter_index: int,
    chapter_name: str,
    book_name: str = "",
    add_chapter_number: bool = True,
    add_book_name: bool = True,
    zero_pad: bool = True,
    total_chapters: int = 10,
    delimiter: str = "_",
) -> str:
    """Constructs a clean, Kaggle-compliant filename for a chapter PDF."""
    parts = []

    # 1. Book name prefix
    if add_book_name and book_name.strip():
        clean_book = kaggle_slugify(book_name, delimiter=delimiter)
        if clean_book:
            parts.append(clean_book)

    # 2. Chapter number prefix: 'chapter_01' or 'chapter_1'
    if add_chapter_number:
        pad_width = max(2, len(str(total_chapters))) if zero_pad else 1
        ch_str = f"chapter{delimiter}{chapter_index:0{pad_width}d}"
        parts.append(ch_str)

    # 3. Chapter title slug
    clean_title = kaggle_slugify(chapter_name, delimiter=delimiter)
    if clean_title:
        parts.append(clean_title)

    base_name = delimiter.join(parts) if parts else f"chapter{delimiter}{chapter_index}"
    return f"{base_name}.pdf"


def extract_chapters_from_bookmarks(
    doc,
    bookmark_level: int = 1
) -> Tuple[Optional[List[str]], Optional[List[Tuple[int, int]]]]:
    """
    Extracts chapter titles and page ranges directly from PDF bookmarks (TOC).
    Bookmark pages from PyMuPDF are 1-based exact viewer pages.
    """
    toc = doc.get_toc()  # Format: [[level, title, page_number], ...]
    if not toc:
        return None, None

    entries = [entry for entry in toc if entry[0] == bookmark_level]
    if not entries:
        return None, None

    chapter_names = []
    chapter_ranges = []
    total_pages = len(doc)

    for i, (lvl, title, start_page) in enumerate(entries):
        if i + 1 < len(entries):
            next_start = entries[i + 1][2]
            end_page = max(start_page, next_start - 1)
        else:
            end_page = total_pages

        chapter_names.append(title.strip())
        chapter_ranges.append((start_page, end_page))

    return chapter_names, chapter_ranges


def normalize_ranges(
    chapter_ranges: List,
    chapter_names: List[str],
    total_pages: int,
    page_offset: int,
) -> List[Tuple[int, int]]:
    """
    Normalizes chapter_ranges so it accepts BOTH:
      1. List of (start, end) tuples: [(1, 10), (11, 25), ...]
      2. Simple list of start page numbers: [1, 11, 26, 51, ...]
         Where each chapter ends right before the next starts, and the
         final chapter ends at the end of the book.
    """
    if not chapter_ranges:
        return []

    # If already a list of tuples or lists: [(start, end), ...]
    if isinstance(chapter_ranges[0], (tuple, list)):
        return [(int(r[0]), int(r[1])) for r in chapter_ranges]

    # Otherwise, it is a list of starting page integers: [3, 21, 43, ...]
    start_pages = [int(p) for p in chapter_ranges]
    normalized = []
    num_names = len(chapter_names)
    max_printed_page = total_pages - page_offset

    for i in range(num_names):
        if i >= len(start_pages):
            break
        start = start_pages[i]
        # Next chapter's start page minus 1, or end of the document
        if i + 1 < len(start_pages):
            end = max(start, start_pages[i + 1] - 1)
        else:
            end = max_printed_page
        normalized.append((start, end))

    return normalized


def split_pdf_by_chapters(
    pdf_path: str,
    chapter_names: Optional[List[str]] = None,
    chapter_ranges: Optional[List[Tuple[int, int]]] = None,
    book_name: str = "",
    output_dir: str = "split_chapters",
    use_bookmarks: bool = False,
    bookmark_level: int = 1,
    page_offset: int = 0,
    add_chapter_number: bool = True,
    add_book_name: bool = True,
    zero_pad: bool = True,
    delimiter: str = "_",
):
    """
    Splits a PDF into chapters.
    If book_name is empty, it automatically extracts the book name from the PDF's file name!
    """
    if fitz is None:
        print(
            "Error: 'PyMuPDF' is not installed. Please install it using:\n    pip install pymupdf",
            file=sys.stderr,
        )
        return

    pdf_file = Path(pdf_path).resolve()
    if not pdf_file.exists():
        print(f"Error: PDF file not found at '{pdf_file}'", file=sys.stderr)
        return

    # AUTO-DETECT BOOK NAME: If no book name is given, use the PDF filename (without .pdf)
    effective_book_name = book_name.strip() if book_name.strip() else pdf_file.stem

    try:
        doc = fitz.open(str(pdf_file))
    except Exception as e:
        print(f"Error opening PDF: {e}", file=sys.stderr)
        return

    total_pages = len(doc)
    mode_used = "Manual Ranges"

    # --- MODE A: Automatic Bookmark Detection ---
    if use_bookmarks:
        auto_names, auto_ranges = extract_chapters_from_bookmarks(doc, bookmark_level=bookmark_level)
        if auto_names and auto_ranges:
            chapter_names = auto_names
            chapter_ranges = auto_ranges
            page_offset = 0  # Bookmarks already point directly to exact viewer pages
            mode_used = f"Auto-detected Bookmarks (Level {bookmark_level})"
        else:
            print("⚠️  No bookmarks found at requested level. Falling back to manual lists...")

    # Validate inputs
    if not chapter_names or not chapter_ranges:
        print("Error: No chapter names or page ranges provided.", file=sys.stderr)
        doc.close()
        return

    # Normalize ranges in case user passed [start1, start2, start3, ...]
    chapter_ranges = normalize_ranges(
        chapter_ranges=chapter_ranges,
        chapter_names=chapter_names,
        total_pages=total_pages,
        page_offset=page_offset,
    )

    if len(chapter_names) != len(chapter_ranges):
        print(
            f"Error: Length mismatch!\n"
            f"  - chapter_names has {len(chapter_names)} items\n"
            f"  - chapter_ranges has {len(chapter_ranges)} items",
            file=sys.stderr,
        )
        doc.close()
        return

    out_dir = Path(output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    total_chapters = len(chapter_names)

    print("\n" + "=" * 70)
    print(f"Source PDF File  : {pdf_file}")
    if add_book_name:
        print(f"Book Name Used   : {effective_book_name}")
    print(f"Total Pages      : {total_pages}")
    print(f"Mode             : {mode_used}")
    print(f"Output Directory : {out_dir}")
    print(f"Total Chapters   : {total_chapters}")
    if page_offset != 0:
        sign = "+" if page_offset > 0 else ""
        print(f"Page Offset      : {sign}{page_offset} (Viewer page = Input page {sign}{page_offset})")
    print("=" * 70)

    success_count = 0

    for idx, (title, (start_page, end_page)) in enumerate(
        zip(chapter_names, chapter_ranges), start=1
    ):
        actual_start = start_page + page_offset
        actual_end = end_page + page_offset

        # Bounds validation
        if not (1 <= actual_start <= total_pages):
            print(
                f"⚠️  [{idx:02d}] Skipped '{title}': Adjusted start page {actual_start} "
                f"is out of bounds (1–{total_pages})."
            )
            continue
        if not (1 <= actual_end <= total_pages):
            print(
                f"⚠️  [{idx:02d}] Skipped '{title}': Adjusted end page {actual_end} "
                f"is out of bounds (1–{total_pages})."
            )
            continue
        if actual_start > actual_end:
            print(f"⚠️  [{idx:02d}] Skipped '{title}': Start page ({actual_start}) > End page ({actual_end}).")
            continue

        # PyMuPDF 0-based page slice
        from_page = actual_start - 1
        to_page = actual_end - 1

        # Build Kaggle-compliant filename using effective_book_name
        filename = build_kaggle_filename(
            chapter_index=idx,
            chapter_name=title,
            book_name=effective_book_name,
            add_chapter_number=add_chapter_number,
            add_book_name=add_book_name,
            zero_pad=zero_pad,
            total_chapters=total_chapters,
            delimiter=delimiter,
        )

        out_path = out_dir / filename

        # Create new PDF slice
        chapter_doc = fitz.open()
        chapter_doc.insert_pdf(doc, from_page=from_page, to_page=to_page)
        chapter_doc.save(str(out_path))
        chapter_doc.close()

        page_count = actual_end - actual_start + 1
        print(f"✓ [{idx:02d}] {filename}")
        if page_offset != 0:
            print(f"       └── Input: {start_page}–{end_page}  ➔  Actual PDF: {actual_start}–{actual_end} ({page_count} pages)")
        else:
            print(f"       └── Actual PDF Pages: {actual_start}–{actual_end} ({page_count} pages)")
        success_count += 1

    doc.close()
    print("=" * 70)
    print(f"Completed: {success_count}/{total_chapters} chapters extracted successfully.\n")


# ===========================================================================
# USER CONFIGURATION SECTION
# ===========================================================================

# 1. BOOK PDF PATH:
#    Provide the path (absolute or relative) to your PDF file.
#    Examples:
#      PDF_PATH = "my_book.pdf"
#      PDF_PATH = "/home/heathcliff/Downloads/Deep Learning by Ian Goodfellow.pdf"
PDF_PATH = "/home/heathcliff/Documents/utility/pdf_chapter_splitter/Introduction to Gravitational Lensing  With Python Examples (Massimo Meneghetti) (z-library.sk, 1lib.sk, z-lib.sk).pdf"

# 2. BOOK NAME (Optional):
#    Leave this empty ("") to AUTOMATICALLY detect the book name from the PDF's filename!
#    Only set this if you want to explicitly override the name.
BOOK_NAME = ""

# 3. Output Directory
OUTPUT_DIR = "split_chapters"

# 4. AUTOMATIC BOOKMARK SPLITTING:
#    Set to True if your PDF has bookmarks (outlines) to split automatically!
USE_BOOKMARKS = False
BOOKMARK_LEVEL = 1    # 1 = Top-level chapters, 2 = Include sub-sections

# 5. PAGE OFFSET (Only used in manual mode):
#    Set this if your PDF viewer page number is ahead of the printed book page number.
#    (e.g., if printed page 1 starts on PDF viewer page 11, set PAGE_OFFSET = 10)
PAGE_OFFSET = 11

# 6. Manual Chapter Names (used if USE_BOOKMARKS = False)
DEFAULT_CHAPTERS = [
    "A Brief History of Gravitational Lensing",  #[cite: 1]
    "Deflection of Light",  #[cite: 1]
    "The General Lens",  #[cite: 1]
    "Microlenses",  #[cite: 2]
    "Extended Lenses",  #[cite: 3]
    "Lensing by Galaxies and Clusters",  #[cite: 3]
    "Lensing by Large-Scale Structure",  #[cite: 4]
    "Python Mini-Tutorial",  #[cite: 5]
    "Cosmology Primer",  #[cite: 5]
]

# 7. Manual Chapter Page Ranges [(start, end), ...] (used if USE_BOOKMARKS = False)
#    PAGE_OFFSET is added automatically to each range.
CHAPTER_RANGES = [3, 21, 43, 103, 179, 255, 331, 371, 381]

# 8. Customization Flags (Kaggle Dataset Formatting)
ADD_CHAPTER_NUMBER = True       # Adds 'chapter_<num>_'
ADD_BOOK_NAME = True            # Adds '<book_name>_'
ZERO_PAD_CHAPTER_NUMBER = True  # True: 'chapter_01', False: 'chapter_1'
DELIMITER = "_"                 # Kaggle separator: '_' or '-'


def main():
    parser = ArgumentParser(description="Split PDF into chapters formatted for Kaggle datasets.")
    parser.add_argument("--pdf", type=str, default=PDF_PATH, help="Full path to input PDF")
    parser.add_argument("--book-name", type=str, default=BOOK_NAME, help="Optional book name override (leave blank to auto-detect from path)")
    parser.add_argument("--out", type=str, default=OUTPUT_DIR, help="Output directory")
    parser.add_argument("--auto-bookmarks", action="store_true", help="Auto-detect chapters from bookmarks")
    parser.add_argument("--bookmark-level", type=int, default=BOOKMARK_LEVEL, help="Bookmark outline level (default: 1)")
    parser.add_argument("--offset", type=int, default=PAGE_OFFSET, help="Page offset (viewer page - printed page)")
    parser.add_argument("--no-ch-num", action="store_true", help="Disable chapter_<number> prefix")
    parser.add_argument("--no-book-name", action="store_true", help="Disable book name prefix")
    parser.add_argument("--hyphen", action="store_true", help="Use '-' instead of '_' as delimiter")

    args = parser.parse_args()

    delimiter = "-" if args.hyphen else DELIMITER
    add_ch_num = False if args.no_ch_num else ADD_CHAPTER_NUMBER
    add_bk_name = False if args.no_book_name else ADD_BOOK_NAME
    use_bm = True if args.auto_bookmarks else USE_BOOKMARKS

    split_pdf_by_chapters(
        pdf_path=args.pdf,
        chapter_names=DEFAULT_CHAPTERS,
        chapter_ranges=CHAPTER_RANGES,
        book_name=args.book_name,
        output_dir=args.out,
        use_bookmarks=use_bm,
        bookmark_level=args.bookmark_level,
        page_offset=args.offset,
        add_chapter_number=add_ch_num,
        add_book_name=add_bk_name,
        zero_pad=ZERO_PAD_CHAPTER_NUMBER,
        delimiter=delimiter,
    )


if __name__ == "__main__":
    main()
