"""ISA-gated quant-kernel dispatch with bounded autotuning cache."""

from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Callable, Literal, Mapping, Sequence


KERNEL_DISPATCH_SCHEMA_V1 = "simplicio-local.kernel-dispatch/v1"


@dataclass(frozen=True)
class KernelCandidate:
    name: str
    isa_requirements: tuple[str, ...]
    measured_speedup: float | None
    numeric_error: float | None
    startup_ms: float
    operation: str = "matmul"
    dtype: str = "int8"
    shape_class: str = "default"
    kernel_version: str = "v1"
    layout_version: str = "v1"


@dataclass(frozen=True)
class KernelDispatchPlan:
    selected: str
    fallback: str
    tuning_key: str
    cache_hit: bool
    accepted: bool
    reason: str
    evidence: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {"schema": KERNEL_DISPATCH_SCHEMA_V1, **asdict(self)}


@dataclass(frozen=True)
class TuningObservation:
    kernel: str
    p50_ms: float
    p95_ms: float
    runs: int = 1
    correct: bool = True
    error: str | None = None


@dataclass(frozen=True)
class BoundedTuningResult:
    selected: str
    fallback: str
    cache_hit: bool
    reason: str
    observations: tuple[TuningObservation, ...]


TuningMode = Literal["off", "cache-only", "bounded", "force-retune"]


def tuning_key(*, hardware_fingerprint: str, backend: str, model_digest: str, runtime_version: str,
               isa_features: Sequence[str] = (), os_state: Mapping[str, bool] | None = None,
               operation: str = "matmul", dtype: str = "int8", shape_class: str = "default",
               kernel_version: str = "v1", layout_version: str = "v1") -> str:
    payload = json.dumps({"hardware": hardware_fingerprint, "backend": backend,
                          "model": model_digest, "runtime": runtime_version,
                          "isa": sorted(set(isa_features)), "os": dict(sorted((os_state or {}).items())),
                          "operation": operation, "dtype": dtype, "shape": shape_class,
                          "kernel": kernel_version, "layout": layout_version},
                         sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


class PersistentTuningCache:
    """Atomic JSON cache. Invalid or incomplete records are cache misses."""

    SCHEMA = "simplicio-local.tuning-cache/v1"

    def __init__(self, path: str | os.PathLike[str]):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self, key: str, candidates: Sequence[KernelCandidate]) -> str | None:
        try:
            document = json.loads(self.path.read_text(encoding="utf-8"))
            if document.get("schema") != self.SCHEMA:
                return None
            selected = document.get("entries", {}).get(key, {}).get("selected")
        except (OSError, ValueError, TypeError, AttributeError):
            return None
        return selected if isinstance(selected, str) and any(candidate.name == selected for candidate in candidates) else None

    def store(self, key: str, selected: str, *, metadata: Mapping[str, str] | None = None) -> None:
        document: dict[str, Any] = {"schema": self.SCHEMA, "entries": {}}
        try:
            document = json.loads(self.path.read_text(encoding="utf-8"))
            if document.get("schema") != self.SCHEMA or not isinstance(document.get("entries"), dict):
                document = {"schema": self.SCHEMA, "entries": {}}
        except (OSError, ValueError, TypeError, AttributeError):
            pass
        document["entries"][key] = {"selected": selected, "metadata": dict(sorted((metadata or {}).items()))}
        handle, temporary_name = tempfile.mkstemp(prefix=self.path.name + ".", suffix=".tmp", dir=self.path.parent)
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                json.dump(document, stream, sort_keys=True, separators=(",", ":"))
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_name, self.path)
        except BaseException:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
            raise


