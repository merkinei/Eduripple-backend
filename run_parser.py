#!/usr/bin/env python
"""Run the CBC curriculum parser.

This is a convenience wrapper for running the cbc_parser package.

Usage:
    python run_parser.py                    # Parse all PDFs
    python run_parser.py --clear            # Clear DB and re-parse
    python run_parser.py --verbose          # Verbose output
    python run_parser.py --workers 8        # Use 8 parallel workers
"""

import sys
from pathlib import Path

# Add parent directory to path if needed
sys.path.insert(0, str(Path(__file__).parent))

from cbc_parser.main import main

if __name__ == "__main__":
    main()
