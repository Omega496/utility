"""Core compilation logic for converting plain text and Markdown files to PDF with Google Docs formatting."""

import html
import logging
from pathlib import Path
import re
from typing import Optional, Union

import markdown
from xhtml2pdf import pisa

# Suppress verbose missing font/glyph warnings from xhtml2pdf and reportlab
logging.getLogger("xhtml2pdf").setLevel(logging.ERROR)
logging.getLogger("reportlab").setLevel(logging.ERROR)

# Pattern matching emoji pictographs and symbols that lack glyphs in standard PDF fonts
EMOJI_PATTERN = re.compile(
    r"[\U0001F300-\U0001FAFF\U00002700-\U000027BF\U00002600-\U000026FF\U0000FE00-\U0000FE0F]+\s*",
    flags=re.UNICODE,
)


def clean_unsupported_characters(text: str) -> str:
    """Remove emoji pictographs that render as blank/black boxes in standard PDF engines.

    Preserves standard punctuation, typographical symbols (©, ®, ™, —, etc.),
    and box-drawing characters (├──, └──, etc.).
    """
    return EMOJI_PATTERN.sub("", text)


def find_system_fonts() -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Detect available TrueType system fonts for standard text, bold text, and monospace code."""
    candidate_sans = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "C:\\Windows\\Fonts\\arial.ttf",
    ]
    candidate_bold = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "C:\\Windows\\Fonts\\arialbd.ttf",
    ]
    candidate_mono = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansMono-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeMono.ttf",
        "/System/Library/Fonts/Supplemental/Courier New.ttf",
        "C:\\Windows\\Fonts\\consola.ttf",
    ]

    sans = next((p for p in candidate_sans if Path(p).is_file()), None)
    bold = next((p for p in candidate_bold if Path(p).is_file()), None)
    mono = next((p for p in candidate_mono if Path(p).is_file()), None)
    return sans, bold, mono


def get_font_face_css() -> str:
    """Return @font-face CSS rules if system TrueType fonts are available."""
    sans, bold, mono = find_system_fonts()
    rules = []
    if sans:
        rules.append(f"""
@font-face {{
    font-family: 'AppSans';
    src: url('{sans}');
}}""")
    if bold:
        rules.append(f"""
@font-face {{
    font-family: 'AppSans';
    src: url('{bold}');
    font-weight: bold;
}}""")
    if mono:
        rules.append(f"""
