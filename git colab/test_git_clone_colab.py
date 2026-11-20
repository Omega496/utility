#!/usr/bin/env python3
"""
Unit tests for git_clone_colab.
"""

import os
import tempfile
import unittest
import zipfile

from git_clone_colab import (
    parse_repo_name,
    format_bytes,
    build_parser,
    ColabCloner,
)


class TestGitCloneColab(unittest.TestCase):
    def test_parse_repo_name_https(self):
        self.assertEqual(parse_repo_name("https://github.com/torvalds/linux.git"), "linux")
        self.assertEqual(parse_repo_name("https://github.com/torvalds/linux/"), "linux")
        self.assertEqual(parse_repo_name("https://github.com/torvalds/linux"), "linux")

    def test_parse_repo_name_ssh(self):
        self.assertEqual(parse_repo_name("git@github.com:huggingface/transformers.git"), "transformers")
        self.assertEqual(parse_repo_name("git@gitlab.com:group/subgroup/project.git"), "project")

    def test_parse_repo_name_special_characters(self):
        self.assertEqual(parse_repo_name("https://github.com/user/my-cool_repo.v2.git"), "my-cool_repo.v2")

    def test_format_bytes(self):
        self.assertEqual(format_bytes(500), "500.00 B")
        self.assertEqual(format_bytes(1024), "1.00 KB")
        self.assertEqual(format_bytes(1024 * 1024), "1.00 MB")
        self.assertEqual(format_bytes(1024 * 1024 * 1024 * 2.5), "2.50 GB")

    def test_parser_defaults(self):
        parser = build_parser()
        args = parser.parse_args(["https://github.com/octocat/Hello-World"])
        self.assertEqual(args.repo_link, "https://github.com/octocat/Hello-World")
        self.assertEqual(args.output_dir, ".")
        self.assertIsNone(args.depth)
        self.assertFalse(args.extract)
        self.assertFalse(args.no_git)

    def test_parser_custom_options(self):
        parser = build_parser()
        args = parser.parse_args([
            "https://github.com/octocat/Hello-World.git",
            "-o", "/tmp/output",
            "-n", "custom_hello",
            "-b", "develop",
            "--depth", "1",
            "--submodules",
            "--no-git",
            "-x",
            "--remove-zip",
            "-s", "my-session",
            "--keep-session",
            "--gpu", "T4",
            "--high-mem",
            "--timeout", "600"
        ])
        self.assertEqual(args.repo_link, "https://github.com/octocat/Hello-World.git")
        self.assertEqual(args.output_dir, "/tmp/output")
        self.assertEqual(args.name, "custom_hello")
        self.assertEqual(args.branch, "develop")
        self.assertEqual(args.depth, 1)
        self.assertTrue(args.submodules)
        self.assertTrue(args.no_git)
        self.assertTrue(args.extract)
        self.assertTrue(args.remove_zip)
        self.assertEqual(args.session, "my-session")
        self.assertTrue(args.keep_session)
        self.assertEqual(args.gpu, "T4")
        self.assertTrue(args.high_mem)
        self.assertEqual(args.timeout, 600.0)

    def test_safe_extraction(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = os.path.join(tmpdir, "test.zip")
            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.writestr("test_repo/hello.txt", "hello world")

            cloner = ColabCloner(
                repo_url="https://github.com/example/test_repo",
                output_dir=tmpdir,
                extract=True,
                remove_zip=False
            )
            cloner.local_zip = zip_path
            cloner.local_extract_dir = os.path.join(tmpdir, "test_repo")
            cloner.extract_zip()

            extracted_file = os.path.join(tmpdir, "test_repo", "hello.txt")
            self.assertTrue(os.path.exists(extracted_file))
            with open(extracted_file) as f:
                self.assertEqual(f.read(), "hello world")


if __name__ == "__main__":
    unittest.main()
