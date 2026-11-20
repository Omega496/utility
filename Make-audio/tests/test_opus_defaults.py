import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from pdf.md_to_audio import main, parse_args


def test_default_format_and_engine():
    """Verify that default output format is opus at 24k and default engine is edge."""
    with patch("sys.argv", ["make-audio", "dummy.md"]):
        args = parse_args()
        assert args.format == "opus"
        assert args.bitrate == "24k"
        assert args.engine == "edge"


def test_engine_flags():
    """Verify that --colab and --local flags set engine properly."""
    with patch("sys.argv", ["make-audio", "dummy.md", "--local"]):
        args = parse_args()
        assert args.local is True
    with patch("sys.argv", ["make-audio", "dummy.md", "--colab"]):
        args = parse_args()
        assert args.colab is True


def test_bitrate_override():
    """Verify that --bitrate flag overrides the default."""
    with patch("sys.argv", ["make-audio", "dummy.md", "--bitrate", "32k"]):
        args = parse_args()
        assert args.bitrate == "32k"


def test_default_file_output_path_has_opus_extension():
    """Verify that converting a file without -o generates a .opus file next to input."""
    with tempfile.TemporaryDirectory() as tmpdir:
        input_file = Path(tmpdir) / "notes.md"
        input_file.write_text("# Test\nSample text content.", encoding="utf-8")

        async def mock_edge_synthesize(*args, **kwargs):
            out_p = kwargs.get("output_path") or args[1]
            out_p.write_bytes(b"dummyopusdata")
            return out_p, "en-US-AriaNeural", "en"

        with patch("sys.argv", ["make-audio", str(input_file)]), \
             patch("pdf.md_to_audio.synthesize_edge_tts", side_effect=mock_edge_synthesize):
            main()

        expected_opus = input_file.with_suffix(".opus")
        assert expected_opus.exists(), "Default .opus output file was not created!"


def test_batch_dir_output_has_opus_extension():
    """Verify that batch converting a directory defaults each file to .opus."""
    with tempfile.TemporaryDirectory() as tmpdir:
        dir_path = Path(tmpdir) / "docs"
        dir_path.mkdir()
        (dir_path / "doc1.md").write_text("Text 1", encoding="utf-8")
        (dir_path / "doc2.md").write_text("Text 2", encoding="utf-8")

        generated_suffixes = []

        async def mock_edge_synthesize(*args, **kwargs):
            out_p = kwargs.get("output_path") or args[1]
            generated_suffixes.append(out_p.suffix)
            out_p.write_bytes(b"dummydata")
            return out_p, "en-US-AriaNeural", "en"

        with patch("sys.argv", ["make-audio", str(dir_path)]), \
             patch("pdf.md_to_audio.synthesize_edge_tts", side_effect=mock_edge_synthesize):
            main()

        assert len(generated_suffixes) == 2
        assert all(s == ".opus" for s in generated_suffixes), f"Expected all .opus, got: {generated_suffixes}"


def test_explicit_format_override():
    """Verify that explicit -o output.wav or -o output.mp3 is respected."""
    with tempfile.TemporaryDirectory() as tmpdir:
        input_file = Path(tmpdir) / "notes.md"
        input_file.write_text("Hello world", encoding="utf-8")
        out_wav = Path(tmpdir) / "custom.wav"

        async def mock_edge_synthesize(*args, **kwargs):
            out_p = kwargs.get("output_path") or args[1]
            assert out_p == out_wav
            out_p.write_bytes(b"dummywav")
            return out_p, "en-US-AriaNeural", "en"

        with patch("sys.argv", ["make-audio", str(input_file), "-o", str(out_wav)]), \
             patch("pdf.md_to_audio.synthesize_edge_tts", side_effect=mock_edge_synthesize):
            main()

        assert out_wav.exists()


