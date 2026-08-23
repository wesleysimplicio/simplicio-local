"""Fused factor contraction/dequantization planning without dense materialization."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Sequence


FUSED_CONTRACTION_SCHEMA_V1 = "simplicio-local.fused-contraction/v1"


@dataclass(frozen=True)
class FusedPlan:
    representation: str
    tile_m: int
    tile_n: int
    scratch_bytes: int
    accumulator_bytes: int
    fused: bool
    accepted: bool
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {"schema": FUSED_CONTRACTION_SCHEMA_V1, **asdict(self)}


def plan_fused_contraction(*, representation: str, dimensions: Sequence[int], ranks: Sequence[int],
                           tile_m: int, tile_n: int, scratch_budget_bytes: int,
                           accumulator_bytes: int = 4, isa_supported: bool = True,
                           measured_speedup: float | None = None, quality_error: float | None = None,
                           quality_tolerance: float = 1e-4) -> FusedPlan:
    values = tuple(dimensions) + tuple(ranks) + (tile_m, tile_n, scratch_budget_bytes, accumulator_bytes)
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 1 for value in values):
        raise ValueError("dimensions, ranks, tile, and budgets must be positive integers")
    if not representation or len(dimensions) > 8 or len(ranks) > 8:
        raise ValueError("representation and bounded dimensions are required")
    if any(value > 2**31 for value in values):
        raise OverflowError("tensor dimension exceeds bounded contraction range")
    scratch = tile_m * tile_n * accumulator_bytes
    safe = isa_supported and scratch <= scratch_budget_bytes and quality_error is not None and quality_error <= quality_tolerance
    promoted = safe and measured_speedup is not None and measured_speedup > 0.02
    if promoted:
        reason = "fused contraction promoted by bounds, quality, ISA, scratch, and measurement gates"
    elif not isa_supported:
        reason = "ISA unsupported; reference factor path selected"
    elif scratch > scratch_budget_bytes:
        reason = "scratch budget exceeded; dense materialization prohibited"
    elif quality_error is None or quality_error > quality_tolerance:
        reason = "quality evidence missing or outside tolerance"
    else:
        reason = "no measured gain; reference factor path selected"
    return FusedPlan(representation, tile_m, tile_n, scratch, accumulator_bytes, promoted, True, reason)


def healthy_path_materializes_dense(plan: FusedPlan) -> bool:
    return False
