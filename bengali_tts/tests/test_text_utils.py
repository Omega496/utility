"""
Unit tests for bengali_tts text preprocessing and chunking.
"""

import unittest
from bengali_tts.text_utils import (
    normalize_bengali_text,
    split_into_sentences,
    chunk_text,
)
from bengali_tts.config import SUPPORTED_SPEAKERS, SUPPORTED_STYLES, DEFAULT_SPEAKER


class TestBengaliTTS(unittest.TestCase):

    def test_normalize_bengali_text(self):
        raw = "## শিরোনাম\n**আমার** সোনার বাংলা, [গান](https://example.com) আমি তোমায় ভালোবাসি! ||"
        cleaned = normalize_bengali_text(raw)
        self.assertNotIn("##", cleaned)
        self.assertNotIn("**", cleaned)
        self.assertNotIn("https://", cleaned)
        self.assertIn("সোনার বাংলা", cleaned)
        self.assertIn("॥", cleaned)

    def test_split_into_sentences(self):
        text = "আমি বাংলায় গান গাই। তুমি বাংলায় কথা বলো? হ্যাঁ, অবশ্যই!"
        sentences = split_into_sentences(text)
        self.assertEqual(len(sentences), 3)
        self.assertEqual(sentences[0], "আমি বাংলায় গান গাই।")
        self.assertEqual(sentences[1], "তুমি বাংলায় কথা বলো?")
        self.assertEqual(sentences[2], "হ্যাঁ, অবশ্যই!")

    def test_chunk_text_grouping(self):
        text = "প্রথম বাক্য। দ্বিতীয় বাক্য। তৃতীয় বাক্য।"
        # When max_chunk_len is large, they should be grouped together
        chunks = chunk_text(text, max_chunk_len=100)
        self.assertEqual(len(chunks), 1)
        self.assertIn("প্রথম বাক্য।", chunks[0])
        self.assertIn("তৃতীয় বাক্য।", chunks[0])

    def test_chunk_text_splitting(self):
        text = "প্রথম বাক্য। দ্বিতীয় বাক্য। তৃতীয় বাক্য।"
        # When max_chunk_len is small, they should be split
        chunks = chunk_text(text, max_chunk_len=20)
        self.assertGreaterEqual(len(chunks), 3)

    def test_speakers_and_styles(self):
        self.assertIn("Ishita", SUPPORTED_SPEAKERS)
        self.assertIn("Sourav", SUPPORTED_SPEAKERS)
        self.assertEqual(DEFAULT_SPEAKER, "Ishita")
        self.assertTrue(SUPPORTED_SPEAKERS["Ishita"]["native"])
        self.assertTrue(SUPPORTED_SPEAKERS["Sourav"]["native"])
        self.assertIn("NEUTRAL", SUPPORTED_STYLES)
        self.assertIn("HAPPY", SUPPORTED_STYLES)


if __name__ == "__main__":
    unittest.main()
