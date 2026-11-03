# PDF Compiler & Converter

A fast, smart, and lightweight Python CLI toolkit and library for compiling images into PDFs, and converting plain text (`.txt`) and Markdown (`.md`) files into standard Google Docs formatted PDFs.

---

## ✨ Features

- 📝 **Plain Text to PDF (`txt_to_pdf`)**: Convert `.txt` files directly into clean, standard Google Docs formatted PDFs (Letter size, 1-inch margins, Arial/Helvetica, 1.15 line spacing).
- 📑 **Markdown to PDF (`md_to_pdf`)**: Convert `.md` files to Google Docs style PDFs with full support for headings, bold/italic, lists, code blocks, tables, blockquotes, horizontal rules, and footer page numbering.
- 🎯 **Smart Default Output Naming**: If output PDF filename is omitted, automatically creates `<filename>.pdf` matching the source file name.
- 🖼️ **Image Compilation (`image_to_pdf`)**: Compile image folders (`JPG`, `PNG`, `WEBP`, `BMP`, `TIFF`) into single multi-page PDFs with natural sorting (e.g., `page2` before `page10`).
- 📱 **Auto EXIF Rotation**: Automatically rotates phone photos and camera scans using EXIF orientation metadata so pages are never sideways.
- 🎨 **Smart Transparency Handling**: Transparent PNG/WEBP images are composited over a clean white background rather than rendering as black blocks.
- 🗜️ **Compression & Optimization**: Control output file size using `--quality` (1–100) and automatic PDF stream optimization.
- 💻 **Multiple CLI Interfaces**: Dedicated global commands (`image_to_pdf`, `txt_to_pdf`, `md_to_pdf`) or import directly as a Python library.

---

## 🚀 Installation & Setup

### 🤖 AI Agent Quickstart (Copy & Paste Prompt)

If you are using an AI coding assistant (**Cursor**, **Claude Code**, **Windsurf**, **Antigravity**, **GitHub Copilot**, etc.), copy and paste this prompt into your AI agent:

````markdown
Set up the `pdf-compiler` repository in my current environment:

1. **Verify Environment**: Ensure Python >= 3.10 is installed. Check if `uv` is installed (`uv --version`).
2. **Install & Build**:
   - If `uv` is available (recommended):
     - Run `uv sync` to install dependencies.
     - Run `uv tool install --editable . --force` so the `image_to_pdf`, `txt_to_pdf`, and `md_to_pdf` CLIs are available globally from any directory.
   - If using standard `pip`:
     - Create and activate a venv (`python3 -m venv .venv && source .venv/bin/activate`).
     - Run `pip install -e ".[dev]"`.
3. **Run Verification**:
   - Run the test suite: `uv run python -m pytest` (or `pytest`) to verify all 49 tests pass.
   - Verify CLI help: `image_to_pdf --help`, `txt_to_pdf --help`, and `md_to_pdf --help`.
4. **Confirm**: Report test results and show quick 1-line examples to run `image_to_pdf`, `txt_to_pdf`, and `md_to_pdf`.
````

---

### 👤 Manual Setup for Humans

