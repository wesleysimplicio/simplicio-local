#!/usr/bin/env python3
"""Evidence-first microarchitectural and roofline baseline capture."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import resource
import subprocess
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Mapping, Sequence


BASELINE_SCHEMA_V1 = "simplicio-local.microarchitectural-baseline/v1"


@dataclass(frozen=True)
class Metric:
    value: float | int | None
    unit: str
    status: str
    reason: str | None = None

    @staticmethod
    def measured(value: float | int, unit: str) -> "Metric":
        return Metric(value, unit, "measured")

    @staticmethod
    def unavailable(unit: str, reason: str) -> "Metric":
        return Metric(None, unit, "unavailable", reason)


@dataclass(frozen=True)
class BenchmarkCase:
    case_id: str
    workload: str
    backend: str
    strategy: str
    phase: str
    context_tokens: int
    command: tuple[str, ...]


def classify_roofline(*, arithmetic_intensity: float | None, bandwidth_gib_s: float | None,
                      compute_gflops: float | None, transfer_fraction: float | None = None) -> str:
    if transfer_fraction is not None and transfer_fraction >= 0.35:
        return "transfer-bound"
    if arithmetic_intensity is None or bandwidth_gib_s is None or compute_gflops is None:
        return "unavailable"
    if arithmetic_intensity <= 0 or bandwidth_gib_s <= 0 or compute_gflops <= 0:
        return "unavailable"
    bandwidth_ceiling = arithmetic_intensity * bandwidth_gib_s
    if bandwidth_ceiling < compute_gflops * 0.8:
        return "memory-bandwidth-bound"
    if compute_gflops < bandwidth_ceiling * 0.8:
        return "compute-bound"
    return "latency-bound"


def _fingerprint(payload: Mapping[str, Any]) -> str:
    stable = {key: payload[key] for key in sorted(payload) if key not in {"hostname", "user"}}
    return hashlib.sha256(json.dumps(stable, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def hardware_fingerprint() -> dict[str, Any]:
    payload: dict[str, Any] = {
        "platform": platform.system().lower(),
        "release": platform.release(),
        "architecture": platform.machine(),
        "cpu_count": os.cpu_count(),
        "python": platform.python_version(),
    }
    payload["fingerprint"] = _fingerprint(payload)
    return payload


def _max_rss_bytes() -> int | None:
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    if usage.ru_maxrss <= 0:
        return None
    return int(usage.ru_maxrss * (1 if platform.system().lower() == "darwin" else 1024))


def run_case(case: BenchmarkCase, *, cwd: str | os.PathLike[str] | None = None,
             timeout: float = 600.0) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        completed = subprocess.run(case.command, cwd=cwd, capture_output=True, text=True,
                                   timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"case": asdict(case), "status": "failed", "error": str(exc), "metrics": {}}
    elapsed = time.perf_counter() - started
    metrics: dict[str, Any] = {
        "wall_time_seconds": Metric.measured(round(elapsed, 6), "s").__dict__,
        "max_rss_bytes": Metric.measured(_max_rss_bytes(), "bytes").__dict__ if _max_rss_bytes() else Metric.unavailable("bytes", "host did not report child RSS"),
        "prompt_tok_s": Metric.unavailable("tokens/s", "runner did not emit prompt timing").__dict__,
        "generation_tok_s": Metric.unavailable("tokens/s", "runner did not emit generation timing").__dict__,
        "cycles": Metric.unavailable("cycles", "PMU counter unavailable to baseline runner").__dict__,
        "instructions": Metric.unavailable("instructions", "PMU counter unavailable to baseline runner").__dict__,
        "l1_misses": Metric.unavailable("count", "PMU counter unavailable to baseline runner").__dict__,
        "l2_misses": Metric.unavailable("count", "PMU counter unavailable to baseline runner").__dict__,
        "llc_misses": Metric.unavailable("count", "PMU counter unavailable to baseline runner").__dict__,
        "cpu_gpu_bytes": Metric.unavailable("bytes", "backend did not expose transfer counters").__dict__,
    }
    return {"case": asdict(case), "status": "measured" if completed.returncode == 0 else "failed",
            "returncode": completed.returncode, "stderr_tail": completed.stderr[-2000:], "metrics": metrics,
            "roofline": {"classification": "unavailable", "reason": "runner did not emit arithmetic intensity and ceilings"}}


def create_baseline(cases: Sequence[BenchmarkCase], *, cwd: str | os.PathLike[str] | None = None,
                    timeout: float = 600.0) -> dict[str, Any]:
    results = [run_case(case, cwd=cwd, timeout=timeout) for case in cases]
    return {"schema": BASELINE_SCHEMA_V1, "status": "measured" if results and all(item["status"] == "measured" for item in results) else "incomplete",
            "hardware": hardware_fingerprint(), "cases": results,
            "claims": [], "notes": ["Unavailable metrics remain null with reasons; this baseline makes no unmeasured performance claim."]}


def write_baseline(path: str | os.PathLike[str], receipt: Mapping[str, Any]) -> None:
    Path(path).write_text(json.dumps(dict(receipt), indent=2, sort_keys=True) + "\n", encoding="utf-8")
