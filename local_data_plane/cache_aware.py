"""Cache-aware traversal and bounded prefetch decisions with safe fallback."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence


CACHE_AWARE_SCHEMA_V1 = "simplicio-local.cache-aware-plan/v1"


@dataclass(frozen=True)
class TraversalPlan:
    order: tuple[int, ...]
    block_bytes: int
    alignment_bytes: int
    prefetch_distance: int
    prefetch_enabled: bool
    reason: str
    fallback: str = "upstream-order"

    def as_dict(self) -> dict[str, Any]:
        return {"schema": CACHE_AWARE_SCHEMA_V1, **self.__dict__}


def _aligned(value: int, alignment: int) -> bool:
    return alignment > 0 and value % alignment == 0


def plan_traversal(block_count: int, block_bytes: int, *, cache_line_bytes: int = 64,
                   alignment_bytes: int = 64, prefetch_distance: int = 0,
                   input_bytes: int | None = None, measured_speedup: float | None = None,
                   regression: bool = False, prefetch_budget_bytes: int = 64 * 1024) -> TraversalPlan:
    values = (block_count, block_bytes, cache_line_bytes, alignment_bytes, prefetch_distance, prefetch_budget_bytes)
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in values):
        raise ValueError("traversal dimensions must be non-negative integers")
    if block_count == 0 or block_bytes == 0:
        return TraversalPlan((), block_bytes, alignment_bytes, 0, False, "empty-input-fallback")
    order = tuple(range(block_count))
    if not _aligned(block_bytes, alignment_bytes):
        return TraversalPlan(order, block_bytes, alignment_bytes, 0, False,
                             "unaligned-blocks-preserve-upstream-path")
    requested = min(prefetch_distance, block_count - 1)
    prefetch_bytes = requested * block_bytes
    bounds_ok = input_bytes is None or input_bytes >= block_count * block_bytes
    evidence_ok = measured_speedup is not None and measured_speedup > 0.02 and not regression
    enabled = requested > 0 and prefetch_bytes <= prefetch_budget_bytes and bounds_ok and evidence_ok
    if enabled:
        reason = "prefetch-enabled-by-positive-bounded-measurement"
    elif regression:
        reason = "regression-detected-auto-disabled"
    elif not bounds_ok:
        reason = "input-bounds-unproven-auto-disabled"
    elif measured_speedup is None:
        reason = "no-measurement-auto-disabled"
    elif prefetch_bytes > prefetch_budget_bytes:
        reason = "prefetch-budget-exceeded-auto-disabled"
    else:
        reason = "measurement-below-promotion-threshold"
    return TraversalPlan(order, block_bytes, alignment_bytes, requested if enabled else 0, enabled, reason)


def reorder_blocks(blocks: Sequence[bytes], *, cache_line_bytes: int = 64) -> tuple[bytes, ...]:
    """Return a contiguous stable order without changing public GGUF layout."""
    if cache_line_bytes <= 0:
        raise ValueError("cache_line_bytes must be positive")
    return tuple(blocks)
