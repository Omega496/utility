"""
Text preprocessing and sentence-chunking utilities for Bengali Text-to-Speech.
Handles Bengali Unicode normalization, markdown cleanup, and natural punctuation-based splitting.
"""

import re
import unicodedata
from typing import List


def normalize_bengali_text(text: str) -> str:
    """
    Normalizes Bengali text:
    - Normalizes Unicode representations (NFKC).
    - Standardizes various Bengali and ASCII punctuation marks.
    - Strips markdown formatting (headers, bold, italics, code blocks, links).
    - Cleans up excessive whitespace and control characters.
    """
    if not text:
        return ""

    # Unicode normalization
    text = unicodedata.normalize("NFKC", text)

    # Remove markdown links: [text](url) -> text
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    # Remove raw URLs
    text = re.sub(r"https?://\S+", "", text)
    # Remove code fences and inline code
    text = re.sub(r"```[\s\S]*?```", "", text)
    text = re.sub(r"`[^`]+`", "", text)
    # Remove markdown headers and list bullets
    text = re.sub(r"^\s*[#*+->]+\s*", "", text, flags=re.MULTILINE)
    # Remove bold/italic markers
    text = re.sub(r"[*_~]+", "", text)

    # Standardize Bengali punctuation
    # Replace alternative dari-like characters with standard Bengali dari U+0964
    text = text.replace("||", "॥")
    text = text.replace("|", "।")

    # Replace multiple question marks / exclamation marks with single
    text = re.sub(r"\?+", "?", text)
    text = re.sub(r"!+", "!", text)
    text = re.sub(r"।+", "।", text)

    # Normalize whitespace
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def split_into_sentences(text: str) -> List[str]:
    """
    Splits Bengali text into individual sentences based on standard delimiters:
    '।' (Bengali dari), '॥', '?', '!', and newline boundaries.
    Preserves punctuation with each sentence.
    """
    normalized = normalize_bengali_text(text)
    if not normalized:
        return []

    # Regex pattern to capture sentences along with their terminators
    # Terminators: [।॥?!] or newline
    pattern = r"([^।॥?!\n]+[।॥?!]?)"
    raw_segments = re.findall(pattern, normalized)

    sentences: List[str] = []
    for seg in raw_segments:
        s = seg.strip()
        if s:
            sentences.append(s)

    return sentences


def chunk_text(text: str, max_chunk_len: int = 200) -> List[str]:
    """
    Chunks Bengali text into units suitable for TTS inference.
    - Groups consecutive short sentences together without exceeding `max_chunk_len`.
    - Splits overly long sentences by secondary delimiters (commas, semicolons, dashes)
      or whitespace to ensure no chunk exceeds `max_chunk_len`.
    """
    sentences = split_into_sentences(text)
    if not sentences:
        return []

    chunks: List[str] = []
    current_chunk = ""

    for sentence in sentences:
        # If the sentence itself is larger than max_chunk_len, split it by secondary punctuation
        if len(sentence) > max_chunk_len:
            # First, flush whatever was in current_chunk
            if current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = ""

            sub_chunks = _split_long_sentence(sentence, max_chunk_len)
            for sub in sub_chunks:
                if sub:
                    chunks.append(sub.strip())
            continue

        # Check if adding sentence exceeds max_chunk_len
        candidate = f"{current_chunk} {sentence}".strip() if current_chunk else sentence
        if len(candidate) <= max_chunk_len:
            current_chunk = candidate
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = sentence

    if current_chunk:
        chunks.append(current_chunk.strip())

    return [c for c in chunks if c]


def _split_long_sentence(sentence: str, max_chunk_len: int) -> List[str]:
    """
    Splits an unusually long sentence into pieces <= max_chunk_len using secondary breaks.
    """
    # Try splitting by comma, semicolon, dash, colon
    parts = re.split(r"([,;:\-–—]\s*)", sentence)
    result: List[str] = []
    curr = ""

    for part in parts:
        if not part:
            continue
        if len(curr) + len(part) <= max_chunk_len:
            curr += part
        else:
            if curr.strip():
                result.append(curr.strip())
            # If a single part exceeds max_chunk_len, break by whitespace words
            if len(part) > max_chunk_len:
                words = part.split()
                sub_curr = ""
                for w in words:
                    if len(sub_curr) + len(w) + 1 <= max_chunk_len:
                        sub_curr = f"{sub_curr} {w}".strip()
                    else:
                        if sub_curr:
                            result.append(sub_curr)
                        sub_curr = w
                curr = sub_curr
            else:
                curr = part

    if curr.strip():
        result.append(curr.strip())

    return result
