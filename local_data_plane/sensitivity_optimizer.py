"""Sensitivity-aware QPHYS rank/bit allocation with quality gates."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, asdict
from typing import Any, Mapping, Sequence


SENSITIVITY_SCHEMA_V1 = "simplicio-local.qphys-sensitivity/v1"


@dataclass(frozen=True)
class LayerSensitivity:
    layer: str
    score: float
    baseline_bytes: int
    candidate_bytes: int
    candidate_quality: float
    options: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class AllocationPlan:
    policy_digest: str
    allocations: Mapping[str, tuple[int, int]]
    resident_bytes: int
    quality: float
    accepted: bool
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {"schema": SENSITIVITY_SCHEMA_V1, **asdict(self)}


def optimize_allocation(*, model_digest: str, corpus_digest: str, policy_version: str,
                        layers: Sequence[LayerSensitivity], memory_budget: int,
                        quality_threshold: float) -> AllocationPlan:
    if not layers or memory_budget <= 0 or not model_digest or not corpus_digest:
        raise ValueError("model/corpus identity, layers, and memory budget are required")
    payload = {"model": model_digest, "corpus": corpus_digest, "policy": policy_version}
    policy_digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    ordered = sorted(layers, key=lambda layer: (-layer.score, layer.layer))
    allocations: dict[str, tuple[int, int]] = {}
    resident = 0
    quality = 1.0
    for layer in ordered:
        choices = sorted(layer.options, key=lambda option: (option[1], -option[0]))
        chosen = next((option for option in choices if resident + option[1] <= memory_budget and layer.candidate_quality >= quality_threshold), None)
        if chosen is None:
            chosen = (16, layer.baseline_bytes)
            quality *= max(0.0, min(1.0, layer.candidate_quality))
        allocations[layer.layer] = chosen
        resident += chosen[1]
    accepted = resident <= memory_budget and quality >= quality_threshold
    return AllocationPlan(policy_digest, allocations, resident, quality, accepted,
                          "sensitivity-aware allocation passed quality and memory gates" if accepted
                          else "allocation remains baseline-safe; quality or memory gate failed")
