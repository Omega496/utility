# Installation & Setup Guide

This guide provides instructions to install and set up **pdf-compiler** (`image_to_pdf`, `txt_to_pdf`, and `md_to_pdf`), either automatically via an **AI Agent** or **manually**.

---

## 🤖 Option 1: AI Agent Setup (Copy & Paste Prompt)

If you are using an AI coding assistant (such as **Claude Code**, **Cursor**, **Windsurf**, **Antigravity**, **GitHub Copilot**, or **Aider**), simply copy the prompt below and paste it into your AI assistant:

```markdown
You are setting up the `pdf-compiler` repository on my machine. Please perform the following steps autonomously:

1. **Environment Check**:
   - Verify Python version (requires Python >= 3.10).
   - Check if `uv` package manager is available (`uv --version`). If not installed, you can either install it via `curl -LsSf https://astral.sh/uv/install.sh | sh` (or `pip install uv`), or fall back to standard `venv` + `pip`.

2. **Dependency & Environment Setup**:
   - **If using `uv` (preferred)**:
     - Run `uv sync` to install all runtime and development dependencies.
     - Install the CLI commands globally/editable so `image_to_pdf`, `txt_to_pdf`, and `md_to_pdf` are accessible from anywhere in the terminal:
       `uv tool install --editable . --force`
   - **If using standard `pip`**:
     - Create and activate a virtual environment (`python3 -m venv .venv && source .venv/bin/activate`).
     - Install package and dev dependencies: `pip install -e ".[dev]"`

3. **Verification**:
   - Run the test suite to ensure all 49 unit tests pass:
     `uv run python -m pytest` (or `pytest`)
   - Verify the CLI binaries are executable:
     `image_to_pdf --help`
     `txt_to_pdf --help`
     `md_to_pdf --help`

4. **Completion Report**:
   - Report if tests passed.
   - Show the detected install path of the CLI commands.
   - Provide quick 1-line command examples showing how I can run:
     - `image_to_pdf "MyImages.pdf"`
     - `txt_to_pdf notes.txt`
     - `md_to_pdf README.md`
```

---

## 👤 Option 2: Human Manual Installation

### 1. Prerequisites
- **Python 3.10** or higher
- **Git**
- [`uv`](https://docs.astral.sh/uv/) (strongly recommended) or standard `pip`

---

### 2. Clone the Repository

```bash
git clone https://github.com/<your-username>/pdf-compiler.git
cd pdf-compiler
```

---

### 3. Setup Dependencies

#### Method A: Using `uv` (Fast & Recommended)

1. **Install project dependencies:**
   ```bash
   uv sync
   ```

2. **Install CLI tools as global terminal commands:**
   ```bash
   uv tool install --editable . --force
   ```
   *This makes `image_to_pdf`, `txt_to_pdf`, and `md_to_pdf` accessible from any terminal window and directory!*

---

#### Method B: Using Standard Python & `pip`

1. **Create and activate a virtual environment:**
   - **Linux / macOS:**
     ```bash
     python3 -m venv .venv
     source .venv/bin/activate
     ```
   - **Windows (Command Prompt / PowerShell):**
     ```cmd
     python -m venv .venv
     .venv\Scripts\activate
     ```

2. **Install package in editable mode with development tools:**
   ```bash
   pip install -e ".[dev]"
   ```

---

### 4. Verify Installation

1. **Run tests to ensure everything is working properly:**
   - With `uv`:
     ```bash
     uv run python -m pytest
     ```
   - With standard `venv`:
     ```bash
     pytest
     ```
   *(All 49 unit tests should pass).*

2. **Check the CLI commands:**
   ```bash
   image_to_pdf --help
   txt_to_pdf --help
   md_to_pdf --help
   ```

3. **Smoke Tests:**
   ```bash
   # Test text to PDF
   echo "Meeting Notes" > sample.txt
   txt_to_pdf sample.txt

   # Test markdown to PDF
   echo "# Project Plan" > sample.md
   md_to_pdf sample.md

   # Test image compilation (run in folder with images)
   image_to_pdf test_output.pdf
   ```

---

## 🔧 Troubleshooting

### `command not found: image_to_pdf` (or `txt_to_pdf` / `md_to_pdf`)
If you installed via `uv tool install` but the terminal cannot find the commands, ensure that your user binary path is added to your shell `$PATH`:
- **Linux/macOS**: Add `export PATH="$HOME/.local/bin:$PATH"` to `~/.bashrc` or `~/.zshrc`.
- Alternatively, you can always run them directly from the repository using:
  ```bash
  uv run image_to_pdf <OUTPUT.pdf>
  uv run txt_to_pdf <FILE.txt>
  uv run md_to_pdf <FILE.md>
  ```
