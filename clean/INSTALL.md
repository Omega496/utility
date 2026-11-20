# Installation & Setup Guide

This guide provides instructions to install and set up **kaggle_clean** (`kaggle_clean` and alias `kagle_clean`), either automatically via an **AI Agent** or **manually**.

---

## 🤖 Option 1: AI Agent Setup (Copy & Paste Prompt)

If you are using an AI coding assistant (such as **Claude Code**, **Cursor**, **Windsurf**, **Antigravity**, **GitHub Copilot**, or **Aider**), simply copy the prompt below and paste it into your AI assistant:

```markdown
You are setting up the `kaggle_clean` repository on my machine. Please perform the following steps autonomously:

1. **Environment Check**:
   - Verify Python version (requires Python >= 3.8).
   - Check if `uv` package manager is available (`uv --version`). If not installed, you can either install it via `curl -LsSf https://astral.sh/uv/install.sh | sh` (or `pip install uv`), or fall back to standard `venv` + `pip`.

2. **Dependency & Environment Setup**:
   - **If using `uv` (preferred)**:
     - Run `uv sync` to install all dependencies and set up the virtual environment.
     - Install the CLI commands globally/editable so `kaggle_clean` and `kagle_clean` are accessible from anywhere in the terminal:
       `uv tool install --editable . --force`
   - **If using standard `pip`**:
     - Create and activate a virtual environment (`python3 -m venv .venv && source .venv/bin/activate`).
     - Install package and dev dependencies: `pip install -e ".[dev]"`

3. **Verification**:
   - Run the test suite to ensure all unit tests pass:
     `uv run pytest` (or `uv run python -m unittest discover -s tests -v`)
   - Verify the CLI binaries are executable:
     `kaggle_clean --help`
     `kagle_clean --help`

4. **Completion Report**:
   - Report if tests passed.
   - Show the detected install path of the CLI commands.
   - Provide quick 1-line command examples showing how I can run:
     - `kaggle_clean "My File [1].pdf"`
     - `kaggle_clean . --dry-run`
     - `kaggle_clean . -e pdf,txt,md`
```

---

## 👤 Option 2: Human Manual Installation

### 1. Prerequisites
- **Python 3.8** or higher
- **Git**
- [`uv`](https://docs.astral.sh/uv/) (strongly recommended) or standard `pip`

---

### 2. Clone the Repository

```bash
git clone https://github.com/Omega496/kaggle_clean.git
cd kaggle_clean
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
   *This makes `kaggle_clean` and `kagle_clean` accessible from any terminal window and directory!*

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
     uv run pytest
     ```
   - With standard `unittest`:
     ```bash
     python3 -m unittest discover -s tests -v
     ```
   *(All 12 unit tests should pass).*

2. **Check the CLI commands:**
   ```bash
   kaggle_clean --help
   kagle_clean --help
   ```

3. **Smoke Tests:**
   ```bash
   # Test dry run on current directory
   kaggle_clean . --dry-run

   # Clean a single file
   kaggle_clean "Sample [Test] (v1).pdf" --dry-run
   ```

---

## 🔧 Troubleshooting

### `command not found: kaggle_clean` (or `kagle_clean`)
If you installed via `uv tool install` but the terminal cannot find the commands, ensure that your user binary path is added to your shell `$PATH`:
- **Linux/macOS**: Add `export PATH="$HOME/.local/bin:$PATH"` to `~/.bashrc` or `~/.zshrc`.
- Alternatively, you can run it directly from the repository using:
  ```bash
  uv run kaggle_clean . --dry-run
  ```
