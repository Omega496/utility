"""Unit tests for md_to_pdf CLI (md_cli.py)."""

from pathlib import Path
import pytest

from pdf_compiler.md_cli import main


def test_md_cli_help(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert "usage: md_to_pdf" in captured.out


def test_md_cli_version(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert "0.1.0" in captured.out


def test_md_cli_default_output(tmp_path: Path, capsys):
    sample_md = tmp_path / "guide.md"
    sample_md.write_text("# Guide\n\nTesting default output path naming.", encoding="utf-8")

    ret = main([str(sample_md)])
    assert ret == 0

    expected_pdf = tmp_path / "guide.pdf"
    assert expected_pdf.is_file()

    captured = capsys.readouterr()
    assert "PDF created:" in captured.out


def test_md_cli_custom_output_positional(tmp_path: Path, capsys):
    sample_md = tmp_path / "input.md"
    sample_md.write_text("# Header\n\nPositional custom output.", encoding="utf-8")
    target_pdf = tmp_path / "custom_doc.pdf"

    ret = main([str(sample_md), str(target_pdf)])
    assert ret == 0
    assert target_pdf.is_file()

    captured = capsys.readouterr()
    assert "PDF created:" in captured.out


def test_md_cli_custom_output_flag(tmp_path: Path, capsys):
    sample_md = tmp_path / "flag_test.md"
    sample_md.write_text("# Title\n\nFlag custom output test.", encoding="utf-8")
    target_pdf = tmp_path / "flag_output.pdf"

    ret = main([str(sample_md), "-o", str(target_pdf)])
    assert ret == 0
    assert target_pdf.is_file()


def test_md_cli_verbose_and_quiet(tmp_path: Path, capsys):
    sample_md = tmp_path / "log.md"
    sample_md.write_text("# Log\n\nTesting verbose and quiet flags.", encoding="utf-8")

    # Verbose
    ret = main([str(sample_md), "-v"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "Reading markdown file:" in captured.out

    # Quiet
    out_pdf = tmp_path / "quiet.pdf"
    ret = main([str(sample_md), str(out_pdf), "-q"])
    assert ret == 0
    captured = capsys.readouterr()
    assert captured.out == ""


def test_md_cli_nonexistent_input(tmp_path: Path, capsys):
    bad_file = tmp_path / "does_not_exist.md"
    ret = main([str(bad_file)])
    assert ret == 1
    captured = capsys.readouterr()
    assert "Error: Input file does not exist" in captured.err
