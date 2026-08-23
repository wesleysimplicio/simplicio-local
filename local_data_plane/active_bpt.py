"""Active-parameter and bytes-per-token planner for dense/MoE models."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Mapping, Sequence


ACTIVE_BPT_SCHEMA_V1 = "simplicio-local.active-bpt/v1"


@dataclass(frozen=True)
class ActiveCost:
    model_id: str
    architecture: str
    total_parameters: int
    active_parameters_per_token: int | None
    weight_bytes_per_token: int | None
    kv_bytes_per_token: int | None
    bandwidth_bytes_per_second: int | None
    confidence: str
    expert_residency: str
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {"schema": ACTIVE_BPT_SCHEMA_V1, **asdict(self)}


def estimate_active_cost(*, model_id: str, architecture: str, total_parameters: int,
                         bytes_per_parameter: float, active_parameters_per_token: int | None = None,
                         kv_bytes_per_token: int | None = None, measured_weight_bytes_per_token: int | None = None,
                         bandwidth_bytes_per_second: int | None = None,
                         expert_residency: str = "unknown") -> ActiveCost:
    if total_parameters <= 0 or bytes_per_parameter <= 0 or not model_id:
        raise ValueError("model identity and positive parameter metadata are required")
    if architecture not in {"dense", "moe", "conditional"}:
        raise ValueError("architecture must be dense, moe, or conditional")
    if architecture != "dense" and active_parameters_per_token is None:
        return ActiveCost(model_id, architecture, total_parameters, None, measured_weight_bytes_per_token,
                          kv_bytes_per_token, bandwidth_bytes_per_second, "unknown", expert_residency,
                          "active parameter count was not explicitly measured or declared")
    active = total_parameters if architecture == "dense" else active_parameters_per_token
    weight_bpt = measured_weight_bytes_per_token
    if weight_bpt is None and active is not None:
        weight_bpt = int(active * bytes_per_parameter)
    confidence = "measured" if measured_weight_bytes_per_token is not None else "estimated"
    return ActiveCost(model_id, architecture, total_parameters, active, weight_bpt, kv_bytes_per_token,
                      bandwidth_bytes_per_second, confidence, expert_residency,
                      "active cost uses explicit architecture metadata")


def rank_by_active_cost(costs: Sequence[ActiveCost]) -> tuple[ActiveCost, ...]:
    return tuple(sorted(costs, key=lambda cost: (cost.weight_bytes_per_token is None,
                                                   cost.weight_bytes_per_token or 2**63,
                                                   cost.model_id)))
