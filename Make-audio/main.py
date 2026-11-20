#!/usr/bin/env python3
"""
Root entry point for make_audio.
Usage:
    python main.py [targets...] [options]
    make_audio [targets...] [options]
"""

import sys
from pathlib import Path

# Add src to python path
src_dir = Path(__file__).resolve().parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from pdf.md_to_audio import main

if __name__ == "__main__":
    main()
