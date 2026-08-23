"""Memory-tiered compressed weight planning with measured SSD break-even gates."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


TIERED_WEIGHTS_SCHEMA_V1 = "simplicio-local.tiered-weights/v1"


@dataclass(frozen=True)
class TieredWeightPlan:
    mode: str
    resident_bytes: int
    streamed_bytes: int
    bytes_per_token: int
    predicted_io_ms_per_token: float
    pagein_queue: int
    accepted: bool
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {"schema": TIERED_WEIGHTS_SCHEMA_V1, **asdict(self)}


def plan_tiered_weights(*, artifact_bytes: int, resident_budget_bytes: int,
                        predicted_bytes_per_token: int, ssd_bandwidth_bytes: float,
                        ssd_latency_ms: float, latency_budget_ms: float,
                        pagein_queue: int = 1, observed_page_fault_rate: float | None = None,
                        conditional_access: bool = False) -> TieredWeightPlan:
    values = (artifact_bytes, resident_budget_bytes, predicted_bytes_per_token, pagein_queue)
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in values):
        raise ValueError("tiering dimensions must be non-negative integers")
    if artifact_bytes <= 0 or resident_budget_bytes <= 0 or ssd_bandwidth_bytes <= 0 or latency_budget_ms <= 0:
        raise ValueError("artifact, budget, bandwidth, and latency budget must be positive")
    if artifact_bytes <= resident_budget_bytes:
        return TieredWeightPlan("full-resident", artifact_bytes, 0, 0, 0, 0, True,
                                "full residency fits and remains preferred")
    streamed = artifact_bytes - resident_budget_bytes
    io_ms = (predicted_bytes_per_token / ssd_bandwidth_bytes) * 1000 if predicted_bytes_per_token else 0
    thrashing = observed_page_fault_rate is not None and observed_page_fault_rate > 0.25
    accepted = conditional_access and io_ms <= latency_budget_ms and not thrashing
    if accepted:
        return TieredWeightPlan("tiered-mmap-ssd", resident_budget_bytes, streamed, predicted_bytes_per_token,
                                io_ms, min(pagein_queue, 8), True,
                                "conditional-access page-in is below measured latency budget")
    reason = "page-thrash detected; streaming disabled" if thrashing else \
             "predicted page-in exceeds latency budget or conditional access is unproven"
    return TieredWeightPlan("cannot-fit", resident_budget_bytes, streamed, predicted_bytes_per_token,
                            io_ms, 0, False, reason)
