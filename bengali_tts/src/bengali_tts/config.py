"""
Configuration settings, voice mappings, and defaults for Bengali TTS (Indic-Speak).
"""

from typing import Dict, Any, List, Set

DEFAULT_MODEL_ID = "bodhan-ai/indic-speak"
DEFAULT_SESSION_NAME = "bengali-tts"
DEFAULT_GPU = "T4"
DEFAULT_SAMPLE_RATE = 24000
DEFAULT_OUTPUT_FORMAT = "opus"
DEFAULT_BITRATE = "24k"

SUPPORTED_EXTENSIONS: Set[str] = {".txt", ".md", ".markdown"}
IGNORE_FILENAMES: Set[str] = {"requirements.txt", "constraints.txt"}
SKIP_DIRECTORIES: Set[str] = {
    ".git", ".venv", "venv", "node_modules", "__pycache__",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", ".idea", ".vscode"
}

# Remote paths on the Colab VM
REMOTE_WORKDIR = "/content/bengali_tts"
REMOTE_MODEL_DIR = "/content/bengali_tts/indic_speak_model"
REMOTE_JOB_FILE = "/content/bengali_tts/job.json"
REMOTE_RESULT_FILE = "/content/bengali_tts/result.json"
REMOTE_OUTPUT_PREFIX = "/content/bengali_tts/output"

# Speakers supported by bodhan-ai/indic-speak
SUPPORTED_SPEAKERS: Dict[str, Dict[str, Any]] = {
    "Ishita": {
        "gender": "Female",
        "language": "Bengali",
        "native": True,
        "description": "Natural female voice, well suited for narration, educational reading, and audiobooks.",
    },
    "Sourav": {
        "gender": "Male",
        "language": "Bengali",
        "native": True,
        "description": "Clear male voice, well suited for instructional text, stories, and conversations.",
    },
    "Amit": {
        "gender": "Male",
        "language": "Hindi / English / Cross-lingual",
        "native": False,
        "description": "Male voice, handles mixed English/Bengali terminology.",
    },
    "Kavya": {
        "gender": "Female",
        "language": "Hindi / English / Cross-lingual",
        "native": False,
        "description": "Female voice, handles mixed English/Bengali terminology.",
    },
}

DEFAULT_SPEAKER = "Ishita"

SUPPORTED_STYLES: List[str] = [
    "NEUTRAL",
    "HAPPY",
    "SAD",
    "ANGER",
    "FEAR",
]

DEFAULT_STYLE = "NEUTRAL"

# Default generation parameters
DEFAULT_TEMPERATURE = 0.6
DEFAULT_TOP_P = 0.9
DEFAULT_TOP_K = 50
DEFAULT_MAX_NEW_TOKENS = 2520
DEFAULT_PAUSE_DURATION = 0.25  # seconds between chunks
MAX_CHUNK_LENGTH = 350  # maximum character count per text slice (optimal for ~20s speech)
