#!/usr/bin/env python3
"""
Root entry point for bengali_tts.
Usage:
    python main.py [args...]
"""

import sys
from pathlib import Path

# Add src to sys.path
src_dir = Path(__file__).resolve().parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from bengali_tts.cli import main

if __name__ == "__main__":
    main()
