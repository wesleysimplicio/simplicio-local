#!/usr/bin/env python3
"""Install a validated Simplicio Local package outside the checkout."""

import argparse

from local_data_plane.distribution import LocalInstaller


parser = argparse.ArgumentParser()
parser.add_argument("package")
parser.add_argument("destination")
parser.add_argument("--runtime-protocol", type=int, default=2)
args = parser.parse_args()
manifest = LocalInstaller(args.destination).install(args.package, runtime_protocol=args.runtime_protocol)
print(manifest.version)
