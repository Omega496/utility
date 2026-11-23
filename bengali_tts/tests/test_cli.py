"""
Tests for file discovery and batch targets in make_bengali_audio.
"""

import pathlib
import tempfile
import unittest

from bengali_tts.cli import discover_files


class TestFileDiscovery(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp_dir.name)

        # Create files
        (self.root / "file1.md").write_text("প্রথম লেখা", encoding="utf-8")
        (self.root / "file2.txt").write_text("দ্বিতীয় লেখা", encoding="utf-8")
        (self.root / "ignored.pdf").write_text("binary", encoding="utf-8")
        (self.root / "requirements.txt").write_text("pip requirements", encoding="utf-8")

        # Subdirectory
        sub = self.root / "subfolder"
        sub.mkdir()
        (sub / "sub1.md").write_text("সাবফোল্ডার লেখা", encoding="utf-8")

        # Hidden directory
        hidden = self.root / ".git"
        hidden.mkdir()
        (hidden / "hidden.md").write_text("hidden", encoding="utf-8")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_single_file_discovery(self):
        target = self.root / "file1.md"
        res = discover_files([str(target)], recursive=False)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0].name, "file1.md")

    def test_current_dir_non_recursive(self):
        res = discover_files([str(self.root)], recursive=False)
        names = {f.name for f in res}
        self.assertIn("file1.md", names)
        self.assertIn("file2.txt", names)
        self.assertNotIn("sub1.md", names)
        self.assertNotIn("ignored.pdf", names)
        self.assertNotIn("requirements.txt", names)
        self.assertNotIn("hidden.md", names)
        self.assertEqual(len(res), 2)

    def test_recursive_discovery(self):
        res = discover_files([str(self.root)], recursive=True)
        names = {f.name for f in res}
        self.assertIn("file1.md", names)
        self.assertIn("file2.txt", names)
        self.assertIn("sub1.md", names)
        self.assertNotIn("ignored.pdf", names)
        self.assertNotIn("requirements.txt", names)
        self.assertNotIn("hidden.md", names)
        self.assertEqual(len(res), 3)


if __name__ == "__main__":
    unittest.main()
