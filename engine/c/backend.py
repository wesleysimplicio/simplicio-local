#!/usr/bin/env python3
"""CLI adapter for simplicio.local-inference-backend/v1."""

import argparse
import json
from pathlib import Path

from backend_contract import (GB, admission_estimate, capability_probe,
                              host_resources)


def parser():
    result = argparse.ArgumentParser(prog="us4-cli backend")
    commands = result.add_subparsers(dest="command", required=True)
    probe = commands.add_parser("probe")
    probe.add_argument("--model")
    probe.add_argument("--json", action="store_true")
    estimate = commands.add_parser("estimate")
    estimate.add_argument("--model-bytes", type=int, required=True)
    estimate.add_argument("--dense-bytes", type=int, required=True)
    estimate.add_argument("--cache-bytes", type=int, default=0)
    estimate.add_argument("--hard-rss-bytes", type=int, default=13 * GB)
    estimate.add_argument("--available-memory-bytes", type=int)
    estimate.add_argument("--available-disk-bytes", type=int)
    estimate.add_argument("--workload",
                          choices=("interactive", "background", "batch",
                                   "deep-offline"),
                          default="deep-offline")
    estimate.add_argument("--allow-interactive", action="store_true")
    estimate.add_argument("--json", action="store_true")
    return result


def main(argv=None):
    args = parser().parse_args(argv)
    if args.command == "probe":
        report = capability_probe(model=args.model)
    else:
        memory, disk = host_resources(Path.cwd())
        report = admission_estimate(
            model_bytes=args.model_bytes,
            dense_bytes=args.dense_bytes,
            cache_bytes=args.cache_bytes,
            available_memory=(memory if args.available_memory_bytes is None
                              else args.available_memory_bytes),
            available_disk=(disk if args.available_disk_bytes is None
                            else args.available_disk_bytes),
            hard_rss_limit=args.hard_rss_bytes,
            workload=args.workload,
            explicit_interactive=args.allow_interactive,
        )
    print(json.dumps(report, sort_keys=True) if args.json
          else json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get("decision") != "deny" else 78


if __name__ == "__main__":
    raise SystemExit(main())
