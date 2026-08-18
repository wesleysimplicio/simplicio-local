#!/usr/bin/env python3
"""Launch the Simplicio Local private inference daemon."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from local_data_plane.daemon import main


if __name__ == "__main__":
    raise SystemExit(main())
