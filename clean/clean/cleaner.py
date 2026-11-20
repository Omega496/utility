"""Core sanitization and renaming logic for Kaggle and Mobile/Syncthing compliance."""

import os
import re
import unicodedata
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

COMPOUND_EXTENSIONS = {
    ".tar.gz",
    ".tar.bz2",
    ".tar.xz",
    ".tar.zst",
}

DEFAULT_TARGET_EXTENSIONS = {
    ".pdf",
    ".txt",
    ".md",
    ".mp3",
    ".opus",
    ".wav",
}

# Forbidden characters on Android/FAT32/exFAT/Windows filesystems
FORBIDDEN_SYNC_CHARS = set(':*?"<>|\\\r\n\t')


class CleanMode(str, Enum):
    KAGGLE = "kaggle"
    SYNC = "sync"


@dataclass
class RenameResult:
    source: Path
    target: Path
    item_type: str = "file"  # "file" or "directory"
    status: str = "already_clean"  # 'renamed', 'already_clean', 'collision_resolved', 'error'
    error_message: Optional[str] = None

    @property
    def changed(self) -> bool:
        return self.status in ("renamed", "collision_resolved")


def split_filename(filename: str) -> Tuple[str, str]:
    """
    Split filename into (stem, extension).
    Recognizes compound extensions like .tar.gz and normalizes extension to lowercase.
    """
    lower_filename = filename.lower()
    for compound in COMPOUND_EXTENSIONS:
        if lower_filename.endswith(compound):
            stem = filename[:-len(compound)]
            return stem, compound

    parts = filename.rsplit(".", 1)
    if len(parts) == 2 and parts[0]:
        stem, ext = parts[0], "." + parts[1].lower()
    else:
        stem, ext = filename, ""

    return stem, ext


def sanitize_filename_kaggle(
    filename: str,
    separator: str = "_",
    lowercase: bool = False,
    is_dir: bool = False,
) -> str:
    """
    Sanitize filename or directory name to be Kaggle compliant.

    Kaggle allows: letters (a-z, A-Z), numbers (0-9), hyphens (-), underscores (_),
    and periods (.) strictly for file extensions.
    Spaces, brackets, colons, quotes, accents, and non-ASCII chars are replaced with separator.
    """
    if is_dir:
        stem, ext = filename, ""
    else:
        stem, ext = split_filename(filename)

    # Normalize Unicode characters (strip accents like é -> e)
    stem_norm = unicodedata.normalize("NFKD", stem)
    stem_ascii = "".join(c for c in stem_norm if not unicodedata.combining(c))

    if lowercase:
        stem_ascii = stem_ascii.lower()

    # Replace any character that is not alphanumeric, hyphen, or underscore with separator
    cleaned_stem = re.sub(r"[^a-zA-Z0-9_\-]+", separator, stem_ascii)

    # Collapse multiple consecutive separators or mixed hyphens/underscores
    cleaned_stem = re.sub(r"[-_]{2,}", separator, cleaned_stem)

    # Strip leading and trailing separators and periods
    cleaned_stem = cleaned_stem.strip("._- ")

    if not cleaned_stem:
        cleaned_stem = "kaggle_dir" if is_dir else "kaggle_file"

    return f"{cleaned_stem}{ext}"


def sanitize_name_sync(
    name: str,
    is_dir: bool = False,
) -> str:
    """
    Sanitize file or directory name to be safe for Android/Windows/Syncthing.

    Preserves readable spaces and valid Unicode names, but removes/replaces:
    - colons (:) and pipes (|) -> ' -'
    - newlines, carriage returns, tabs -> ' '
    - quotes (") -> single quote (')
    - brackets (< >) -> ( )
    - asterisks (*) and backslashes (\\) -> '_'
    - question marks (?) -> ''
    - trailing spaces and trailing dots (forbidden on Windows & Android)
    """
    if is_dir:
        stem, ext = name, ""
    else:
        stem, ext = os.path.splitext(name)

    # Replace newlines, carriage returns, tabs with space
    clean_stem = re.sub(r'[\r\n\t]+', ' ', stem)

    # Replace colons and pipes with spaced dashes
    clean_stem = clean_stem.replace(':', ' -')
    clean_stem = clean_stem.replace('|', ' -')

    # Replace illegal characters
    clean_stem = clean_stem.replace('?', '')
    clean_stem = clean_stem.replace('"', "'")
    clean_stem = clean_stem.replace('<', '(').replace('>', ')')
    clean_stem = clean_stem.replace('*', '_')
    clean_stem = clean_stem.replace('\\', '_')

    # Collapse consecutive spaces and dashes
    clean_stem = re.sub(r' +', ' ', clean_stem)
    clean_stem = re.sub(r' - +', ' - ', clean_stem)
    clean_stem = re.sub(r'-+', '-', clean_stem)

    # Strip leading and trailing spaces or dots (forbidden on Windows/Android)
    clean_stem = clean_stem.strip(' .')

    if not clean_stem:
        clean_stem = "_"

    return f"{clean_stem}{ext}"


