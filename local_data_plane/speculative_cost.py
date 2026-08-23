"""Speculative placement cost envelope shared by Local execution and Fast policy."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Mapping, Sequence


SPECULATIVE_COST_SCHEMA_V1 = "simplicio-local.speculative-cost/v1"


@dataclass(frozen=True)
class CostObservation:
    strategy: str
    placement: str
    target_tok_s: float | None
    draft_tok_s: float | None
    acceptance_rate: float | None
    ttft_ms: float | None
    memory_peak_bytes: int | None
    transfer_bytes: int | None
    bandwidth_pressure: float | None
    cache_miss_rate: float | None
    measured: bool = True


@dataclass(frozen=True)
class SpeculativeCostPlan:
    strategy: str
    placement: str
    accepted: bool
    used_fallback: bool
    reason: str
    observed: CostObservation
    receipt: Mapping[str, Any]


def _valid_observation(observation: CostObservation) -> bool:
    if not observation.measured:
        return False
    if observation.acceptance_rate is not None and not 0 <= observation.acceptance_rate <= 1:
        return False
    return all(value is None or value >= 0 for value in (
        observation.target_tok_s, observation.draft_tok_s, observation.ttft_ms,
        observation.memory_peak_bytes, observation.transfer_bytes,
        observation.bandwidth_pressure, observation.cache_miss_rate))


def select_speculative_cost_plan(*, baseline: CostObservation, candidates: Sequence[CostObservation],
                                 memory_budget_bytes: int, target_headroom_bytes: int,
                                 minimum_throughput_gain: float = 0.02,
                                 maximum_ttft_regression: float = 0.10,
                                 maximum_memory_pressure: float = 0.90) -> SpeculativeCostPlan:
    if not _valid_observation(baseline) or baseline.target_tok_s in (None, 0) or baseline.ttft_ms in (None, 0):
        raise ValueError("measured baseline throughput and TTFT are required")
    best: tuple[float, CostObservation] | None = None
    for candidate in candidates:
        if not _valid_observation(candidate) or candidate.target_tok_s is None or candidate.ttft_ms is None:
            continue
        if candidate.memory_peak_bytes is not None and candidate.memory_peak_bytes > max(0, memory_budget_bytes - target_headroom_bytes):
            continue
        throughput_gain = candidate.target_tok_s / baseline.target_tok_s - 1
        ttft_regression = candidate.ttft_ms / baseline.ttft_ms - 1
        pressure = (candidate.bandwidth_pressure or 0.0)
        if throughput_gain < minimum_throughput_gain or ttft_regression > maximum_ttft_regression or pressure > maximum_memory_pressure:
            continue
        if best is None or throughput_gain > best[0]:
            best = (throughput_gain, candidate)
    if best is None:
        fallback = CostObservation("baseline", "baseline", baseline.target_tok_s, None, None,
                                   baseline.ttft_ms, baseline.memory_peak_bytes, 0, baseline.bandwidth_pressure,
                                   baseline.cache_miss_rate)
        return SpeculativeCostPlan("baseline", "baseline", True, True,
                                   "no speculative candidate passed throughput, TTFT, memory, and pressure gates",
                                   fallback, _receipt(fallback, True, True))
    candidate = best[1]
    return SpeculativeCostPlan(candidate.strategy, candidate.placement, True, False,
                               "candidate passed measured throughput, TTFT, memory, and pressure gates",
                               candidate, _receipt(candidate, True, False))


def _receipt(observation: CostObservation, accepted: bool, fallback: bool) -> dict[str, Any]:
    return {"schema": SPECULATIVE_COST_SCHEMA_V1, "accepted": accepted, "used_fallback": fallback,
            "strategy": observation.strategy, "placement": observation.placement,
            "observation": asdict(observation)}
