"""Unit tests for text and markdown to PDF compiler."""

from pathlib import Path
import pytest

from pdf_compiler.text_compiler import (
    clean_unsupported_characters,
    md_to_pdf,
    resolve_output_pdf_path,
    txt_to_pdf,
)


def test_clean_unsupported_characters():
    text = "## ✨ Features\n- 📝 Plain Text\n├── tree\n© 2026"
    cleaned = clean_unsupported_characters(text)
    assert "✨" not in cleaned
    assert "📝" not in cleaned
    assert "## Features" in cleaned
    assert "Plain Text" in cleaned
    assert "├── tree" in cleaned
    assert "© 2026" in cleaned


def test_resolve_output_pdf_path_default():
    txt_path = Path("sample/notes.txt")
    resolved = resolve_output_pdf_path(txt_path)
    assert resolved == Path("sample/notes.pdf")

    md_path = Path("docs/guide.md")
    resolved_md = resolve_output_pdf_path(md_path)
    assert resolved_md == Path("docs/guide.pdf")


def test_resolve_output_pdf_path_custom():
    txt_path = Path("notes.txt")
    # With .pdf extension
    resolved = resolve_output_pdf_path(txt_path, "output.pdf")
    assert resolved == Path("output.pdf")

    # Without .pdf extension (auto-appends)
    resolved_no_ext = resolve_output_pdf_path(txt_path, "output")
    assert resolved_no_ext == Path("output.pdf")


def test_txt_to_pdf_success(tmp_path: Path):
    txt_file = tmp_path / "meeting_notes.txt"
    txt_file.write_text(
        "Quarterly Project Review\n\n"
        "This document summarizes the quarterly milestones.\n"
        "Line 1 of details\nLine 2 of details\n\n"
        "Final conclusion and next steps.",
        encoding="utf-8",
    )
    custom_pdf = tmp_path / "custom_notes.pdf"
    result = txt_to_pdf(txt_file, custom_pdf)

    assert result == custom_pdf
    assert result.is_file()
    assert result.stat().st_size > 500


def test_txt_to_pdf_default_output(tmp_path: Path):
    txt_file = tmp_path / "report.txt"
    txt_file.write_text("Plain text content without custom output name.", encoding="utf-8")

    result = txt_to_pdf(txt_file)
    expected_pdf = tmp_path / "report.pdf"

    assert result == expected_pdf
    assert expected_pdf.is_file()
    assert expected_pdf.stat().st_size > 500


def test_txt_to_pdf_unicode_and_blank_lines(tmp_path: Path):
    txt_file = tmp_path / "unicode_notes.txt"
    txt_file.write_text(
        "International characters: café, résumé, ñ, ü, ç, ©, —, “smart quotes”.\n\n\n\n"
        "Another paragraph after blank lines.",
        encoding="utf-8",
    )
    result = txt_to_pdf(txt_file)
    assert result.is_file()


def test_txt_to_pdf_missing_file(tmp_path: Path):
    non_existent = tmp_path / "missing.txt"
    with pytest.raises(FileNotFoundError):
        txt_to_pdf(non_existent)


def test_txt_to_pdf_no_page_numbers(tmp_path: Path):
    txt_file = tmp_path / "simple.txt"
    txt_file.write_text("Hello world", encoding="utf-8")
    result = txt_to_pdf(txt_file, show_page_numbers=False)
    assert result.is_file()


def test_md_to_pdf_success(tmp_path: Path):
    md_file = tmp_path / "document.md"
    md_file.write_text(
        "# Heading 1\n\n"
        "A paragraph with **bold** and *italic* text.\n\n"
        "## Heading 2\n\n"
        "- Bullet item A\n"
        "- Bullet item B\n\n"
        "1. Numbered 1\n"
        "2. Numbered 2\n",
        encoding="utf-8",
    )
    custom_pdf = tmp_path / "doc_output.pdf"
    result = md_to_pdf(md_file, custom_pdf)

    assert result == custom_pdf
    assert result.is_file()
    assert result.stat().st_size > 1000


def test_md_to_pdf_default_output(tmp_path: Path):
    md_file = tmp_path / "spec.md"
    md_file.write_text("# Specification\n\nDefault output naming test.", encoding="utf-8")

    result = md_to_pdf(md_file)
    expected_pdf = tmp_path / "spec.pdf"

    assert result == expected_pdf
    assert expected_pdf.is_file()
    assert expected_pdf.stat().st_size > 500


def test_md_to_pdf_rich_features(tmp_path: Path):
    md_file = tmp_path / "rich.md"
    md_file.write_text(
        """# Google Docs Markdown Test

This is a paragraph with `inline code` and a [link](https://example.com).

---

> This is a blockquote styled with a subtle border.

```python
def add(a: int, b: int) -> int:
    return a + b
```

| Task | Priority | Status |
| :--- | :---: | ---: |
| Fix bug | High | In Progress |
| Write docs | Medium | Done |
""",
        encoding="utf-8",
    )
    result = md_to_pdf(md_file)
    assert result.is_file()
    assert result.stat().st_size > 2000


def test_md_to_pdf_missing_file(tmp_path: Path):
    non_existent = tmp_path / "nonexistent.md"
    with pytest.raises(FileNotFoundError):
        md_to_pdf(non_existent)
