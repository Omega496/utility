"""Unit tests for txt_to_pdf CLI (txt_cli.py)."""

from pathlib import Path
import pytest

from pdf_compiler.txt_cli import main


def test_txt_cli_help(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert "usage: txt_to_pdf" in captured.out


def test_txt_cli_version(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert "0.1.0" in captured.out


def test_txt_cli_default_output(tmp_path: Path, capsys):
    sample_txt = tmp_path / "notes.txt"
    sample_txt.write_text("Hello text to pdf without output param", encoding="utf-8")

    ret = main([str(sample_txt)])
    assert ret == 0

    expected_pdf = tmp_path / "notes.pdf"
    assert expected_pdf.is_file()

    captured = capsys.readouterr()
    assert "PDF created:" in captured.out


def test_txt_cli_custom_output_positional(tmp_path: Path, capsys):
    sample_txt = tmp_path / "input.txt"
    sample_txt.write_text("Positional custom output test", encoding="utf-8")
    target_pdf = tmp_path / "custom_named.pdf"

    ret = main([str(sample_txt), str(target_pdf)])
    assert ret == 0
    assert target_pdf.is_file()

    captured = capsys.readouterr()
    assert "PDF created:" in captured.out


def test_txt_cli_custom_output_flag(tmp_path: Path, capsys):
    sample_txt = tmp_path / "flag_test.txt"
    sample_txt.write_text("Flag custom output test", encoding="utf-8")
    target_pdf = tmp_path / "flag_output.pdf"

    ret = main([str(sample_txt), "-o", str(target_pdf)])
    assert ret == 0
    assert target_pdf.is_file()


def test_txt_cli_verbose_and_quiet(tmp_path: Path, capsys):
    sample_txt = tmp_path / "log.txt"
    sample_txt.write_text("Testing verbose and quiet flags", encoding="utf-8")

    # Verbose
    ret = main([str(sample_txt), "-v"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "Reading text file:" in captured.out

    # Quiet
    out_pdf = tmp_path / "quiet.pdf"
    ret = main([str(sample_txt), str(out_pdf), "-q"])
    assert ret == 0
    captured = capsys.readouterr()
    assert captured.out == ""


def test_txt_cli_nonexistent_input(tmp_path: Path, capsys):
    bad_file = tmp_path / "does_not_exist.txt"
    ret = main([str(bad_file)])
    assert ret == 1
    captured = capsys.readouterr()
    assert "Error: Input file does not exist" in captured.err
