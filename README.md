# Utility

A unified collection of daily productivity tools and CLI utilities for documents, audio processing, dataset preparation, and PDF compilation.

All utilities in this repository share a single [uv](https://docs.astral.sh/uv/) workspace and virtual environment (`.venv`).

---

## Included Projects

| Project | Folder | Description | Key Commands |
|---|---|---|---|
| **PDF Chapter Splitter** | [`pdf_chapter_splitter/`](pdf_chapter_splitter/) | Split book PDFs into chapters using embedded bookmarks or page ranges, formatted for Kaggle datasets. | `python pdf_chapter_splitter/split_chapters.py` |
| **PDF Compiler** | [`make-pdf/`](make-pdf/) | Fast CLI tool and Python library to compile images, text, and markdown files into PDFs. | `image-to-pdf`, `txt-to-pdf`, `md-to-pdf` |
| **Make Audio** | [`Make-audio/`](Make-audio/) | Convert Markdown, Text, or PDF files into natural plain-English audio using Kokoro-TTS or Google Colab. | `md-to-audio`, `clean-md`, `bengali-clean` |
| **Kaggle Clean** | [`kaggle_clean/`](kaggle_clean/) | Fast CLI tool to rename and sanitize file names for Kaggle dataset uploads (POSIX compliant). | `kaggle_clean` |

---

## Setup & Installation

This project is managed with [uv](https://docs.astral.sh/uv/).

### 1. Install `uv` (if not already installed)
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Sync all projects into the unified virtual environment
From the root of the repository:
```bash
uv sync --all-packages
```

### 3. Expose CLI commands globally (optional)
Run the setup script once to link all commands into your `~/.local/bin`:
```bash
./setup-cli.sh
```
Now commands like `make-pdf`, `make-audio`, `kaggle-clean`, and `split-chapters` will work directly from anywhere in your terminal without needing to activate `.venv`.

---

## Quick Usage

### 1. PDF Chapter Splitter
```bash
# Auto-split chapters using embedded bookmarks
python pdf_chapter_splitter/split_chapters.py --pdf "/path/to/book.pdf" --auto-bookmarks

# Split with a page offset
python pdf_chapter_splitter/split_chapters.py --pdf "/path/to/book.pdf" --offset 10
```

### 2. PDF Compiler (`make-pdf`)
```bash
# Compile images into a PDF
image-to-pdf ./images -o document.pdf

# Convert markdown to PDF
md-to-pdf notes.md -o notes.pdf
```

### 3. Make Audio (`Make-audio`)
```bash
# Convert a markdown or PDF file to audio and play interactively
md-to-audio notes.md --play

# Synthesize using Kokoro voice
md-to-audio document.pdf -v af_heart -o output.mp3
```

### 4. Kaggle Clean (`kaggle_clean`)
```bash
# Sanitize all filenames in current directory for Kaggle uploads
kaggle_clean .

# Preview changes without modifying files (dry run)
kaggle_clean . --dry-run
```
