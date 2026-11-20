#!/usr/bin/env bash
# Installation script for git_clone_colab
set -e

SCRIPT_DIR="$( cd -P "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
TARGET_DIR="${HOME}/.local/bin"
TARGET_BIN="${TARGET_DIR}/git_clone_colab"

echo "Installing git_clone_colab..."
mkdir -p "$TARGET_DIR"

chmod +x "$SCRIPT_DIR/git_clone_colab" "$SCRIPT_DIR/git_clone_colab.py"
ln -sf "$SCRIPT_DIR/git_clone_colab" "$TARGET_BIN"

echo "Checking installation..."
if which git_clone_colab >/dev/null 2>&1; then
    echo "Successfully installed! You can now run:"
    echo "  git_clone_colab <repo_link>"
else
    echo "Symlinked to $TARGET_BIN"
    echo "Please ensure $TARGET_DIR is in your PATH."
fi
