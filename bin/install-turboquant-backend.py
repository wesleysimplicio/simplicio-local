#!/usr/bin/env python3
"""Install Atomic's TurboQuant llama-server into the Local managed home."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from local_data_plane.turboquant_backend import TurboQuantBackendInstaller


parser = argparse.ArgumentParser()
parser.add_argument("--home", default=None)
parser.add_argument("--json", action="store_true")
args = parser.parse_args()

receipt = TurboQuantBackendInstaller(args.home).install()
if args.json:
    print(json.dumps(receipt, indent=2, sort_keys=True))
else:
    print(receipt["executable"])
