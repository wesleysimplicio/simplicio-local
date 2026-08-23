"""GPU/unified-memory residency and minimal-copy planning."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Mapping


RESIDENCY_SCHEMA_V1 = "simplicio-local.residency-plan/v1"


@dataclass(frozen=True)
class ResidencyCategory:
    device: str
    bytes: int
    invariant_per_token: bool


@dataclass(frozen=True)
class ResidencyPlan:
    backend: str
    weights: ResidencyCategory
    kv: ResidencyCategory
    scratch: ResidencyCategory
    draft: ResidencyCategory
    accepted: bool
    transfers_per_token: int
    transfer_bytes_per_token: int
    reason: str
    evidence: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {"schema": RESIDENCY_SCHEMA_V1, **asdict(self)}


def plan_residency(*, backend: str, weights_bytes: int, kv_bytes: int, scratch_bytes: int,
                   draft_bytes: int = 0, device_available_bytes: int, system_available_bytes: int,
                   transfer_evidence: Mapping[str, Any] | None = None,
                   separate_draft_device_supported: bool = False) -> ResidencyPlan:
    values = (weights_bytes, kv_bytes, scratch_bytes, draft_bytes, device_available_bytes, system_available_bytes)
    if backend not in {"cuda", "metal", "unified", "cpu"}:
        raise ValueError("unsupported residency backend")
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in values):
        raise ValueError("residency sizes must be non-negative integers")
    evidence = dict(transfer_evidence or {})
    total = weights_bytes + kv_bytes + scratch_bytes + draft_bytes
    device_ok = device_available_bytes >= total
    if backend == "unified":
        if device_ok:
            category = "unified"
            return ResidencyPlan(backend, ResidencyCategory(category, weights_bytes, True),
                                 ResidencyCategory(category, kv_bytes, False),
                                 ResidencyCategory(category, scratch_bytes, False),
                                 ResidencyCategory(category, draft_bytes, False), True, 0, 0,
                                 "unified-memory residency avoids artificial CUDA-style copies",
                                 ("unified-memory-policy",))
        return ResidencyPlan(backend, ResidencyCategory("none", weights_bytes, True),
                             ResidencyCategory("none", kv_bytes, False), ResidencyCategory("none", scratch_bytes, False),
                             ResidencyCategory("none", draft_bytes, False), False, 0, 0,
                             "unified-memory pressure exceeds reserved budget", ("oom-prevention",))
    if backend == "cpu":
        accepted = system_available_bytes >= total
        return ResidencyPlan(backend, ResidencyCategory("cpu", weights_bytes, True),
                             ResidencyCategory("cpu", kv_bytes, False), ResidencyCategory("cpu", scratch_bytes, False),
                             ResidencyCategory("cpu", draft_bytes, False), accepted, 0, 0,
                             "CPU-only residency" if accepted else "CPU memory pressure exceeds budget",
                             ("cpu-fallback",))
    if device_ok:
        return ResidencyPlan(backend, ResidencyCategory(backend, weights_bytes, True),
                             ResidencyCategory(backend, kv_bytes, False), ResidencyCategory(backend, scratch_bytes, False),
                             ResidencyCategory(backend, draft_bytes, False), True, 0, 0,
                             "all categories fit device headroom; invariant weights stay resident",
                             ("device-headroom", "no-weight-transfer-per-token"))
    target_total = weights_bytes + kv_bytes + scratch_bytes
    hybrid_ok = separate_draft_device_supported and draft_bytes > 0 and system_available_bytes >= total
    if hybrid_ok and evidence.get("hybrid_throughput_delta", 0) >= 0:
        return ResidencyPlan(backend, ResidencyCategory(backend, weights_bytes, True),
                             ResidencyCategory(backend, kv_bytes, False), ResidencyCategory(backend, scratch_bytes, False),
                             ResidencyCategory("cpu", draft_bytes, False), True, 1, draft_bytes,
                             "draft moved to CPU after measured non-regressive hybrid evidence",
                             ("hybrid-break-even", "draft-cpu"))
    if system_available_bytes >= target_total:
        return ResidencyPlan(backend, ResidencyCategory("cpu", weights_bytes, True),
                             ResidencyCategory("cpu", kv_bytes, False), ResidencyCategory("cpu", scratch_bytes, False),
                             ResidencyCategory("cpu", draft_bytes, False), True, 0, 0,
                             "device budget or transfer evidence is insufficient; CPU fallback",
                             ("safe-fallback",))
    return ResidencyPlan(backend, ResidencyCategory("none", weights_bytes, True),
                         ResidencyCategory("none", kv_bytes, False), ResidencyCategory("none", scratch_bytes, False),
                         ResidencyCategory("none", draft_bytes, False), False, 0, 0,
                         "weights, KV, scratch, and draft exceed all available memory", ("oom-prevention",))
