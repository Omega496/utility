import tempfile
import json
import base64
from pathlib import Path
from unittest.mock import patch

import pytest

from pdf.make_opus import (
    is_gdocs_tts_txt,
    extract_gdocs_audio_bytes,
    collect_target_files,
    convert_single_file,
    main,
)


def test_is_gdocs_tts_txt():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Valid gdocs txt
        gdocs_file = Path(tmpdir) / "gdocs.txt"
        gdocs_file.write_text(")]}'\n[\"generate_tts_response\", null, \"dummyb64\"]", encoding="utf-8")
        assert is_gdocs_tts_txt(gdocs_file) is True

        # Plain txt
        plain_file = Path(tmpdir) / "plain.txt"
        plain_file.write_text("This is just a normal text note.", encoding="utf-8")
        assert is_gdocs_tts_txt(plain_file) is False

        # Non-txt file
        md_file = Path(tmpdir) / "doc.md"
        md_file.write_text("Markdown text", encoding="utf-8")
        assert is_gdocs_tts_txt(md_file) is False


def test_extract_gdocs_audio_bytes():
    with tempfile.TemporaryDirectory() as tmpdir:
        test_bytes = b"ID3v2fakemp3bytes"
        b64_str = base64.b64encode(test_bytes).decode("ascii")

        gdocs_file = Path(tmpdir) / "response.txt"
        gdocs_content = f")]}}'\n[\"generate_tts_response\", null, \"{b64_str}\"]"
        gdocs_file.write_text(gdocs_content, encoding="utf-8")

        extracted = extract_gdocs_audio_bytes(gdocs_file)
        assert extracted == test_bytes


def test_collect_target_files_batch_and_recursive():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        sub = root / "subfolder"
        sub.mkdir()

        (root / "song1.mp3").write_bytes(b"dummy")
        (root / "song2.wav").write_bytes(b"dummy")
        (root / "plain.txt").write_text("normal text", encoding="utf-8")
        (root / "gdocs.txt").write_text(")]}'\n[\"generate_tts_response\", null, \"xxx\"]", encoding="utf-8")
        (sub / "nested.flac").write_bytes(b"dummy")

        # Non-recursive
        files_flat = collect_target_files(root, recursive=False)
        flat_names = {f.name for f in files_flat}
        assert "song1.mp3" in flat_names
        assert "song2.wav" in flat_names
        assert "gdocs.txt" in flat_names
        assert "plain.txt" not in flat_names
        assert "nested.flac" not in flat_names

        # Recursive
        files_rec = collect_target_files(root, recursive=True)
        rec_names = {f.name for f in files_rec}
        assert "nested.flac" in rec_names
        assert "song1.mp3" in rec_names
        assert "plain.txt" not in rec_names


def test_make_opus_cli_single_and_batch_args():
    with patch("sys.argv", ["make_opus", "dummy.mp3"]), \
         patch("pdf.make_opus.convert_single_file") as mock_conv, \
         patch("pathlib.Path.exists", return_value=True), \
         patch("pathlib.Path.is_file", return_value=True):
        mock_conv.return_value = {
            "status": "success",
            "src": Path("dummy.mp3"),
            "dest": Path("dummy.opus"),
            "orig_size": 1000,
            "new_size": 200,
            "msg": "Converted",
        }
        main()
        assert mock_conv.called
        # Verify delete_source=True was passed by default
        assert mock_conv.call_args.kwargs["delete_source"] is True


def test_make_opus_cli_keep_flag():
    with patch("sys.argv", ["make_opus", "dummy.mp3", "--keep"]), \
         patch("pdf.make_opus.convert_single_file") as mock_conv, \
         patch("pathlib.Path.exists", return_value=True), \
         patch("pathlib.Path.is_file", return_value=True):
        mock_conv.return_value = {
            "status": "success",
            "src": Path("dummy.mp3"),
            "dest": Path("dummy.opus"),
            "orig_size": 1000,
            "new_size": 200,
            "msg": "Converted",
        }
        main()
        assert mock_conv.called
        # Verify delete_source=False was passed when --keep is used
        assert mock_conv.call_args.kwargs["delete_source"] is False
