"""Unit tests for clean core functionality and CLI."""

import io
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from clean.cleaner import (
    CleanMode,
    clean_directory,
    clean_file,
    resolve_collision,
    sanitize_filename_kaggle,
    sanitize_name_sync,
    split_filename,
    update_markdown_links,
)
from clean.cli import main


class TestClean(unittest.TestCase):
    def test_split_filename(self):
        self.assertEqual(split_filename("file.pdf"), ("file", ".pdf"))
        self.assertEqual(split_filename("UPPER.PDF"), ("UPPER", ".pdf"))
        self.assertEqual(split_filename("multi.dot.name.txt"), ("multi.dot.name", ".txt"))
        self.assertEqual(split_filename("archive.tar.gz"), ("archive", ".tar.gz"))
        self.assertEqual(split_filename("no_ext"), ("no_ext", ""))

    def test_sanitize_kaggle_mode(self):
        cases = [
            ("My Document [Lecture 1] (Final).pdf", "My_Document_Lecture_1_Final.pdf"),
            ("Chapter 1: Deep Learning & AI.pdf", "Chapter_1_Deep_Learning_AI.pdf"),
            ("100% Guaranteed $Profit?.pdf", "100_Guaranteed_Profit.pdf"),
            ("Notes.2024.final.PDF", "Notes_2024_final.pdf"),
            ("   spaced   name  .pdf", "spaced_name.pdf"),
            ("résumé 2024.txt", "resume_2024.txt"),
            ("podcast sample [raw].opus", "podcast_sample_raw.opus"),
        ]
        for original, expected in cases:
            with self.subTest(original=original):
                self.assertEqual(sanitize_filename_kaggle(original), expected)

    def test_sanitize_sync_mode(self):
        cases = [
            ("Neural Networks: Zero to Hero", "Neural Networks - Zero to Hero"),
            ("Let's build GPT: from scratch.md", "Let's build GPT - from scratch.md"),
            ("navigating the ", "navigating the"),
            ("Automatic Differentiation .md", "Automatic Differentiation.md"),
            ("File | With | Pipes.txt", "File - With - Pipes.txt"),
            ("Quotes \"Inside\" Title.pdf", "Quotes 'Inside' Title.pdf"),
            ("Question? Mark.opus", "Question Mark.opus"),
            ("File\nWith\nNewlines.md", "File With Newlines.md"),
        ]
        for original, expected in cases:
            with self.subTest(original=original):
                is_dir = not Path(original).suffix or original.endswith(" ")
                self.assertEqual(sanitize_name_sync(original, is_dir=is_dir), expected)

    def test_clean_file_sync_mode(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            f1 = tmppath / "Video 1: Autograd & Micrograd.md"
            f1.write_text("notes")

            res = clean_file(f1, mode=CleanMode.SYNC)
            self.assertEqual(res.status, "renamed")
            self.assertFalse(f1.exists())
            expected = tmppath / "Video 1 - Autograd & Micrograd.md"
            self.assertTrue(expected.exists())

    def test_clean_file_dry_run(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            f = tmppath / "Uncleaned Name: Test.pdf"
            f.write_text("dummy")

            res = clean_file(f, mode=CleanMode.SYNC, dry_run=True)
            self.assertEqual(res.status, "renamed")
            self.assertTrue(f.exists())
            self.assertFalse((tmppath / "Uncleaned Name - Test.pdf").exists())

    def test_collision_handling(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            existing = tmppath / "Data_File_1.txt"
            existing.write_text("existing")

            f = tmppath / "Data File (1).txt"
            f.write_text("new")

            res = clean_file(f, mode=CleanMode.KAGGLE)
            self.assertEqual(res.status, "collision_resolved")
            self.assertEqual(res.target.name, "Data_File_1_1.txt")
            self.assertTrue((tmppath / "Data_File_1_1.txt").exists())
            self.assertTrue(existing.exists())

    def test_clean_directory_sync_with_subdirs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            # Create a directory with colon
            d1 = tmppath / "Lecture: Part 1 "
            d1.mkdir()
            (d1 / "Notes: Intro.md").write_text("hello")

            # Recursive cleaning
            results = clean_directory(tmppath, mode=CleanMode.SYNC, recursive=True)
            renamed_targets = {r.target.name for r in results if r.status == "renamed"}

            self.assertIn("Lecture - Part 1", renamed_targets)
            self.assertIn("Notes - Intro.md", renamed_targets)

            clean_dir = tmppath / "Lecture - Part 1"
            self.assertTrue(clean_dir.exists())
            self.assertTrue((clean_dir / "Notes - Intro.md").exists())

    def test_markdown_link_updating(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            note_file = tmppath / "Karpathy: GPT.md"
            note_file.write_text("Sample")

            hub = tmppath / "Hub.md"
            hub.write_text("Check [Karpathy GPT](Karpathy:%20GPT.md) or [[Karpathy: GPT.md]]")

            results = clean_directory(tmppath, mode=CleanMode.SYNC)
            hub_content = hub.read_text()
            self.assertIn("Karpathy - GPT.md", hub_content)
            self.assertNotIn("Karpathy: GPT.md", hub_content)

    def test_cli_execution_sync(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            test_file = tmppath / "CLI Test: File.md"
            test_file.write_text("cli test")

            buf = io.StringIO()
            with redirect_stdout(buf):
                exit_code = main([str(test_file), "--no-color"])

            self.assertEqual(exit_code, 0)
            self.assertFalse(test_file.exists())
            self.assertTrue((tmppath / "CLI Test - File.md").exists())
            self.assertIn("CLI Test - File.md", buf.getvalue())

    def test_cli_execution_kaggle(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            test_file = tmppath / "My Document [Lecture 1].pdf"
            test_file.write_text("kaggle test")

            buf = io.StringIO()
            with redirect_stdout(buf):
                exit_code = main([str(test_file), "-k", "--no-color"])

            self.assertEqual(exit_code, 0)
            self.assertFalse(test_file.exists())
            self.assertTrue((tmppath / "My_Document_Lecture_1.pdf").exists())


if __name__ == "__main__":
    unittest.main()
