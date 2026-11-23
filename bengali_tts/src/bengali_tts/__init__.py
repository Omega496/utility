"""
Bengali TTS (Text-to-Speech) using indic-speak via Google Colab CLI.
"""

from pathlib import Path
from typing import Dict, Any, List, Optional, Union

from bengali_tts.config import (
    DEFAULT_SESSION_NAME,
    DEFAULT_GPU,
    DEFAULT_SPEAKER,
    DEFAULT_STYLE,
    DEFAULT_OUTPUT_FORMAT,
    DEFAULT_TEMPERATURE,
    DEFAULT_TOP_P,
    DEFAULT_TOP_K,
    DEFAULT_MAX_NEW_TOKENS,
    DEFAULT_PAUSE_DURATION,
    MAX_CHUNK_LENGTH,
    SUPPORTED_SPEAKERS,
    SUPPORTED_STYLES,
)
from bengali_tts.text_utils import normalize_bengali_text, chunk_text, split_into_sentences
from bengali_tts.colab_client import BengaliTTSColabClient, ColabBengaliTTSError, HuggingFaceAccessError

__version__ = "1.0.0"


class BengaliTTS:
    """
    High-level interface for Bengali Text-to-Speech powered by bodhan-ai/indic-speak
    running remotely on Google Colab with GPU acceleration.
    """

    def __init__(
        self,
        session_name: str = DEFAULT_SESSION_NAME,
        gpu: str = DEFAULT_GPU,
        timeout: int = 900,
        verbose: bool = True,
    ):
        self.session_name = session_name
        self.gpu = gpu
        self.timeout = timeout
        self.verbose = verbose
        self.client = BengaliTTSColabClient(
            session_name=session_name,
            gpu=gpu,
            timeout=timeout,
            verbose=verbose,
        )

    def synthesize(
        self,
        text: str,
        output_path: Union[str, Path] = "output.opus",
        speaker: str = DEFAULT_SPEAKER,
        style: str = DEFAULT_STYLE,
        max_chunk_len: int = MAX_CHUNK_LENGTH,
        temperature: float = DEFAULT_TEMPERATURE,
        top_p: float = DEFAULT_TOP_P,
        top_k: int = DEFAULT_TOP_K,
        pause_duration: float = DEFAULT_PAUSE_DURATION,
        stop_session_after: bool = False,
    ) -> Dict[str, Any]:
        """
        Synthesizes speech from Bengali text.
        Splits long texts into manageable acoustic chunks, generates audio on Colab,
        and saves the audio locally.
        """
        clean_text = normalize_bengali_text(text)
        if not clean_text:
            raise ValueError("Input text is empty after normalization.")

        chunks = chunk_text(clean_text, max_chunk_len=max_chunk_len)
        if not chunks:
            raise ValueError("No valid sentences could be extracted from input text.")

        return self.client.synthesize(
            chunks=chunks,
            output_path=output_path,
            speaker=speaker,
            style=style,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            pause_duration=pause_duration,
            stop_session_after=stop_session_after,
        )

    def stop_session(self) -> bool:
        """Stops the Colab session VM."""
        return self.client.stop_session()

    def get_status(self) -> Dict[str, Any]:
        """Checks the Colab session status."""
        return self.client.get_status()

    @staticmethod
    def list_speakers() -> Dict[str, Dict[str, Any]]:
        """Returns the dictionary of supported voice speakers."""
        return SUPPORTED_SPEAKERS

    @staticmethod
    def list_styles() -> List[str]:
        """Returns the list of supported emotion styles."""
        return SUPPORTED_STYLES


def synthesize(
    text: str,
    output_path: Union[str, Path] = "output.opus",
    speaker: str = DEFAULT_SPEAKER,
    style: str = DEFAULT_STYLE,
    gpu: str = DEFAULT_GPU,
    session_name: str = DEFAULT_SESSION_NAME,
    stop_session_after: bool = False,
) -> Dict[str, Any]:
    """
    Convenience function for synthesizing Bengali audio in one line.
    """
    tts = BengaliTTS(session_name=session_name, gpu=gpu)
    return tts.synthesize(
        text=text,
        output_path=output_path,
        speaker=speaker,
        style=style,
        stop_session_after=stop_session_after,
    )


__all__ = [
    "BengaliTTS",
    "synthesize",
    "BengaliTTSColabClient",
    "ColabBengaliTTSError",
    "HuggingFaceAccessError",
    "normalize_bengali_text",
    "chunk_text",
    "split_into_sentences",
    "SUPPORTED_SPEAKERS",
    "SUPPORTED_STYLES",
]
