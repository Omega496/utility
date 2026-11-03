"""pdf-compiler: A fast, smart Python tool and library to compile images into PDF documents."""

from pdf_compiler.cli import main
from pdf_compiler.compiler import (
    SUPPORTED_EXTENSIONS,
    compile_folder,
    compile_images,
    find_image_files,
    images_to_pdf,
    natural_sort_key,
    process_image,
)
from pdf_compiler.text_compiler import md_to_pdf, txt_to_pdf

__version__ = "0.1.0"

__all__ = [
    "compile_folder",
    "compile_images",
    "find_image_files",
    "images_to_pdf",
    "natural_sort_key",
    "process_image",
    "SUPPORTED_EXTENSIONS",
    "txt_to_pdf",
    "md_to_pdf",
    "main",
    "__version__",
]