def _observation(kernel: str, value: TuningObservation | Mapping[str, Any] | Sequence[float] | float) -> TuningObservation:
    if isinstance(value, TuningObservation):
        return value
    if isinstance(value, Mapping):
        return TuningObservation(kernel, float(value["p50_ms"]), float(value.get("p95_ms", value["p50_ms"])),
                                 int(value.get("runs", 1)), bool(value.get("correct", True)), value.get("error"))
    if isinstance(value, (int, float)):
        return TuningObservation(kernel, float(value), float(value))
    values = tuple(float(item) for item in value)
    if not values:
        raise ValueError("benchmark returned no samples")
    ordered = sorted(values)
    p50 = ordered[(len(ordered) - 1) // 2]
    p95 = ordered[min(len(ordered) - 1, math.ceil(len(ordered) * 0.95) - 1)]
    return TuningObservation(kernel, p50, p95, len(values))


def run_bounded_autotune(*, candidates: Sequence[KernelCandidate], benchmark: Callable[[KernelCandidate],
                       TuningObservation | Mapping[str, Any] | Sequence[float] | float],
                       isa_features: Sequence[str], numeric_tolerance: float = 1e-4,
                       tuning_budget_ms: float = 100.0, max_candidates: int = 8,
                       max_runs_per_candidate: int = 32, max_p95_regression: float = 0.10) -> BoundedTuningResult:
    """Run a finite benchmark set and promote only correct, faster candidates."""
    if max_candidates < 1 or max_runs_per_candidate < 1 or tuning_budget_ms <= 0:
        raise ValueError("bounded tuning limits must be positive")
    scalar = next((candidate for candidate in candidates if candidate.name == "scalar"), None)
    if scalar is None:
        raise ValueError("portable scalar fallback candidate is required")
    supported = [candidate for candidate in candidates if candidate.name != "scalar"
                 and set(candidate.isa_requirements).issubset(set(isa_features))
                 and candidate.startup_ms <= tuning_budget_ms]
    supported = supported[:max_candidates]
    observations: list[TuningObservation] = []
    try:
        baseline = _observation("scalar", benchmark(scalar))
        observations.append(baseline)
    except (ArithmeticError, KeyError, TypeError, ValueError):
        return BoundedTuningResult("scalar", "scalar", False, "scalar-baseline-benchmark-failed", ())
    if (not baseline.correct or not math.isfinite(baseline.p50_ms) or baseline.p50_ms <= 0
            or not math.isfinite(baseline.p95_ms) or baseline.p95_ms <= 0):
        return BoundedTuningResult("scalar", "scalar", False, "invalid-scalar-baseline", tuple(observations))
    best = scalar
    for candidate in supported:
        try:
            observation = _observation(candidate.name, benchmark(candidate))
        except (ArithmeticError, KeyError, TypeError, ValueError):
            continue
        observations.append(observation)
        within_budget = observation.runs <= max_runs_per_candidate
        correct = observation.correct and (candidate.numeric_error is None or candidate.numeric_error <= numeric_tolerance)
        finite = (math.isfinite(observation.p50_ms) and math.isfinite(observation.p95_ms)
                  and observation.p50_ms > 0 and observation.p95_ms > 0)
        faster = observation.p50_ms < baseline.p50_ms * (1.0 - 0.02)
        p95_ok = observation.p95_ms <= baseline.p95_ms * (1.0 + max_p95_regression)
        if within_budget and correct and finite and faster and p95_ok:
            if best is scalar or observation.p50_ms < next(item.p50_ms for item in observations if item.kernel == best.name):
                best = candidate
    reason = "bounded-autotune-promoted" if best is not scalar else "no-candidate-beat-safe-baseline"
    return BoundedTuningResult(best.name, "scalar", False, reason, tuple(observations))


def select_kernel(*, isa_features: Sequence[str], candidates: Sequence[KernelCandidate],
                  hardware_fingerprint: str, backend: str, model_digest: str, runtime_version: str,
                  tuning_cache: Mapping[str, str] | None = None, numeric_tolerance: float = 1e-4,
                  tuning_budget_ms: float = 100.0, tuning_mode: TuningMode = "bounded",
                  persistent_cache: PersistentTuningCache | None = None,
                  operation: str = "matmul", dtype: str = "int8", shape_class: str = "default",
                  kernel_version: str = "v1", layout_version: str = "v1",
                  os_state: Mapping[str, bool] | None = None,
                  benchmark: Callable[[KernelCandidate], TuningObservation | Mapping[str, Any] |
                                       Sequence[float] | float] | None = None) -> KernelDispatchPlan:
    if tuning_mode not in ("off", "cache-only", "bounded", "force-retune"):
        raise ValueError("unsupported tuning mode")
    key = tuning_key(hardware_fingerprint=hardware_fingerprint, backend=backend,
                     model_digest=model_digest, runtime_version=runtime_version,
                     isa_features=isa_features, os_state=os_state, operation=operation,
                     dtype=dtype, shape_class=shape_class, kernel_version=kernel_version,
                     layout_version=layout_version)
    cache = dict(tuning_cache or {})
    scalar = next((candidate for candidate in candidates if candidate.name == "scalar"), None)
    if scalar is None:
        raise ValueError("portable scalar fallback candidate is required")
    if tuning_mode == "off":
        return KernelDispatchPlan("scalar", "scalar", key, False, True, "tuning disabled by policy", ("scalar-fallback",))
    cached = None if tuning_mode == "force-retune" else cache.get(key)
    if cached is None and persistent_cache is not None and tuning_mode != "force-retune":
        cached = persistent_cache.load(key, candidates)
    supported_names = {candidate.name for candidate in candidates if candidate.name != "scalar"
                       and set(candidate.isa_requirements).issubset(set(isa_features))
                       and candidate.measured_speedup is not None and candidate.measured_speedup > 0
                       and candidate.numeric_error is not None and candidate.numeric_error <= numeric_tolerance
                       and candidate.startup_ms <= tuning_budget_ms}
    if cached and cached in supported_names:
        return KernelDispatchPlan(cached, "scalar", key, True, True, "cached tuning selected", ("tuning-cache",))
    if tuning_mode == "cache-only":
        return KernelDispatchPlan("scalar", "scalar", key, False, True, "cache miss; scalar fallback", ("scalar-fallback",))
    if benchmark is not None:
        result = run_bounded_autotune(candidates=candidates, benchmark=benchmark, isa_features=isa_features,
                                      numeric_tolerance=numeric_tolerance, tuning_budget_ms=tuning_budget_ms)
        if result.selected != "scalar" and persistent_cache is not None:
            persistent_cache.store(key, result.selected, metadata={"mode": tuning_mode, "backend": backend})
        return KernelDispatchPlan(result.selected, "scalar", key, False, True, result.reason,
                                  ("isa-capability", "numeric-equivalence", "bounded-autotune"))
    supported = [candidate for candidate in candidates if candidate.name != "scalar"
                 and set(candidate.isa_requirements).issubset(set(isa_features))
                 and candidate.measured_speedup is not None and candidate.measured_speedup > 0
                 and candidate.numeric_error is not None and candidate.numeric_error <= numeric_tolerance
                 and candidate.startup_ms <= tuning_budget_ms]
    if not supported:
        return KernelDispatchPlan("scalar", "scalar", key, False, True,
                                  "no supported measured kernel; portable fallback", ("scalar-fallback",))
    selected = max(supported, key=lambda candidate: (candidate.measured_speedup or 0, -candidate.startup_ms))
    if persistent_cache is not None:
        persistent_cache.store(key, selected.name, metadata={"mode": tuning_mode, "backend": backend})
    return KernelDispatchPlan(selected.name, "scalar", key, False, True,
                              "ISA and numeric gates passed; measured kernel promoted",
                              ("isa-capability", "numeric-equivalence", "bounded-autotune"))
