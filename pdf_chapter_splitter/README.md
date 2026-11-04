# PDF Chapter Splitter (Kaggle Dataset Ready)

A Python utility for splitting book PDFs into individual chapter files using [PyMuPDF](https://pymupdf.readthedocs.io/). Generates sanitized, sorted, and Kaggle-dataset-compliant filenames automatically.

---

## Features

- **Auto-Bookmark Mode**: Automatically detects chapters and page ranges if the PDF has embedded bookmarks/outlines.
- **Manual Mode**: Specify chapter names and page ranges via simple Python lists.
- **Auto Book Name Detection**: Extracts and formats the book name directly from the PDF file path.
- **Page Offset Handling (`PAGE_OFFSET`)**: Compensates when the PDF viewer page is ahead of printed book numbers (e.g., covers, preface).
- **Kaggle-Compliant Filenames**:
  - Lowercase ASCII (`a-z`, `0-9`).
  - Converts spaces and symbols to clean delimiters (`_` or `-`).
  - Zero-padded chapter numbering (`chapter_01`, `chapter_02`) to ensure proper sorting in file browsers and Kaggle datasets.

---

## Installation

```bash
uv venv 
uv sync
```

---

## Quick Start

### 1. In-Script Configuration
Open [`split_chapters.py`](split_chapters.py) and update the configuration section at the bottom:

```python
# 1. Path to your PDF (book name is auto-detected from this path)
PDF_PATH = "/path/to/Deep Learning by Ian Goodfellow.pdf"
BOOK_NAME = ""  # Leave blank to use filename, or set custom name

# 2. To auto-split using PDF bookmarks:
USE_BOOKMARKS = True

# 3. Or use manual ranges (with optional page offset):
USE_BOOKMARKS = False
PAGE_OFFSET = 10  # If viewer page is 10 pages ahead of printed page
DEFAULT_CHAPTERS = [
    "Introduction",
    "Linear Models",
]
CHAPTER_RANGES = [
    (1, 20),
    (21, 50),
]
```

Run the script:
```bash
python3 split_chapters.py
```

---

## Command Line Examples

### Auto-split using embedded bookmarks:
```bash
python3 split_chapters.py --pdf "/path/to/book.pdf" --auto-bookmarks
```

### Manual split with a +12 page offset:
```bash
python3 split_chapters.py --pdf "/path/to/book.pdf" --offset 12
```

### Save to custom folder with hyphen separators (kebab-case):
```bash
python3 split_chapters.py --pdf "/path/to/book.pdf" --auto-bookmarks --out "kaggle_dataset" --hyphen
```

### Chapter numbers only (no book title prefix):
```bash
python3 split_chapters.py --pdf "/path/to/book.pdf" --auto-bookmarks --no-book-name
```

---

## Output Filename Examples

| Settings | Output Filename |
|---|---|
| Auto Book Name + Chapter Number | `deep_learning_by_ian_goodfellow_chapter_01_introduction.pdf` |
| Hyphen Delimiter (`--hyphen`) | `deep-learning-by-ian-goodfellow-chapter-01-introduction.pdf` |
| No Book Name (`--no-book-name`) | `chapter_01_introduction.pdf` |
| No Prefixes (`--no-book-name --no-ch-num`) | `introduction.pdf` |