#### Prerequisites
- Python **3.10** or higher
- [`uv`](https://docs.astral.sh/uv/) (strongly recommended) or standard `pip`

#### 1. Clone the repository
```bash
git clone https://github.com/<your-username>/pdf-compiler.git
cd pdf-compiler
```

#### 2. Install Dependencies

##### Option A: Using `uv` (Recommended)
```bash
# Sync dependencies
uv sync

# Install image_to_pdf as a global terminal command (run from ANY directory)
uv tool install --editable . --force
```

##### Option B: Using standard Python / `pip`
```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

#### 3. Verify Installation
```bash
image_to_pdf --help
txt_to_pdf --help
md_to_pdf --help
uv run python -m pytest
```

> 📖 For detailed troubleshooting and environment tips, see [INSTALL.md](INSTALL.md).

---

## 📖 How to Use

### 1. Plain Text to PDF (`txt_to_pdf`)

Convert any plain text file (`.txt`) directly into a clean, standard Google Docs formatted PDF (US Letter, 1-inch margins, Arial/Helvetica 11pt, 1.15 line spacing, and footer page numbering).

```bash
txt_to_pdf <textfilename>.txt [pdffilename.pdf]
```

#### Examples:
- **Default output (creates `notes.pdf`):**
  ```bash
  txt_to_pdf notes.txt
  ```
- **Custom output PDF name:**
  ```bash
  txt_to_pdf notes.txt my_document.pdf
  ```
- **Using explicit output flag:**
  ```bash
  txt_to_pdf ./logs/daily_report.txt -o ./reports/final.pdf
  ```
- **Disable footer page numbers:**
  ```bash
  txt_to_pdf notes.txt --no-page-numbers
  ```

---

### 2. Markdown to PDF (`md_to_pdf`)

Convert any Markdown file (`.md`) into a Google Docs styled PDF with full support for headings (H1–H6), bold/italic text, numbered/bulleted lists, code blocks, tables, blockquotes, and horizontal rules.

```bash
md_to_pdf <mdfilename>.md [pdffilename.pdf]
```

#### Examples:
- **Default output (creates `README.pdf`):**
  ```bash
  md_to_pdf README.md
  ```
- **Custom output PDF name:**
  ```bash
  md_to_pdf project_spec.md specification.pdf
  ```
- **Using explicit output flag:**
  ```bash
  md_to_pdf ./docs/guide.md -o ./dist/user_manual.pdf
  ```
- **Disable footer page numbers:**
  ```bash
  md_to_pdf summary.md --no-page-numbers
  ```

---

### 3. Images to PDF (`image_to_pdf`)

Compile image folders or specific images into a single multi-page PDF with natural sorting, EXIF auto-rotation, and compression options.

```bash
image_to_pdf [INPUT_PATH] [OUTPUT_PATH]
```

#### Basic Examples:
- **Compile images in current directory into a named PDF:**
  ```bash
  image_to_pdf "Grade_Cards.pdf"
  ```
- **Compile images from a specific folder:**
  ```bash
  image_to_pdf ./my_images "document.pdf"
  ```
- **Compile with explicit flags:**
  ```bash
  image_to_pdf -i ./scans -o ./compiled.pdf --quality 75
  ```

#### Options & Flags:
| Flag | Description | Default |
|------|-------------|---------|
| `-i`, `--input PATH` | Path to folder containing images | Current directory |
| `-o`, `--output PATH` | Output PDF filename or path | `output.pdf` |
| `--sort {natural,alpha,none}` | Natural (`page2` before `page10`), alphabetical, or none | `natural` |
| `--reverse` | Reverse image order | `False` |
| `--quality N` | JPEG compression quality (1–100) | Lossless/original |
| `--no-optimize` | Disable Pillow PDF stream size optimization | Enabled |
| `--no-exif` | Disable automatic EXIF camera rotation | Enabled |
| `--skip-corrupted` | Skip unreadable files without failing | `False` |
| `-v`, `--verbose` | Detailed progress log | `False` |
| `-q`, `--quiet` | Errors only | `False` |

---

### 4. Using as a Python Library

You can import all compilation tools directly into your own Python applications:

```python
from pdf_compiler import txt_to_pdf, md_to_pdf, compile_folder, compile_images

# 1. Convert Text to Google Docs PDF
txt_to_pdf("meeting_notes.txt")  # Generates meeting_notes.pdf
txt_to_pdf("report.txt", output_pdf="final_report.pdf")

# 2. Convert Markdown to Google Docs PDF
md_to_pdf("README.md")  # Generates README.pdf
md_to_pdf("docs/spec.md", output_pdf="spec.pdf")

# 3. Compile Images to PDF
compile_folder(
    folder_path="./documents",
    output_pdf="Compiled_Documents.pdf",
    sort_mode="natural",
    quality=85,
    auto_rotate=True,
)
```

---

## 🧪 Running Tests

The test suite covers text conversion, markdown parsing, natural sorting, EXIF orientation, transparency, corrupted files, and CLI commands (49 tests).

Run tests using `uv`:
```bash
uv run python -m pytest -v
```

Or with standard `pytest`:
```bash
pytest -v
```

---

## 📁 Project Structure

```
pdf-compiler/
├── pyproject.toml             # Package metadata, scripts, and dependencies
├── uv.lock                    # Locked dependency tree
├── README.md                  # Main documentation
├── INSTALL.md                 # Dedicated installation guide & AI prompt
├── main.py                    # Standalone entry point
├── src/
│   └── pdf_compiler/
│       ├── __init__.py        # Public library exports
│       ├── compiler.py        # Image compilation logic
│       ├── text_compiler.py   # Text & Markdown Google Docs PDF generator
│       ├── cli.py             # CLI parser for image_to_pdf
│       ├── txt_cli.py         # CLI parser for txt_to_pdf
│       └── md_cli.py          # CLI parser for md_to_pdf
└── tests/
    ├── test_compiler.py       # Tests for image compilation & sorting
    ├── test_cli.py            # Tests for image_to_pdf CLI
    ├── test_text_compiler.py  # Tests for txt_to_pdf & md_to_pdf logic
    ├── test_txt_cli.py        # Tests for txt_to_pdf CLI
    └── test_md_cli.py         # Tests for md_to_pdf CLI
```