def sanitize_name(
    name: str,
    mode: CleanMode = CleanMode.SYNC,
    separator: str = "_",
    lowercase: bool = False,
    is_dir: bool = False,
) -> str:
    """Dispatcher for sanitization based on selected mode."""
    if mode == CleanMode.KAGGLE:
        return sanitize_filename_kaggle(
            name,
            separator=separator,
            lowercase=lowercase,
            is_dir=is_dir,
        )
    return sanitize_name_sync(name, is_dir=is_dir)


def resolve_collision(target_path: Path, source_path: Path) -> Tuple[Path, bool]:
    """
    Find a non-colliding destination path if target_path already exists.
    Returns (resolved_path, was_collision).
    """
    try:
        if source_path.resolve() == target_path.resolve():
            return target_path, False
    except FileNotFoundError:
        if source_path == target_path:
            return target_path, False

    if not target_path.exists():
        return target_path, False

    is_dir = source_path.is_dir() or target_path.is_dir()
    if is_dir:
        stem, ext = target_path.name, ""
    else:
        stem, ext = split_filename(target_path.name)

    parent = target_path.parent
    counter = 1

    while True:
        candidate_name = f"{stem}_{counter}{ext}"
        candidate_path = parent / candidate_name
        if not candidate_path.exists():
            return candidate_path, True
        counter += 1


def clean_file(
    file_path: Path,
    mode: CleanMode = CleanMode.SYNC,
    dry_run: bool = False,
    separator: str = "_",
    lowercase: bool = False,
) -> RenameResult:
    """Clean an individual file."""
    if not file_path.exists():
        return RenameResult(
            source=file_path,
            target=file_path,
            item_type="file",
            status="error",
            error_message="File does not exist",
        )

    if not file_path.is_file():
        return RenameResult(
            source=file_path,
            target=file_path,
            item_type="file",
            status="error",
            error_message="Path is not a regular file",
        )

    original_name = file_path.name
    cleaned_name = sanitize_name(
        original_name,
        mode=mode,
        separator=separator,
        lowercase=lowercase,
        is_dir=False,
    )

    if original_name == cleaned_name:
        return RenameResult(
            source=file_path,
            target=file_path,
            item_type="file",
            status="already_clean",
        )

    candidate_target = file_path.parent / cleaned_name
    final_target, had_collision = resolve_collision(candidate_target, file_path)

    status = "collision_resolved" if had_collision else "renamed"

    if not dry_run:
        try:
            file_path.rename(final_target)
        except OSError as e:
            return RenameResult(
                source=file_path,
                target=final_target,
                item_type="file",
                status="error",
                error_message=str(e),
            )

    return RenameResult(
        source=file_path,
        target=final_target,
        item_type="file",
        status=status,
    )


