#!/usr/bin/env python3
"""Quick run script for Instagram Saved Posts Scraper."""

import sys
from pathlib import Path

# Add src to path for direct execution
sys.path.insert(0, str(Path(__file__).parent / "src"))

from instagram_scraper.cli import main

if __name__ == "__main__":
    main()
