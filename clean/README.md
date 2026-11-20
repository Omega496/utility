# clean

A fast, unified CLI tool to automatically rename and sanitize file and folder names for **Kaggle datasets** and **Mobile / Syncthing sharing**.

---

## 🌟 Key Features

1. **Mobile / Syncthing Mode (Default)**:
   - Fixes illegal Android, FAT32/exFAT, and Windows characters (colons `:`, quotes `"`, pipes `|`, asterisks `*`, backslashes `\`, question marks `?`, `< >`, newlines `\n`).
   - Fixes trailing spaces and trailing periods (e.g., `navigating the ` -> `navigating the`, `file .md` -> `file.md`).
   - **Preserves readable spaces** (doesn't force underscores).
   - Sanitizes directory names in addition to filenames.
   - Automatically checks and updates Markdown links referencing renamed files.
   - **Current directory only by default** (non-recursive unless `-r` is passed).

2. **Kaggle Mode (`-k` / `--kaggle` or alias `kaggle_clean`)**:
   - Strict POSIX compliance: converts spaces, brackets, parentheses, colons, accents, and special characters into safe underscores (`_`).
   - Strips diacritics/accents (e.g., `résumé.pdf` -> `resume.pdf`).
   - Normalizes compound extensions (`.tar.gz`).
   - Strips internal dots from stems (`file.v1.pdf` -> `file_v1.pdf`).
   - Collision-safe: appends `_1`, `_2` if a target file already exists.

---

## 🚀 Quick Start & Usage

### 1. Mobile / Syncthing Cleaning (Default)

```bash
# Clean all files & folders in current directory (non-recursive)
clean

# Preview changes without modifying anything (dry-run)
clean -n

# Clean current directory AND subdirectories recursively
clean -r

# Clean a specific folder
clean "NeuroDyads_NEURODYAD/GSOC 2026 project"
```

### 2. Kaggle Upload Cleaning

```bash
# Clean current directory for Kaggle upload
clean -k

# Or using the backwards-compatible alias:
kaggle_clean .

# Recursive Kaggle cleaning
clean -k -r

# Convert to lowercase
clean -k --lower
```

### 3. Filter by Specific Extensions

```bash
clean -e md,opus,pdf
```

---

## 🛠️ CLI Options Reference

| Flag | Short | Description |
|---|---|---|
| `--kaggle` | `-k` | Run in strict Kaggle upload mode (underscores, ASCII only). |
| `--sync` / `--mobile` | `-s` / `-m` | Run in Mobile/Syncthing mode (default). |
| `--recursive` | `-r` | Recursively process subdirectories (default is current directory only). |
| `--dry-run` | `-n` | Preview changes without modifying any files or folders. |
| `--ext` | `-e` | Comma-separated list of file extensions to include (e.g. `pdf,txt,md`). |
| `--no-dirs` | | Only sanitize files; do not rename directories. |
| `--lower` | `-l` | Convert filenames to lowercase (Kaggle mode). |
| `--verbose` | `-v` | Show verbose output including already-compliant files. |
| `--no-color` | | Disable ANSI terminal colors. |
| `--version` | | Show program version. |

---

## 🧪 Running Tests

```bash
python3 -m unittest discover -s tests -v
```
