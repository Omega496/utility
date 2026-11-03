"""Tests for pdf_compiler.cli."""

from pathlib import Path
from PIL import Image
import pytest

from pdf_compiler.cli import main, parse_paths


@pytest.fixture
def image_directory(tmp_path: Path) -> Path:
    img_dir = tmp_path / "images"
    img_dir.mkdir()
    for i in range(1, 4):
        p = img_dir / f"scan_{i}.png"
        Image.new("RGB", (50, 50), color=(i * 30, i * 30, i * 30)).save(p)
    return img_dir


def test_parse_paths_no_args():
    in_path, out_path = parse_paths([], None, None)
    assert in_path == Path.cwd()
    assert out_path.name == "output.pdf"


def test_parse_paths_single_pdf_arg():
    in_path, out_path = parse_paths(["MyDoc.pdf"], None, None)
    assert in_path == Path.cwd()
    assert out_path.name == "MyDoc.pdf"


def test_parse_paths_single_non_pdf_arg(tmp_path: Path):
    in_path, out_path = parse_paths([str(tmp_path)], None, None)
    assert in_path == tmp_path
    assert out_path.name == f"{tmp_path.name}.pdf"


def test_parse_paths_two_args(tmp_path: Path):
    out_file = tmp_path / "target.pdf"
    in_path, out_path = parse_paths([str(tmp_path), str(out_file)], None, None)
    assert in_path == tmp_path
    assert out_path == out_file


def test_parse_paths_flags():
    in_path, out_path = parse_paths([], "/custom/in", "/custom/out.pdf")
    assert in_path == Path("/custom/in")
    assert out_path == Path("/custom/out.pdf")


def test_cli_help(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert "usage: image_to_pdf" in captured.out


def test_cli_version(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert "0.1.0" in captured.out


def test_cli_compile_success(image_directory: Path, tmp_path: Path, capsys):
    out_pdf = tmp_path / "result.pdf"
    ret = main([str(image_directory), "-o", str(out_pdf)])
    assert ret == 0
    assert out_pdf.is_file()
    captured = capsys.readouterr()
    assert "PDF created:" in captured.out


def test_cli_compile_verbose(image_directory: Path, tmp_path: Path, capsys):
    out_pdf = tmp_path / "verbose_result.pdf"
    ret = main([str(image_directory), str(out_pdf), "-v"])
    assert ret == 0
    assert out_pdf.is_file()
    captured = capsys.readouterr()
    assert "Found 3 image(s) to compile:" in captured.out
    assert "scan_1.png" in captured.out


def test_cli_compile_quiet(image_directory: Path, tmp_path: Path, capsys):
    out_pdf = tmp_path / "quiet_result.pdf"
    ret = main([str(image_directory), str(out_pdf), "-q"])
    assert ret == 0
    assert out_pdf.is_file()
    captured = capsys.readouterr()
    assert captured.out == ""


def test_cli_nonexistent_input(tmp_path: Path, capsys):
    bad_dir = tmp_path / "nonexistent"
    ret = main([str(bad_dir), "-o", "fail.pdf"])
    assert ret == 1
    captured = capsys.readouterr()
    assert "Error: Input path does not exist" in captured.err


def test_cli_empty_directory(tmp_path: Path, capsys):
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    ret = main([str(empty_dir), "-o", "fail.pdf"])
    assert ret == 1
    captured = capsys.readouterr()
    assert "Error: No images found" in captured.err
