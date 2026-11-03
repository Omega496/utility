"""Tests for pdf_compiler.compiler."""

import os
from pathlib import Path
from PIL import Image
import pytest

from pdf_compiler.compiler import (
    SUPPORTED_EXTENSIONS,
    compile_folder,
    compile_images,
    find_image_files,
    images_to_pdf,
    natural_sort_key,
    process_image,
)


@pytest.fixture
def temp_image_dir(tmp_path: Path) -> Path:
    """Create a temporary directory with multiple dummy test images."""
    # Create images named out of order numerically: page1, page2, page10, page11
    names = ["page1.png", "page10.png", "page2.png", "page11.jpg", "banner.WEBP"]
    for name in names:
        img_path = tmp_path / name
        img = Image.new("RGB", (100, 100), color=(128, 64, 32))
        img.save(img_path)
    return tmp_path


def test_natural_sort_key():
    filenames = ["item10.png", "item1.png", "item2.png", "item20.png"]
    sorted_files = sorted(filenames, key=natural_sort_key)
    assert sorted_files == ["item1.png", "item2.png", "item10.png", "item20.png"]


def test_find_image_files_natural(temp_image_dir: Path):
    files = find_image_files(temp_image_dir, sort_mode="natural")
    filenames = [f.name for f in files]
    # 'banner.WEBP' has no number, page1, page2, page10, page11
    assert "banner.WEBP" in filenames
    assert filenames.index("page1.png") < filenames.index("page2.png")
    assert filenames.index("page2.png") < filenames.index("page10.png")
    assert filenames.index("page10.png") < filenames.index("page11.jpg")


def test_find_image_files_alpha(temp_image_dir: Path):
    files = find_image_files(temp_image_dir, sort_mode="alpha")
    filenames = [f.name for f in files]
    # Lexicographical: page1, page10, page11, page2
    assert filenames.index("page1.png") < filenames.index("page10.png")
    assert filenames.index("page10.png") < filenames.index("page11.jpg")
    assert filenames.index("page11.jpg") < filenames.index("page2.png")


def test_find_image_files_reverse(temp_image_dir: Path):
    normal = find_image_files(temp_image_dir, sort_mode="natural", reverse=False)
    reversed_files = find_image_files(temp_image_dir, sort_mode="natural", reverse=True)
    assert reversed_files == list(reversed(normal))


def test_process_image_rgba(tmp_path: Path):
    # Test that RGBA images with transparency are composited with white background
    rgba_path = tmp_path / "transparent.png"
    img = Image.new("RGBA", (50, 50), color=(255, 0, 0, 0))  # Fully transparent red
    img.save(rgba_path)

    converted = process_image(rgba_path)
    assert converted.mode == "RGB"
    # Transparent area should be composited as white (255, 255, 255)
    pixel = converted.getpixel((0, 0))
    assert pixel == (255, 255, 255)


def test_compile_single_image(tmp_path: Path):
    img_path = tmp_path / "single.jpg"
    img = Image.new("RGB", (80, 80), color=(0, 255, 0))
    img.save(img_path)

    output_pdf = tmp_path / "single.pdf"
    result = compile_images([img_path], output_pdf)

    assert result.is_file()
    assert result.stat().st_size > 0

    # Verify that the generated file is a valid PDF starting with %PDF-
    header = result.read_bytes()[:5]
    assert header == b"%PDF-"


def test_compile_folder(temp_image_dir: Path, tmp_path: Path):
    output_pdf = tmp_path / "compiled_output.pdf"
    result = compile_folder(temp_image_dir, output_pdf)

    assert result.is_file()
    assert result.stat().st_size > 0

    # Auto extension appending
    no_ext_output = tmp_path / "no_ext"
    result_auto = compile_folder(temp_image_dir, no_ext_output)
    assert result_auto.name == "no_ext.pdf"
    assert result_auto.is_file()


def test_compile_folder_subfolder_creation(temp_image_dir: Path, tmp_path: Path):
    nested_output = tmp_path / "nested" / "sub" / "output.pdf"
    result = compile_folder(temp_image_dir, nested_output)
    assert result.is_file()


def test_compile_folder_empty(tmp_path: Path):
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    with pytest.raises(FileNotFoundError, match="No images found"):
        compile_folder(empty_dir, tmp_path / "output.pdf")


def test_compile_nonexistent_folder(tmp_path: Path):
    nonexistent = tmp_path / "does_not_exist"
    with pytest.raises(FileNotFoundError, match="Directory not found"):
        compile_folder(nonexistent, tmp_path / "output.pdf")


def test_skip_corrupted_images(tmp_path: Path):
    valid_path = tmp_path / "valid.png"
    Image.new("RGB", (20, 20), color=(10, 20, 30)).save(valid_path)

    corrupted_path = tmp_path / "bad.png"
    corrupted_path.write_bytes(b"not an image content")

    output_pdf = tmp_path / "skip_test.pdf"

    # Should raise by default
    with pytest.raises(RuntimeError, match="Failed to process image"):
        compile_images([valid_path, corrupted_path], output_pdf, skip_corrupted=False)

    # Should succeed with skip_corrupted=True
    result = compile_images([valid_path, corrupted_path], output_pdf, skip_corrupted=True)
    assert result.is_file()


def test_images_to_pdf_wrapper(temp_image_dir: Path, tmp_path: Path):
    output_pdf = tmp_path / "wrapper_output.pdf"
    result = images_to_pdf(temp_image_dir, output_pdf)
    assert result is not None
    assert result.is_file()
