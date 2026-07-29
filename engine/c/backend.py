#!/usr/bin/env python3
"""CLI adapter for simplicio.local-inference-backend/v1."""

import argparse
import json
from pathlib import Path

from backend_contract import (GB, LITERT_INSTALL_PLAN_SCHEMA,
                              LITERT_ROLLBACK_SCHEMA, LITERT_VERIFY_SCHEMA,
                              admission_estimate, build_litert_install_plan,
                              capability_probe, host_resources,
                              install_litert_package, rollback_litert_package,
                              verify_litert_package)


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

    install = commands.add_parser("install")
    install_commands = install.add_subparsers(dest="install_command", required=True)
    litert = install_commands.add_parser("litert")
    litert.add_argument("--dry-run", action="store_true")
    litert.add_argument("--yes", action="store_true")
    litert.add_argument("--verify", action="store_true")
    litert.add_argument("--rollback", action="store_true")
    litert.add_argument("--uninstall", action="store_true")
    litert.add_argument("--manifest")
    litert.add_argument("--artifact")
    litert.add_argument("--cache-dir")
    litert.add_argument("--platform")
    litert.add_argument("--json", action="store_true")
    return result


def _install_report(args):
    repo_root = Path(__file__).resolve().parents[2]
    try:
        if args.verify:
            return verify_litert_package(
                repo_root=repo_root,
                manifest_path=args.manifest,
                cache_dir=args.cache_dir,
                platform_key=args.platform,
            ), 0
        if args.rollback or args.uninstall:
            return rollback_litert_package(
                repo_root=repo_root,
                manifest_path=args.manifest,
                cache_dir=args.cache_dir,
                platform_key=args.platform,
                yes=args.yes,
            ), 0
        if args.dry_run:
            report = build_litert_install_plan(
                repo_root=repo_root,
                manifest_path=args.manifest,
                cache_dir=args.cache_dir,
                platform_key=args.platform,
                artifact_path=args.artifact,
            )
            report["status"] = "planned"
            return report, 0
        if not args.yes:
            raise ValueError("choose exactly one of --dry-run, --verify, or --yes")
        return install_litert_package(
            repo_root=repo_root,
            manifest_path=args.manifest,
            cache_dir=args.cache_dir,
            platform_key=args.platform,
            artifact_path=args.artifact,
            yes=True,
        ), 0
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        if args.verify:
            schema = LITERT_VERIFY_SCHEMA
        elif args.rollback or args.uninstall:
            schema = LITERT_ROLLBACK_SCHEMA
        else:
            schema = LITERT_INSTALL_PLAN_SCHEMA
        return {
            "schema": schema,
            "status": "failed",
            "offline": bool(args.verify or args.rollback or args.uninstall),
            "writes": False,
            "failure_reason": str(error),
        }, 1


def main(argv=None):
    args = parser().parse_args(argv)
    if args.command == "probe":
        report = capability_probe(model=args.model)
        status = 0
    elif args.command == "estimate":
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
        status = 0 if report.get("decision") != "deny" else 78
    else:
        report, status = _install_report(args)
    print(json.dumps(report, sort_keys=True) if args.json
          else json.dumps(report, indent=2, sort_keys=True))
    return status


if __name__ == "__main__":
    raise SystemExit(main())
