# Bengali TTS & Audio Synthesizer: Installation Guide

This guide details how to install and configure the `make_bengali_audio` tool (powered by `bodhan-ai/indic-speak` and Google Colab CLI) in the `utility` workspace.

---

## Section 1: AI Agent Setup Prompt

> **Copy and paste the prompt below into your AI coding agent** (e.g., Antigravity, Gemini CLI, Claude Code, Cursor, Aider). The agent will autonomously inspect your environment, install missing tools, set up the workspace, and verify readiness.

```text
You are an autonomous AI software engineer. Your task is to set up and verify the Bengali TTS (`make_bengali_audio`) subproject inside the `utility` repository.

Follow these steps carefully:

1. Environment Inspection:
   - Verify Python version (requires Python >= 3.12).
   - Check if `uv` is installed (`which uv`). If missing, install it (`curl -LsSf https://astral.sh/uv/install.sh | sh`).
   - Check if Google Colab CLI is installed (`which colab`). If missing, install via `uv tool install google-colab-cli` or `pip install google-colab-cli`.
   - Ensure `ffmpeg` is installed locally (`which ffmpeg`) for audio format conversions (Opus, MP3).

2. Colab CLI Verification:
   - Run `colab sessions` to verify that Colab CLI is authenticated and operational.
   - If not authenticated, inform the user to run `gcloud auth application-default login` or configure their Colab credentials.

3. Hugging Face Access Check:
   - Check for a valid Hugging Face token at `~/.cache/huggingface/token` or the `HF_TOKEN` environment variable.
   - Verify access to the model repository `bodhan-ai/indic-speak`. Note that `bodhan-ai/indic-speak` is gated (`gated: auto`): the user must accept the license agreement at https://huggingface.co/bodhan-ai/indic-speak once (approval is automatic and instant).

4. Workspace Dependencies & CLI Registration:
   - In the repository root (`utility/`), run `uv sync` to synchronize workspace packages.
   - Install `bengali_tts` in editable mode: `uv pip install -e ./bengali_tts`.
   - Run `./setup-cli.sh` to create global symlinks in `~/.local/bin` for `make_bengali_audio` and `make-bengali-audio`.

5. Testing & Verification:
   - Run unit tests: `PYTHONPATH=bengali_tts/src python3 -m unittest discover -s bengali_tts/tests`.
   - Verify CLI commands: `make_bengali_audio --help` and `make_bengali_audio --list-speakers`.
   - Report a clean summary of the setup status.
```

---

## Section 2: Manual Setup Instructions (For Humans)

Follow these step-by-step instructions to manually configure and install `make_bengali_audio`.

### Step 1: Install System Prerequisites

1. **Python 3.12 or later**:
   ```bash
   python3 --version
   ```
2. **`uv` Package Manager** (Recommended for fast dependency resolution):
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```
3. **`ffmpeg`** (Required for encoding `.opus` and `.mp3` audio files):
   ```bash
   # Debian / Ubuntu / Linux Mint
   sudo apt update && sudo apt install -y ffmpeg

   # Arch Linux
   sudo pacman -S ffmpeg

   # macOS (Homebrew)
   brew install ffmpeg
   ```

---

### Step 2: Install and Authenticate Google Colab CLI

Because `indic-speak` is a 3.3B parameter model requiring 8–16 GB of GPU VRAM, heavy inference is performed on Google Colab's cloud Tesla T4 GPU.

1. **Install Colab CLI**:
   ```bash
   uv tool install google-colab-cli
   # OR: pip install google-colab-cli
   ```
2. **Verify Colab CLI Authentication**:
   ```bash
   colab sessions
   ```
   If needed, log in using Google Cloud Application Default Credentials (ADC):
   ```bash
   gcloud auth application-default login \
     --scopes=openid,\
   https://www.googleapis.com/auth/cloud-platform,\
   https://www.googleapis.com/auth/userinfo.email,\
   https://www.googleapis.com/auth/colaboratory
   ```

---

### Step 3: Hugging Face License Acceptance

The weights for `bodhan-ai/indic-speak` are released under the Indic Open Model License.

1. In your web browser, navigate to:  
   👉 **[https://huggingface.co/bodhan-ai/indic-speak](https://huggingface.co/bodhan-ai/indic-speak)**
2. Log in with your Hugging Face account.
3. Fill out the brief request form (intended use, country) and click **"Acknowledge license / Request access"**.  
   *(Approval is automatic and instant!)*
4. Log in locally with your token:
   ```bash
   huggingface-cli login
   ```
   *(Your token will be saved at `~/.cache/huggingface/token` and detected automatically by the tool).*

---

### Step 4: Install Workspace Dependencies

Inside the `utility` repository root:

```bash
cd /path/to/utility

# Synchronize virtual environment packages
uv sync

# Install bengali_tts subproject in editable mode
uv pip install -e ./bengali_tts
```

---

### Step 5: Link Global Terminal Commands

Run the setup script to link the CLI commands into `~/.local/bin`:

```bash
./setup-cli.sh
```

Ensure `~/.local/bin` is in your shell's `PATH`:
```bash
echo $PATH | grep -q "$HOME/.local/bin" || echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

---

### Step 6: Verify Installation

Run the verification commands:

```bash
# Check CLI help
make_bengali_audio --help

# List available voices
make_bengali_audio --list-speakers

# Run unit tests
PYTHONPATH=bengali_tts/src python3 -m unittest discover -s bengali_tts/tests
```

All 8 tests should pass, confirming that the tool is ready for use!
