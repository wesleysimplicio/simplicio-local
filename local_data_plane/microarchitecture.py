"""Integration authority for microarchitecture-aware inference decisions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


MICROARCHITECTURE_PLAN_SCHEMA_V1 = "simplicio-local.microarchitecture-plan/v1"


@dataclass(frozen=True)
class MicroarchitecturePlan:
    topology_fingerprint: str
    bottleneck: str
    traversal_mode: str
    prefetch_enabled: bool
    kv_policy: str
    max_context: int
    target_device: str
    draft_device: str
    accepted: bool
    reason: str
    evidence: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {"schema": MICROARCHITECTURE_PLAN_SCHEMA_V1, **self.__dict__, "evidence": list(self.evidence)}


class MicroarchitectureAwarePlanner:
    """Compose measured baseline, topology, placement, traversal and KV policy.

    This class intentionally treats L1/L2/L3 as observations, never as a
    place where an application can pin model weights.
    """

    def plan(self, *, topology: Mapping[str, Any], baseline: Mapping[str, Any],
             traversal: Mapping[str, Any], kv: Mapping[str, Any], execution: Mapping[str, Any]) -> MicroarchitecturePlan:
        if topology.get("schema") != "simplicio-local.hardware-topology/v1":
            raise ValueError("a versioned hardware topology is required")
        fingerprint = str(topology.get("fingerprint", ""))
        if not fingerprint:
            raise ValueError("topology fingerprint is required")
        benchmark_measured = baseline.get("status") == "measured"
        prefetch_requested = bool(traversal.get("prefetch_enabled", False))
        prefetch_enabled = prefetch_requested and benchmark_measured
        traversal_mode = "cache-aware" if prefetch_enabled else "upstream-fallback"
        bottleneck = "unavailable"
        cases = baseline.get("cases", ())
        if cases:
            bottleneck = str((cases[0].get("roofline") or {}).get("classification", "unavailable"))
        accepted = bool(kv.get("accepted")) and bool(execution.get("accepted"))
        reason = "measured plan accepted" if accepted else "baseline-safe fallback: memory or execution plan rejected"
        if not benchmark_measured:
            reason += "; benchmark evidence unavailable, optimization remains disabled"
        evidence = [f"topology:{fingerprint}", f"roofline:{bottleneck}",
                    "cache-observation-not-pinning", f"kv:{kv.get('format', 'unknown')}"]
        return MicroarchitecturePlan(
            fingerprint, bottleneck, traversal_mode, prefetch_enabled,
            str((kv.get("format") or {}).get("name", kv.get("format", "unknown"))),
            int(kv.get("max_context", 0)), str(execution.get("backend", "none")),
            str((execution.get("placement") or {}).get("draft_device", "none")), accepted,
            reason, tuple(evidence))