def test_make_audio_dot_with_cleaned_files(monkeypatch):
    """Verify that 'make_audio .' discovers and processes _cleaned.md files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        doc_dir = Path(tmpdir)
        (doc_dir / "chapter_01_cleaned.md").write_text("# Chapter 1\nSome text.", encoding="utf-8")
        (doc_dir / "chapter_02_cleaned.md").write_text("# Chapter 2\nMore text.", encoding="utf-8")

        monkeypatch.chdir(doc_dir)

        processed = []

        async def mock_edge_synthesize(*args, **kwargs):
            out_p = kwargs.get("output_path") or args[1]
            processed.append(out_p.name)
            out_p.write_bytes(b"dummydata")
            return out_p, "en-US-AriaNeural", "en"

        with patch("sys.argv", ["make-audio", "."]), \
             patch("pdf.md_to_audio.synthesize_edge_tts", side_effect=mock_edge_synthesize):
            main()

        assert len(processed) == 2
        assert "chapter_01_cleaned.opus" in processed
        assert "chapter_02_cleaned.opus" in processed


def test_make_audio_dot_colab_batch(monkeypatch):
    """Verify that 'make_audio . --colab' processes all files remotely on Colab."""
    with tempfile.TemporaryDirectory() as tmpdir:
        doc_dir = Path(tmpdir)
        (doc_dir / "section1_cleaned.md").write_text("Colab section 1", encoding="utf-8")
        (doc_dir / "section2_cleaned.md").write_text("Colab section 2", encoding="utf-8")

        monkeypatch.chdir(doc_dir)

        colab_calls = []

        def mock_convert(text, output_path, voice, speed, stop_session_after, bitrate):
            out_p = Path(output_path)
            colab_calls.append(out_p.name)
            out_p.write_bytes(b"colab_opus_data")
            return out_p

        with patch("sys.argv", ["make-audio", ".", "--colab"]), \
             patch("pdf.colab_tts.ColabTTS.convert_to_audio_file", side_effect=mock_convert), \
             patch("pdf.colab_tts.ColabTTS.stop_session") as mock_stop:
            main()

        assert len(colab_calls) == 2
        assert "section1_cleaned.opus" in colab_calls
        assert "section2_cleaned.opus" in colab_calls
        mock_stop.assert_called_once()


def test_make_audio_deduplicates_cleaned_pair(monkeypatch):
    """When both notes.md and notes_cleaned.md exist, prefer notes_cleaned.md without duplicates."""
    with tempfile.TemporaryDirectory() as tmpdir:
        doc_dir = Path(tmpdir)
        (doc_dir / "notes.md").write_text("Uncleaned raw notes", encoding="utf-8")
        (doc_dir / "notes_cleaned.md").write_text("Cleaned plain text notes", encoding="utf-8")

        monkeypatch.chdir(doc_dir)

        converted_names = []

        async def mock_edge_synthesize(*args, **kwargs):
            out_p = kwargs.get("output_path") or args[1]
            converted_names.append(out_p.name)
            out_p.write_bytes(b"data")
            return out_p, "en-US-AriaNeural", "en"

        with patch("sys.argv", ["make-audio", "."]), \
             patch("pdf.md_to_audio.synthesize_edge_tts", side_effect=mock_edge_synthesize):
            main()

        assert converted_names == ["notes_cleaned.opus"], f"Expected only notes_cleaned.opus, got: {converted_names}"


def test_make_audio_no_args_defaults_to_dot(monkeypatch):
    """Running 'make-audio' without arguments in a directory with files defaults to '.'."""
    with tempfile.TemporaryDirectory() as tmpdir:
        doc_dir = Path(tmpdir)
        (doc_dir / "auto.md").write_text("Auto content", encoding="utf-8")

        monkeypatch.chdir(doc_dir)

        converted_names = []

        async def mock_edge_synthesize(*args, **kwargs):
            out_p = kwargs.get("output_path") or args[1]
            converted_names.append(out_p.name)
            out_p.write_bytes(b"data")
            return out_p, "en-US-AriaNeural", "en"

        with patch("sys.argv", ["make-audio"]), \
             patch("pdf.md_to_audio.synthesize_edge_tts", side_effect=mock_edge_synthesize):
            main()

        assert converted_names == ["auto.opus"]
