import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import soundfile as sf
import pytest

from pdf.md_to_audio import main, parse_args
from pdf.tts import KokoroTTS


def test_default_format_is_opus():
    """Verify that default output format argument is opus with 24k bitrate."""
    with patch("sys.argv", ["make-audio", "dummy.md"]):
        args = parse_args()
        assert args.format == "opus"
        assert args.bitrate == "24k"


def test_bitrate_override():
    """Verify that --bitrate flag overrides the default."""
    with patch("sys.argv", ["make-audio", "dummy.md", "--bitrate", "32k"]):
        args = parse_args()
        assert args.bitrate == "32k"


def test_default_file_output_path_has_opus_extension():
    """Verify that converting a file without -o generates a .opus file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        input_file = Path(tmpdir) / "notes.md"
        input_file.write_text("# Test\nSample text content.", encoding="utf-8")

        def mock_synthesize(args, cleaned_text, output_audio_path):
            assert output_audio_path.suffix == ".opus"
            output_audio_path.write_bytes(b"dummyopusdata")
            return output_audio_path

        with patch("sys.argv", ["make-audio", str(input_file)]), \
             patch("pdf.md_to_audio._run_local_synthesis", side_effect=mock_synthesize):
            main()

        expected_opus = Path.cwd() / "notes.opus"
        assert expected_opus.exists(), "Default .opus output file was not created!"
        expected_opus.unlink(missing_ok=True)


def test_batch_dir_output_has_opus_extension():
    """Verify that batch converting a directory defaults each file to .opus."""
    with tempfile.TemporaryDirectory() as tmpdir:
        dir_path = Path(tmpdir) / "docs"
        dir_path.mkdir()
        (dir_path / "doc1.md").write_text("Text 1", encoding="utf-8")
        (dir_path / "doc2.md").write_text("Text 2", encoding="utf-8")

        generated_suffixes = []

        def mock_synthesize(args, cleaned_text, output_audio_path):
            generated_suffixes.append(output_audio_path.suffix)
            output_audio_path.write_bytes(b"dummydata")
            return output_audio_path

        with patch("sys.argv", ["make-audio", str(dir_path)]), \
             patch("pdf.md_to_audio._run_local_synthesis", side_effect=mock_synthesize):
            main()

        assert len(generated_suffixes) == 2
        assert all(s == ".opus" for s in generated_suffixes), f"Expected all .opus, got: {generated_suffixes}"

        # Clean up any created files in cwd
        (Path.cwd() / "doc1.opus").unlink(missing_ok=True)
        (Path.cwd() / "doc2.opus").unlink(missing_ok=True)


def test_explicit_format_override():
    """Verify that explicit -o output.wav or -o output.mp3 is respected."""
    with tempfile.TemporaryDirectory() as tmpdir:
        input_file = Path(tmpdir) / "notes.md"
        input_file.write_text("Hello world", encoding="utf-8")
        out_wav = Path(tmpdir) / "custom.wav"

        def mock_synthesize(args, cleaned_text, output_audio_path):
            assert output_audio_path == out_wav
            output_audio_path.write_bytes(b"dummywav")
            return output_audio_path

        with patch("sys.argv", ["make-audio", str(input_file), "-o", str(out_wav)]), \
             patch("pdf.md_to_audio._run_local_synthesis", side_effect=mock_synthesize):
            main()

        assert out_wav.exists()
