"""Unified deterministic ExecutionPlan v2 authority."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping


EXECUTION_PLAN_V2_SCHEMA = "simplicio-local.execution-plan/v2"


@dataclass(frozen=True)
class UnifiedExecutionPlan:
    payload: Mapping[str, Any]
    digest: str

    def as_dict(self) -> dict[str, Any]:
        return {"schema": EXECUTION_PLAN_V2_SCHEMA, "digest": self.digest, "plan": dict(self.payload)}


def _canonical(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def build_execution_plan(*, model: Mapping[str, Any], artifact: Mapping[str, Any],
                         topology: Mapping[str, Any], workers: Mapping[str, Any],
                         kernel: Mapping[str, Any], placement: Mapping[str, Any],
                         kv: Mapping[str, Any], mmap: Mapping[str, Any],
                         residency: Mapping[str, Any], speculative: Mapping[str, Any],
                         baseline: Mapping[str, Any], measured_generation: str | None = None) -> UnifiedExecutionPlan:
    model_id = str(model.get("model_id", ""))
    artifact_digest = str(artifact.get("sha256", artifact.get("digest", "")))
    topology_digest = str(topology.get("fingerprint", ""))
    if not model_id or not artifact_digest or not topology_digest:
        raise ValueError("model, artifact digest, and topology fingerprint are required")
    fallback_ladder = ["selected-plan", "cpu-baseline", "cannot_fit"]
    if not bool(kv.get("accepted")) or not bool(placement.get("accepted", True)):
        selected_state = "cannot_fit"
    else:
        selected_state = "selected-plan"
    payload: dict[str, Any] = {
        "identity": {"model": model_id, "artifact_sha256": artifact_digest,
                     "backend": model.get("backend", placement.get("backend", "unknown")),
                     "topology_fingerprint": topology_digest},
        "workers": dict(workers), "kernel": dict(kernel), "placement": dict(placement),
        "kv": dict(kv), "mmap": dict(mmap), "residency": dict(residency),
        "speculative": dict(speculative), "baseline": dict(baseline),
        "fallback_ladder": fallback_ladder, "selected_state": selected_state,
        "measured_generation": measured_generation,
        "observed_vs_estimated": {"observed": {}, "estimated": {}},
    }
    rendered = _canonical(payload)
    return UnifiedExecutionPlan(payload, hashlib.sha256(rendered.encode()).hexdigest())


def validate_execution_plan(plan: UnifiedExecutionPlan, *, available_isa: set[str] | None = None,
                            current_tuning_generation: str | None = None) -> tuple[bool, str]:
    if plan.as_dict()["schema"] != EXECUTION_PLAN_V2_SCHEMA:
        return False, "unsupported-plan-schema"
    selected = plan.payload.get("selected_state")
    if selected not in {"selected-plan", "cpu-baseline", "cannot_fit"}:
        return False, "invalid-selected-state"
    if selected == "cannot_fit":
        return False, "cannot_fit"
    kernel = plan.payload.get("kernel", {})
    required = set(kernel.get("isa_requirements", ()))
    if available_isa is not None and not required.issubset(available_isa):
        return False, "unsupported-isa"
    planned_generation = plan.payload.get("measured_generation")
    if planned_generation and current_tuning_generation and planned_generation != current_tuning_generation:
        return False, "stale-tuning-generation"
    return True, "plan-valid"
