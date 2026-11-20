# clean

A fast, unified CLI tool to automatically rename and sanitize file and folder names for **Kaggle datasets** (default) and **Mobile / Syncthing sharing**.

---

## 🌟 Key Features

1. **Kaggle Mode (Default)**:
   - **Strict POSIX compliance**: converts spaces, brackets `[]`, parentheses `()`, colons `:`, commas, accents, and special characters into safe underscores (`_`).
   - Strips diacritics/accents (e.g., `résumé.pdf` -> `resume.pdf`).
   - Normalizes compound extensions (`.tar.gz`).
   - Strips internal dots from stems (`file.v1.pdf` -> `file_v1.pdf`).
   - Collision-safe: appends `_1`, `_2` if a target file already exists.
   - Cleans the current directory by default (non-recursive unless `-r` is passed).

2. **Mobile / Syncthing Mode (`-s` / `-m` / `--sync`)**:
   - Fixes illegal Android, FAT32/exFAT, and Windows characters (colons `:`, quotes `"`, pipes `|`, asterisks `*`, backslashes `\`, question marks `?`, `< >`, newlines `\n`).
   - Fixes trailing spaces and trailing periods (e.g., `navigating the ` -> `navigating the`, `file .md` -> `file.md`).
   - **Preserves readable spaces** (doesn't force underscores).
   - Sanitizes directory names in addition to filenames.
   - Automatically checks and updates Markdown links referencing renamed files.

---

## 🚀 Quick Start & Usage

### 1. Kaggle Upload Cleaning (Default)

Simply run `clean` in any directory:

```bash
# Clean current directory for Kaggle upload (Default)
clean

# Preview changes without modifying anything (dry-run)
clean -n

# Clean current directory AND subdirectories recursively
clean -r

# Convert to lowercase
clean -l

# Clean a specific folder
clean ./my_dataset
```

### 2. Mobile / Syncthing Cleaning (`-s` or `-m`)

```bash
# Clean current directory for mobile sharing (keeps spaces, fixes colons/illegal chars)
clean -s

# Recursive mobile cleaning
clean -s -r

# Preview mobile renames
clean -s -n
```

### 3. Filter by Specific Extensions

```bash
clean -e md,opus,pdf
```

---

## 🛠️ CLI Options Reference

| Flag | Short | Description |
|---|---|---|
| *(default)* | | Kaggle upload mode (underscores, ASCII, POSIX). |
| `--sync` / `--mobile` | `-s` / `-m` | Mobile/Syncthing mode (preserves spaces, fixes Android forbidden characters). |
| `--recursive` | `-r` | Recursively process subdirectories (default is current directory only). |
| `--dry-run` | `-n` | Preview changes without modifying any files or folders. |
| `--ext` | `-e` | Comma-separated list of file extensions to include (e.g. `pdf,txt,md`). |
| `--no-dirs` | | Only sanitize files; do not rename directories. |
| `--lower` | `-l` | Convert filenames to lowercase (Kaggle mode). |
| `--sep` | | Replacement character for Kaggle mode (default: `_`). |
| `--verbose` | `-v` | Show verbose output including already-compliant files. |
| `--no-color` | | Disable ANSI terminal colors. |
| `--version` | | Show program version. |

---

## 🧪 Running Tests

```bash
python3 -m unittest discover -s tests -v
```
