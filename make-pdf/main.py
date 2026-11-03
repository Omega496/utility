"""Entrypoint script for pdf-compiler.

Run directly with:
    python main.py [options] [INPUT] [OUTPUT]

Or use the installed console script:
    image_to_pdf [options] [INPUT] [OUTPUT]
"""

import sys
from pathlib import Path

# Ensure src/ is on sys.path for direct python main.py execution
src_dir = Path(__file__).resolve().parent / "src"
if src_dir.is_dir() and str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from pdf_compiler.cli import main
from pdf_compiler.compiler import (
    SUPPORTED_EXTENSIONS,
    compile_folder,
    compile_images,
    find_image_files,
    images_to_pdf,
)
from pdf_compiler.text_compiler import md_to_pdf, txt_to_pdf

__all__ = [
    "main",
    "images_to_pdf",
    "compile_folder",
    "compile_images",
    "find_image_files",
    "SUPPORTED_EXTENSIONS",
    "txt_to_pdf",
    "md_to_pdf",
]

if __name__ == "__main__":
    sys.exit(main())
