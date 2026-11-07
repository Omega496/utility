#!/usr/bin/env python3
"""
Root entry point for make_opus converter.
Usage:
    make_opus <file>
    make_opus .
    make_opus -r
"""

import sys
from pathlib import Path

# Add src to python path
src_dir = Path(__file__).resolve().parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from pdf.make_opus import main

if __name__ == "__main__":
    main()
