"""Fail-closed correctness, benchmark and release gates for SIMD promotion."""

from __future__ import annotations

import math
import os
import platform
import resource
import time
from dataclasses import asdict, dataclass
from typing import Any, Callable, Iterable, Mapping, Sequence


SIMD_VALIDATION_SCHEMA_V1 = "simplicio-local.simd-release/v1"


@dataclass(frozen=True)
class BenchmarkSummary:
    p50_ms: float
    p95_ms: float
    wall_ms: float
    cpu_ms: float
    cpu_seconds: float
    runs: int

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def benchmark_callable(callable_: Callable[[], Any], *, warmups: int = 1,
                       repetitions: int = 7) -> BenchmarkSummary:
    """Measure wall and process CPU time with a bounded sample count."""
    if isinstance(warmups, bool) or isinstance(repetitions, bool) or warmups < 0 or repetitions < 1:
        raise ValueError("warmups must be non-negative and repetitions must be positive")
    for _ in range(warmups):
        callable_()
    wall: list[float] = []
    cpu: list[float] = []
    for _ in range(repetitions):
        wall_start = time.perf_counter_ns()
        cpu_start = time.process_time_ns()
        callable_()
        wall.append((time.perf_counter_ns() - wall_start) / 1_000_000.0)
        cpu.append((time.process_time_ns() - cpu_start) / 1_000_000.0)
    ordered_wall = sorted(wall)
    p50 = ordered_wall[(len(ordered_wall) - 1) // 2]
    p95 = ordered_wall[min(len(ordered_wall) - 1, math.ceil(len(ordered_wall) * 0.95) - 1)]
    return BenchmarkSummary(p50, p95, sum(wall), sum(cpu), sum(cpu) / 1000.0, repetitions)


@dataclass(frozen=True)
class DifferentialResult:
    passed: bool
    cases: int
    mismatches: tuple[str, ...]


def run_differential(reference: Callable[[Any], Any], candidate: Callable[[Any], Any],
                     cases: Iterable[Any], *, compare: Callable[[Any, Any], bool] | None = None) -> DifferentialResult:
    """Compare a physical kernel against the scalar/reference path."""
    comparator = compare or (lambda expected, actual: expected == actual)
    mismatches: list[str] = []
    count = 0
    for count, case in enumerate(cases, start=1):
        expected = reference(case)
        actual = candidate(case)
        if not comparator(expected, actual):
            mismatches.append(str(count - 1))
    return DifferentialResult(not mismatches, count, tuple(mismatches))


@dataclass(frozen=True)
class SimdValidationObservation:
    requested_isa: str
    effective_kernel: str
    isa_source: str
    correctness_passed: bool
    illegal_instruction: bool
    memory_safe: bool
    oom: bool
    model_evidence: bool
    benchmark: BenchmarkSummary | None
    baseline: BenchmarkSummary | None
    tuning_key: str = ""
    cache_hit: bool = False
    layout_version: str = ""
    packed: bool = False
    fallback_reason: str = ""
    workers: int = 1
    threads: int = 1
    batch_size: int = 1
    error: str | None = None


@dataclass(frozen=True)
class SimdGateResult:
    accepted: bool
    reasons: tuple[str, ...]
    receipt: dict[str, Any]


def evaluate_release_gate(observation: SimdValidationObservation, *, min_speedup: float = 0.02,
                          max_p95_regression: float = 0.10) -> SimdGateResult:
    reasons: list[str] = []
    benchmark = observation.benchmark
    baseline = observation.baseline
    if not observation.correctness_passed:
        reasons.append("correctness-differential-failed")
    if observation.illegal_instruction:
        reasons.append("illegal-instruction-observed")
    if not observation.memory_safe:
        reasons.append("memory-safety-gate-failed")
    if observation.oom:
        reasons.append("oom-observed")
    if not observation.model_evidence:
        reasons.append("end-to-end-model-evidence-missing")
    if benchmark is None or baseline is None:
        reasons.append("benchmark-baseline-missing")
    else:
        finite = all(math.isfinite(value) and value > 0 for value in (
            benchmark.p50_ms, benchmark.p95_ms, baseline.p50_ms, baseline.p95_ms))
        if not finite:
            reasons.append("benchmark-metrics-invalid")
        elif benchmark.p50_ms >= baseline.p50_ms * (1.0 - min_speedup):
            reasons.append("p50-speedup-below-promotion-threshold")
        elif benchmark.p95_ms > baseline.p95_ms * (1.0 + max_p95_regression):
            reasons.append("p95-regression-exceeds-budget")
    if observation.effective_kernel in ("", "scalar") and not observation.fallback_reason:
        reasons.append("effective-simd-kernel-not-visible")
    accepted = not reasons
    if accepted:
        reasons.append("all-correctness-benchmark-model-gates-passed")
    receipt = build_simd_receipt(observation, accepted=accepted, reasons=tuple(reasons))
    return SimdGateResult(accepted, tuple(reasons), receipt)


def build_simd_receipt(observation: SimdValidationObservation, *, accepted: bool,
                       reasons: Sequence[str]) -> dict[str, Any]:
    benchmark = observation.benchmark.as_dict() if observation.benchmark else None
    baseline = observation.baseline.as_dict() if observation.baseline else None
    metrics: dict[str, Any] = {
        "candidate": benchmark,
        "scalar_baseline": baseline,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpu_seconds_source": "process_time",
    }
    return {
        "schema": SIMD_VALIDATION_SCHEMA_V1,
        "gate": {"accepted": accepted, "reasons": list(reasons)},
        "isa": {"requested": observation.requested_isa, "effective": observation.effective_kernel,
                "source": observation.isa_source, "illegal_instruction": observation.illegal_instruction},
        "kernel": {"effective": observation.effective_kernel, "fallback_reason": observation.fallback_reason},
        "tuning": {"key": observation.tuning_key, "cache_hit": observation.cache_hit},
        "layout": {"version": observation.layout_version, "packed": observation.packed},
        "execution": {"workers": observation.workers, "threads": observation.threads,
                       "batch_size": observation.batch_size},
        "safety": {"memory_safe": observation.memory_safe, "oom": observation.oom,
                    "error": observation.error},
        "model_evidence": observation.model_evidence,
        "metrics": metrics,
    }


def collect_process_cpu_seconds() -> float:
    """Small telemetry helper used by release harnesses."""
    usage = resource.getrusage(resource.RUSAGE_SELF)
    return usage.ru_utime + usage.ru_stime
