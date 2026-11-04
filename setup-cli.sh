#!/usr/bin/env bash
# setup-cli.sh
# Links all utility commands into ~/.local/bin so they are globally available in terminal.

set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOCAL_BIN="$HOME/.local/bin"
VENV_BIN="$REPO_DIR/.venv/bin"

mkdir -p "$LOCAL_BIN"

COMMANDS=(
  # make-pdf
  "make-pdf" "make_pdf" "image-to-pdf" "image_to_pdf"
  "pdf-compiler" "txt-to-pdf" "txt_to_pdf" "md-to-pdf" "md_to_pdf"
  # Make-audio
  "make-audio" "make_audio" "md-to-audio" "clean-md" "clean_md"
  "bengali-clean" "bengali_clean"
  # kaggle_clean
  "kaggle-clean" "kaggle_clean" "kagle_clean"
)

echo "Linking commands to $LOCAL_BIN ..."
for cmd in "${COMMANDS[@]}"; do
  if [ -f "$VENV_BIN/$cmd" ]; then
    ln -sf "$VENV_BIN/$cmd" "$LOCAL_BIN/$cmd"
    echo "  ✓ $cmd"
  fi
done

# Chapter splitter
if [ -f "$REPO_DIR/pdf_chapter_splitter/split_chapters.py" ]; then
  ln -sf "$REPO_DIR/pdf_chapter_splitter/split_chapters.py" "$LOCAL_BIN/split-chapters"
  ln -sf "$REPO_DIR/pdf_chapter_splitter/split_chapters.py" "$LOCAL_BIN/split_chapters"
  echo "  ✓ split-chapters"
  echo "  ✓ split_chapters"
fi

echo "Done! All commands are now ready in your terminal."
