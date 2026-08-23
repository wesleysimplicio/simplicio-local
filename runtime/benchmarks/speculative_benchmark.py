#!/usr/bin/env python3
"""Reproducible baseline-vs-speculative benchmark capture.

The harness records measured receipts only after a command really runs.  A
dry-run is explicitly marked planned and never becomes a performance claim.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import resource
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


SCHEMA_ID = "simplicio-local/speculative-benchmark/v1"
STRATEGIES = {"baseline", "ngram_prompt_lookup", "draft_model", "dflash", "mtp", "fast_auto"}


@dataclass(frozen=True)
class BenchmarkCase:
    case_id: str
    workload: str
    strategy: str
    command: tuple[str, ...]


def validate_suite(payload: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("schema") != SCHEMA_ID:
        errors.append(f"schema must be {SCHEMA_ID}")
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        return errors + ["cases must be a non-empty array"]
    seen: set[str] = set()
    for index, case in enumerate(cases):
        label = f"cases[{index}]"
        if not isinstance(case, dict):
            errors.append(f"{label} must be an object")
            continue
        case_id = case.get("id")
        if not isinstance(case_id, str) or not case_id.strip():
            errors.append(f"{label}.id is required")
        elif case_id in seen:
            errors.append(f"{label}.id duplicates {case_id}")
        seen.add(str(case_id))
        if not isinstance(case.get("workload"), str) or not case["workload"].strip():
            errors.append(f"{label}.workload is required")
        if case.get("strategy") not in STRATEGIES:
            errors.append(f"{label}.strategy is unsupported")
        command = case.get("command")
        if not isinstance(command, list) or not command or not all(isinstance(item, str) and item for item in command):
            errors.append(f"{label}.command must be a non-empty argv array")
    return errors


def load_cases(path: str | os.PathLike[str]) -> tuple[BenchmarkCase, ...]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    errors = validate_suite(payload)
    if errors:
        raise ValueError("; ".join(errors))
    return tuple(BenchmarkCase(str(item["id"]), str(item["workload"]), str(item["strategy"]),
                               tuple(item["command"])) for item in payload["cases"])


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _max_rss_bytes() -> int | None:
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    if usage.ru_maxrss <= 0:
        return None
    multiplier = 1024 if platform.system().lower() != "darwin" else 1
    return int(usage.ru_maxrss * multiplier)


def _metrics_from_stdout(stdout: str) -> dict[str, Any]:
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return {"prompt_tokens": None, "generation_tokens": None, "accepted_tokens": None, "output_sha256": None}
    if not isinstance(payload, dict):
        return {"prompt_tokens": None, "generation_tokens": None, "accepted_tokens": None, "output_sha256": None}
    output = payload.get("output")
    return {
        "prompt_tokens": payload.get("prompt_tokens"),
        "generation_tokens": payload.get("generation_tokens"),
        "accepted_tokens": payload.get("accepted_tokens"),
        "output_sha256": _sha256(output) if isinstance(output, str) else None,
    }


def run_case(case: BenchmarkCase, *, cwd: str | os.PathLike[str] | None = None,
             dry_run: bool = False, timeout: float = 600.0) -> dict[str, Any]:
    base: dict[str, Any] = {"case_id": case.case_id, "workload": case.workload, "strategy": case.strategy}
    if dry_run:
        return {**base, "status": "planned", "command": list(case.command), "metrics": None, "output_equivalent": None}
    started = time.perf_counter()
    try:
        completed = subprocess.run(case.command, cwd=cwd, capture_output=True, text=True,
                                   timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {**base, "status": "failed", "command": list(case.command), "error": str(exc), "metrics": None,
                "output_equivalent": None}
    metrics = _metrics_from_stdout(completed.stdout)
    metrics.update({"wall_time_seconds": round(time.perf_counter() - started, 6),
                    "exit_code": completed.returncode, "max_rss_bytes": _max_rss_bytes()})
    return {**base, "status": "measured" if completed.returncode == 0 else "failed",
            "command": list(case.command), "metrics": metrics,
            "stderr_tail": completed.stderr[-2000:], "output_equivalent": None}


def run_suite(cases: Sequence[BenchmarkCase], *, cwd: str | os.PathLike[str] | None = None,
              dry_run: bool = False, timeout: float = 600.0) -> dict[str, Any]:
    results = [run_case(case, cwd=cwd, dry_run=dry_run, timeout=timeout) for case in cases]
    baseline_by_workload = {
        item["workload"]: item.get("metrics", {}).get("output_sha256")
        for item in results
        if item["strategy"] == "baseline" and item["status"] == "measured" and item.get("metrics")
    }
    for item in results:
        digest = (item.get("metrics") or {}).get("output_sha256")
        baseline = baseline_by_workload.get(item["workload"])
        if item["status"] == "measured" and digest and baseline:
            item["output_equivalent"] = digest == baseline
    return {
        "schema": SCHEMA_ID,
        "status": "planned" if dry_run else ("measured" if all(item["status"] == "measured" for item in results) else "incomplete"),
        "host": {"platform": platform.platform(), "python": sys.version.split()[0]},
        "cases": results,
        "claims": [] if dry_run or any(item["status"] != "measured" for item in results) else [
            "Results are workload- and host-specific; no general speedup is implied."
        ],
    }


def _main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("suite", type=Path)
    parser.add_argument("--cwd", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--timeout", type=float, default=600.0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        receipt = run_suite(load_cases(args.suite), cwd=args.cwd, dry_run=args.dry_run, timeout=args.timeout)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    rendered = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