@font-face {{
    font-family: 'AppMono';
    src: url('{mono}');
}}""")
    return "\n".join(rules)


def get_google_docs_css(page_size: str = "letter", margin: str = "1in") -> str:
    """Return Google Docs formatted CSS stylesheet with robust text wrapping."""
    font_faces = get_font_face_css()
    return f"""
{font_faces}
@page {{
    size: {page_size};
    margin: {margin};
    @frame footer {{
        -pdf-frame-content: footerContent;
        bottom: 0.4in;
        margin-left: {margin};
        margin-right: {margin};
        height: 0.4in;
    }}
}}
body {{
    font-family: 'AppSans', Helvetica, Arial, sans-serif;
    font-size: 10.5pt;
    line-height: 1.25;
    color: #202124;
    word-wrap: break-word;
}}
h1 {{
    font-size: 19pt;
    font-weight: bold;
    color: #1f1f1f;
    margin-top: 14pt;
    margin-bottom: 5pt;
    word-wrap: break-word;
}}
h2 {{
    font-size: 14.5pt;
    font-weight: bold;
    color: #1f1f1f;
    margin-top: 12pt;
    margin-bottom: 4pt;
    word-wrap: break-word;
}}
h3 {{
    font-size: 12.5pt;
    font-weight: bold;
    color: #1f1f1f;
    margin-top: 10pt;
    margin-bottom: 3pt;
    word-wrap: break-word;
}}
h4, h5, h6 {{
    font-size: 10.5pt;
    font-weight: bold;
    color: #1f1f1f;
    margin-top: 8pt;
    margin-bottom: 3pt;
    word-wrap: break-word;
}}
p {{
    margin-top: 0;
    margin-bottom: 7pt;
    word-wrap: break-word;
}}
ul, ol {{
    margin-top: 0;
    margin-bottom: 7pt;
    padding-left: 16pt;
}}
li {{
    margin-bottom: 3pt;
    word-wrap: break-word;
}}
blockquote {{
    border-left: 3px solid #dadce0;
    margin: 6pt 0 6pt 0;
    padding-left: 10pt;
    color: #5f6368;
    font-style: italic;
    word-wrap: break-word;
}}
pre {{
    background-color: #f8f9fa;
    border: 1px solid #dadce0;
    padding: 6pt 8pt;
    font-family: 'AppMono', Courier, monospace;
    font-size: 8.5pt;
    border-radius: 4px;
    margin-top: 5pt;
    margin-bottom: 7pt;
    white-space: pre-wrap;
    word-wrap: break-word;
}}
code {{
    font-family: 'AppMono', Courier, monospace;
    background-color: #f1f3f4;
    font-size: 9pt;
    word-wrap: break-word;
}}
pre code {{
    background-color: transparent;
    font-size: 8.5pt;
}}
table {{
    border: 1px solid #dadce0;
    width: 100%;
    margin-top: 7pt;
    margin-bottom: 7pt;
    word-wrap: break-word;
}}
th, td {{
    border: 1px solid #dadce0;
    padding: 5pt 7pt;
    text-align: left;
    font-size: 9.5pt;
    word-wrap: break-word;
}}
th {{
    background-color: #f8f9fa;
    font-weight: bold;
}}
hr {{
    border: 0;
    border-top: 1px solid #dadce0;
    margin: 12pt 0;
}}
a {{
    color: #1a73e8;
    text-decoration: underline;
}}
#footerContent {{
    text-align: right;
    font-size: 9pt;
    color: #70757a;
    font-family: 'AppSans', Helvetica, Arial, sans-serif;
}}
"""


def resolve_output_pdf_path(
    input_path: Union[str, Path],
    output_pdf: Optional[Union[str, Path]] = None,
) -> Path:
    """Resolve destination PDF path. If output_pdf is None, uses input filename with .pdf suffix."""
    in_path = Path(input_path)
    if output_pdf is not None and str(output_pdf).strip():
        out_path = Path(output_pdf)
    else:
        out_path = in_path.with_suffix(".pdf")

    if not out_path.name.lower().endswith(".pdf"):
        out_path = out_path.with_suffix(".pdf")

    return out_path


def read_text_file(file_path: Path) -> str:
    """Read text file with UTF-8 encoding, falling back to Latin-1 if decoding fails."""
    try:
        return file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return file_path.read_text(encoding="latin-1")


def render_html_to_pdf(html_content: str, output_path: Path) -> Path:
    """Render full HTML document string into a PDF file using xhtml2pdf."""
    # Ensure loggers stay silent during render
    logging.getLogger("xhtml2pdf").setLevel(logging.ERROR)
    logging.getLogger("reportlab").setLevel(logging.ERROR)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as pdf_file:
        pisa_status = pisa.CreatePDF(
            src=html_content.encode("utf-8"),
            dest=pdf_file,
            encoding="utf-8",
            resource_policy=pisa.PERMISSIVE_POLICY,
        )

    if pisa_status.err:
        raise RuntimeError(f"PDF generation failed with {pisa_status.err} error(s)")

    return output_path


def txt_to_pdf(
    input_path: Union[str, Path],
    output_pdf: Optional[Union[str, Path]] = None,
    page_size: str = "letter",
    margin: str = "1in",
    show_page_numbers: bool = True,
) -> Path:
    """Convert a plain text (.txt) file into a Google Docs formatted PDF."""
    in_path = Path(input_path)
    if not in_path.is_file():
        raise FileNotFoundError(f"Input text file does not exist: '{in_path}'")

    out_path = resolve_output_pdf_path(in_path, output_pdf)
    raw_text = read_text_file(in_path)
    cleaned_text = clean_unsupported_characters(raw_text)

    # Convert plain text to Google Docs paragraphs
    paragraphs = cleaned_text.split("\n\n")
    html_paragraphs = []
    for para in paragraphs:
        cleaned = para.strip()
        if not cleaned:
            continue
        # Escape HTML and preserve line breaks within paragraphs
        escaped = html.escape(cleaned).replace("\n", "<br/>")
        html_paragraphs.append(f"<p>{escaped}</p>")

    if not html_paragraphs:
        body_content = "<p></p>"
    else:
        body_content = "\n".join(html_paragraphs)

    footer_html = (
        '<div id="footerContent"><pdf:pagenumber/></div>' if show_page_numbers else ""
    )

    css = get_google_docs_css(page_size=page_size, margin=margin)
    full_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
{css}
</style>
</head>
<body>
{body_content}
{footer_html}
</body>
</html>"""

    return render_html_to_pdf(full_html, out_path)


def md_to_pdf(
    input_path: Union[str, Path],
    output_pdf: Optional[Union[str, Path]] = None,
    page_size: str = "letter",
    margin: str = "1in",
    show_page_numbers: bool = True,
) -> Path:
    """Convert a Markdown (.md) file into a Google Docs formatted PDF."""
    in_path = Path(input_path)
    if not in_path.is_file():
        raise FileNotFoundError(f"Input markdown file does not exist: '{in_path}'")

    out_path = resolve_output_pdf_path(in_path, output_pdf)
    raw_md = read_text_file(in_path)
    cleaned_md = clean_unsupported_characters(raw_md)

    # Convert Markdown to HTML with standard extensions
    body_content = markdown.markdown(
        cleaned_md,
        extensions=["extra", "tables", "fenced_code", "sane_lists"],
    )

    footer_html = (
        '<div id="footerContent"><pdf:pagenumber/></div>' if show_page_numbers else ""
    )

    css = get_google_docs_css(page_size=page_size, margin=margin)
    full_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
{css}
</style>
</head>
<body>
{body_content}
{footer_html}
</body>
</html>"""

    return render_html_to_pdf(full_html, out_path)
