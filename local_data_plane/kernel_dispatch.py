"""ISA-gated quant-kernel dispatch with bounded autotuning cache."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, asdict
from typing import Any, Mapping, Sequence


KERNEL_DISPATCH_SCHEMA_V1 = "simplicio-local.kernel-dispatch/v1"


@dataclass(frozen=True)
class KernelCandidate:
    name: str
    isa_requirements: tuple[str, ...]
    measured_speedup: float | None
    numeric_error: float | None
    startup_ms: float


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


def tuning_key(*, hardware_fingerprint: str, backend: str, model_digest: str, runtime_version: str) -> str:
    payload = json.dumps({"hardware": hardware_fingerprint, "backend": backend,
                          "model": model_digest, "runtime": runtime_version}, sort_keys=True).encode()
    return hashlib.sha256(payload).hexdigest()


def select_kernel(*, isa_features: Sequence[str], candidates: Sequence[KernelCandidate],
                  hardware_fingerprint: str, backend: str, model_digest: str, runtime_version: str,
                  tuning_cache: Mapping[str, str] | None = None, numeric_tolerance: float = 1e-4,
                  tuning_budget_ms: float = 100.0) -> KernelDispatchPlan:
    key = tuning_key(hardware_fingerprint=hardware_fingerprint, backend=backend,
                     model_digest=model_digest, runtime_version=runtime_version)
    cache = dict(tuning_cache or {})
    scalar = next((candidate for candidate in candidates if candidate.name == "scalar"), None)
    if scalar is None:
        raise ValueError("portable scalar fallback candidate is required")
    cached = cache.get(key)
    if cached and any(candidate.name == cached for candidate in candidates):
        return KernelDispatchPlan(cached, "scalar", key, True, True, "cached tuning selected", ("tuning-cache",))
    supported = [candidate for candidate in candidates if candidate.name != "scalar"
                 and set(candidate.isa_requirements).issubset(set(isa_features))
                 and candidate.measured_speedup is not None and candidate.measured_speedup > 0
                 and candidate.numeric_error is not None and candidate.numeric_error <= numeric_tolerance
                 and candidate.startup_ms <= tuning_budget_ms]
    if not supported:
        return KernelDispatchPlan("scalar", "scalar", key, False, True,
                                  "no supported measured kernel; portable fallback", ("scalar-fallback",))
    selected = max(supported, key=lambda candidate: (candidate.measured_speedup or 0, -candidate.startup_ms))
    return KernelDispatchPlan(selected.name, "scalar", key, False, True,
                              "ISA and numeric gates passed; measured kernel promoted",
                              ("isa-capability", "numeric-equivalence", "bounded-autotune"))
