# git_clone_colab

A command-line tool that clones massive Git repositories directly inside Google Colab (leveraging Google Cloud's multi-gigabit datacenter connection), packages them into a compressed `.zip` archive, and downloads the zip file directly to your local computer.

---

## ⚡ Why Use This?

Cloning very large repositories (e.g., Linux kernel, LLM frameworks, monorepos, datasets with Git LFS) locally often suffers from:
- Slow local ISP bandwidth or throttling.
- Network interruptions requiring a restart of the multi-gigabyte git clone.
- Large uncompressed transfer sizes.

**`git_clone_colab` solves this:**
1. **Multi-Gigabit Datacenter Cloning**: Google Colab VMs clone repositories at 50–100+ MB/s.
2. **High-Ratio Compression**: The entire repository is compressed into a `.zip` archive on Colab's fast NVMe storage, drastically reducing the transfer payload.
3. **Seamless Download**: The compressed archive is streamed to your machine using the Google Colab CLI (`colab download`).
4. **Automated Lifecycle**: Creates ephemeral Colab sessions, runs the tasks, downloads the files, and cleanly stops the session afterwards so no compute is wasted.

---

## 🚀 Quick Start

Run the command from any directory:

```bash
git_clone_colab <repo_link>
```

### Examples

```bash
# Basic: clones, zips in Colab, and downloads repo.zip to current directory
git_clone_colab https://github.com/octocat/Hello-World.git

# Shallow clone (truncate history to depth 1 for maximum speed)
git_clone_colab https://github.com/torvalds/linux.git --depth 1

# Download to a specific directory and extract automatically
git_clone_colab https://github.com/huggingface/transformers.git -o ~/Downloads --extract

# Strip .git history folder to only download clean code files (smaller zip)
git_clone_colab https://github.com/pytorch/pytorch.git --no-git -x

# Clone a specific branch or tag
git_clone_colab https://github.com/vllm-project/vllm.git -b v0.6.0
```

---

## 🛠️ CLI Options & Flags

| Flag | Description | Default |
| :--- | :--- | :--- |
| `repo_link` | Git repository URL (HTTPS or SSH) | *(Required)* |
| `-o`, `--output-dir` | Local directory to save the downloaded zip | Current directory (`.`) |
| `-n`, `--name` | Custom name for the zip file and extracted folder | Inferred from repo URL |
| `-b`, `--branch` | Branch or tag to clone | Default branch |
| `--depth` | Shallow clone depth (e.g. `--depth 1`) | Full clone |
| `--submodules` | Recursively clone git submodules | `False` |
| `--no-git` | Exclude `.git/` folder before zipping to save space | `False` |
| `-x`, `--extract`, `--unzip` | Automatically unzip archive upon download | `False` |
| `--remove-zip` | Remove the `.zip` file after extracting (requires `-x`) | `False` |
| `-s`, `--session` | Reuse an existing active Colab session | Creates new ephemeral session |
| `--keep-session` | Keep Colab session running after task completion | `False` (auto-terminates) |
| `--gpu` | Request GPU runtime (`T4`, `L4`, `A100`) | CPU (free) |
| `--high-mem` | Request high-memory Colab shape | Standard memory |
| `--timeout` | Maximum execution timeout in seconds | `1800` (30 minutes) |
| `-v`, `--version` | Display version information | `1.0.0` |

---

## 📦 Installation & Setup

### 1. Prerequisites
Ensure you have the Google Colab CLI installed:
```bash
uv tool install google-colab-cli
# or: pip install google-colab-cli
```

### 2. Install `git_clone_colab`
Run the installer to link the CLI tool into `~/.local/bin/`:
```bash
cd "/home/heathcliff/Documents/utility/git colab"
./install.sh
```

Ensure `~/.local/bin` is in your `$PATH`.

---

## 🧪 Testing

Run the included unit test suite:
```bash
python3 test_git_clone_colab.py
```