def clean_directory(
    dir_path: Path,
    mode: CleanMode = CleanMode.SYNC,
    extensions: Optional[Set[str]] = None,
    recursive: bool = False,
    dry_run: bool = False,
    separator: str = "_",
    lowercase: bool = False,
    clean_dirs: bool = True,
) -> List[RenameResult]:
    """
    Clean files and optionally directories in dir_path.
    - If recursive=False: processes only items directly inside dir_path (current directory only).
    - If recursive=True: processes the entire tree bottom-up.
    - Skips hidden files and directories (names starting with '.').
    """
    results: List[RenameResult] = []

    if not dir_path.exists():
        return [
            RenameResult(
                source=dir_path,
                target=dir_path,
                item_type="directory",
                status="error",
                error_message="Directory does not exist",
            )
        ]

    normalized_extensions = (
        {ext.lower() if ext.startswith(".") else f".{ext.lower()}" for ext in extensions}
        if extensions
        else None
    )

    rename_map: Dict[str, str] = {}

    if not recursive:
        # NON-RECURSIVE: Only items directly present in dir_path
        entries = sorted(dir_path.iterdir(), key=lambda p: (p.is_dir(), p.name))
        
        # 1. Clean files first
        for item in entries:
            if item.name.startswith("."):
                continue
            if item.is_file():
                if normalized_extensions is not None:
                    _, ext = split_filename(item.name)
                    if ext not in normalized_extensions:
                        continue
                res = clean_file(
                    item,
                    mode=mode,
                    dry_run=dry_run,
                    separator=separator,
                    lowercase=lowercase,
                )
                results.append(res)
                if res.changed:
                    rename_map[res.source.name] = res.target.name

        # 2. Clean immediate subdirectories if requested
        if clean_dirs:
            for item in entries:
                if item.name.startswith("."):
                    continue
                if item.is_dir():
                    original_name = item.name
                    cleaned_name = sanitize_name(
                        original_name,
                        mode=mode,
                        separator=separator,
                        lowercase=lowercase,
                        is_dir=True,
                    )
                    if original_name == cleaned_name:
                        continue

                    candidate_target = item.parent / cleaned_name
                    final_target, had_collision = resolve_collision(candidate_target, item)
                    status = "collision_resolved" if had_collision else "renamed"

                    if not dry_run:
                        try:
                            item.rename(final_target)
                        except OSError as e:
                            results.append(
                                RenameResult(
                                    source=item,
                                    target=final_target,
                                    item_type="directory",
                                    status="error",
                                    error_message=str(e),
                                )
                            )
                            continue

                    res = RenameResult(
                        source=item,
                        target=final_target,
                        item_type="directory",
                        status=status,
                    )
                    results.append(res)
                    if res.changed:
                        rename_map[original_name] = final_target.name

    else:
        # RECURSIVE: Bottom-up traversal using os.walk
        for root, dirs, files in os.walk(dir_path, topdown=False):
            # Skip hidden directories
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            root_path = Path(root)

            # 1. Process files in current directory
            for f in sorted(files):
                if f.startswith("."):
                    continue
                file_path = root_path / f
                if normalized_extensions is not None:
                    _, ext = split_filename(f)
                    if ext not in normalized_extensions:
                        continue

                res = clean_file(
                    file_path,
                    mode=mode,
                    dry_run=dry_run,
                    separator=separator,
                    lowercase=lowercase,
                )
                results.append(res)
                if res.changed:
                    rename_map[res.source.name] = res.target.name

            # 2. Process directories in current directory
            if clean_dirs:
                for d in sorted(dirs):
                    dir_item = root_path / d
                    original_name = d
                    cleaned_name = sanitize_name(
                        original_name,
                        mode=mode,
                        separator=separator,
                        lowercase=lowercase,
                        is_dir=True,
                    )
                    if original_name == cleaned_name:
                        continue

                    candidate_target = root_path / cleaned_name
                    final_target, had_collision = resolve_collision(candidate_target, dir_item)
                    status = "collision_resolved" if had_collision else "renamed"

                    if not dry_run:
                        try:
                            dir_item.rename(final_target)
                        except OSError as e:
                            results.append(
                                RenameResult(
                                    source=dir_item,
                                    target=final_target,
                                    item_type="directory",
                                    status="error",
                                    error_message=str(e),
                                )
                            )
                            continue

                    res = RenameResult(
                        source=dir_item,
                        target=final_target,
                        item_type="directory",
                        status=status,
                    )
                    results.append(res)
                    if res.changed:
                        rename_map[original_name] = final_target.name

    # If any files were renamed and we're in SYNC mode, update markdown links
    if mode == CleanMode.SYNC and rename_map:
        update_markdown_links(dir_path, rename_map, recursive=recursive, dry_run=dry_run)

    return results


def update_markdown_links(
    dir_path: Path,
    rename_map: Dict[str, str],
    recursive: bool = False,
    dry_run: bool = False,
) -> int:
    """Updates markdown file links that reference renamed files."""
    if not rename_map or not dir_path.exists():
        return 0

    count_updated = 0
    md_files: List[Path] = []

    if recursive:
        for root, dirs, files in os.walk(dir_path):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for f in files:
                if f.endswith(".md"):
                    md_files.append(Path(root) / f)
    else:
        for item in dir_path.iterdir():
            if item.is_file() and item.name.endswith(".md"):
                md_files.append(item)

    for md_path in md_files:
        try:
            content = md_path.read_text(encoding="utf-8")
        except Exception:
            continue

        modified = False
        for old_name, new_name in rename_map.items():
            if old_name in content:
                content = content.replace(old_name, new_name)
                # Also handle URL-encoded representations (e.g. %20, %3A)
                old_encoded = old_name.replace(" ", "%20").replace(":", "%3A")
                new_encoded = new_name.replace(" ", "%20")
                content = content.replace(old_encoded, new_encoded)
                modified = True

        if modified:
            count_updated += 1
            if not dry_run:
                try:
                    md_path.write_text(content, encoding="utf-8")
                except Exception:
                    pass

    return count_updated
