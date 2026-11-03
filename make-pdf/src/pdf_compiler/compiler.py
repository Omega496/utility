"""Core compilation functions for converting images to PDF."""

import os
import re
from pathlib import Path
from typing import List, Optional, Sequence, Union
from PIL import Image, ImageOps

SUPPORTED_EXTENSIONS = (
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".bmp",
    ".tiff",
    ".tif",
)


def natural_sort_key(value: Union[str, Path]) -> list:
    """Sort key for natural/human alphanumeric ordering (e.g. page2 before page10)."""
    text = str(value).lower()
    return [
        int(chunk) if chunk.isdigit() else chunk
        for chunk in re.split(r"(\d+)", text)
    ]


def find_image_files(
    folder_path: Union[str, Path],
    extensions: Optional[Sequence[str]] = None,
    sort_mode: str = "natural",
    reverse: bool = False,
) -> List[Path]:
    """Find and sort image files in a directory."""
    folder = Path(folder_path)
    if not folder.exists():
        raise FileNotFoundError(f"Directory not found: '{folder}'")
    if not folder.is_dir():
        raise NotADirectoryError(f"Path is not a directory: '{folder}'")

    if extensions is None:
        target_extensions = {ext.lower() for ext in SUPPORTED_EXTENSIONS}
    else:
        target_extensions = {
            ext.lower() if ext.startswith(".") else f".{ext.lower()}"
            for ext in extensions
        }

    image_files = [
        file_path
        for file_path in folder.iterdir()
        if file_path.is_file() and file_path.suffix.lower() in target_extensions
    ]

    if sort_mode == "natural":
        image_files.sort(key=lambda p: natural_sort_key(p.name), reverse=reverse)
    elif sort_mode == "alpha":
        image_files.sort(key=lambda p: p.name.lower(), reverse=reverse)
    elif sort_mode == "none":
        if reverse:
            image_files.reverse()
    else:
        raise ValueError(
            f"Unsupported sort mode '{sort_mode}'. Choose from 'natural', 'alpha', or 'none'."
        )

    return image_files


def process_image(img_path: Union[str, Path], auto_rotate: bool = True) -> Image.Image:
    """Open an image, apply EXIF auto-rotation if enabled, and convert cleanly to RGB.

    If the image has an alpha channel, composites it over a white background
    so transparent areas don't render black in the PDF.
    """
    path = Path(img_path)
    with Image.open(path) as raw_img:
        # Auto-rotate based on EXIF orientation if present
        if auto_rotate:
            img = ImageOps.exif_transpose(raw_img)
            if img is None:
                img = raw_img.copy()
            else:
                img = img.copy()
        else:
            img = raw_img.copy()

    # Handle transparency
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.split()[3])
        return background

    if img.mode != "RGB":
        return img.convert("RGB")

    return img


def compile_images(
    image_paths: Sequence[Union[str, Path]],
    output_pdf: Union[str, Path],
    auto_rotate: bool = True,
    quality: Optional[int] = None,
    optimize: bool = True,
    skip_corrupted: bool = False,
) -> Path:
    """Compile a list of image file paths into a single PDF file."""
    if not image_paths:
        raise ValueError("No images provided to compile.")

    output_path = Path(output_pdf)
    if not output_path.name.lower().endswith(".pdf"):
        output_path = output_path.with_suffix(".pdf")

    processed_images: List[Image.Image] = []
    used_files: List[Path] = []

    for img_path in image_paths:
        path = Path(img_path)
        if not path.is_file():
            if skip_corrupted:
                continue
            raise FileNotFoundError(f"Image file not found: '{path}'")

        try:
            processed = process_image(path, auto_rotate=auto_rotate)
            processed_images.append(processed)
            used_files.append(path)
        except Exception as err:
            if skip_corrupted:
                continue
            # Close already processed images before re-raising
            for img in processed_images:
                img.close()
            raise RuntimeError(f"Failed to process image '{path}': {err}") from err

    if not processed_images:
        raise ValueError("No valid images could be processed to create the PDF.")

    # Create destination directory if needed
    output_path.parent.mkdir(parents=True, exist_ok=True)

    base_image = processed_images[0]
    append_list = processed_images[1:]

    save_kwargs = {
        "save_all": True,
        "optimize": optimize,
    }
    if append_list:
        save_kwargs["append_images"] = append_list
    if quality is not None:
        save_kwargs["quality"] = quality

    try:
        base_image.save(output_path, **save_kwargs)
    finally:
        for img in processed_images:
            img.close()

    return output_path


def compile_folder(
    folder_path: Union[str, Path],
    output_pdf: Union[str, Path],
    sort_mode: str = "natural",
    reverse: bool = False,
    extensions: Optional[Sequence[str]] = None,
    auto_rotate: bool = True,
    quality: Optional[int] = None,
    optimize: bool = True,
    skip_corrupted: bool = False,
) -> Path:
    """Compile all matching images from a folder into a single PDF."""
    image_files = find_image_files(
        folder_path=folder_path,
        extensions=extensions,
        sort_mode=sort_mode,
        reverse=reverse,
    )

    if not image_files:
        exts_str = ", ".join(extensions or SUPPORTED_EXTENSIONS)
        raise FileNotFoundError(
            f"No images found in '{folder_path}'. Looked for extensions: {exts_str}"
        )

    return compile_images(
        image_paths=image_files,
        output_pdf=output_pdf,
        auto_rotate=auto_rotate,
        quality=quality,
        optimize=optimize,
        skip_corrupted=skip_corrupted,
    )


def images_to_pdf(
    image_folder: Union[str, Path],
    output_pdf_name: Union[str, Path],
    **kwargs,
) -> Optional[Path]:
    """Backward-compatible helper function for compiling images in a folder to a PDF."""
    try:
        result = compile_folder(image_folder, output_pdf_name, **kwargs)
        image_count = len(find_image_files(image_folder))
        print(f"Successfully compiled {image_count} images into {result}")
        return result
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return None
