"""Evidence report for Qwen3.8-27B compression budgets."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Iterable, Mapping


QWEN_EXPERIMENT_SCHEMA_V1 = "simplicio-local.qwen38-compression/v1"
STATUSES = {"usable", "experimental_slow", "quality_regression", "cannot_fit"}


@dataclass(frozen=True)
class VariantResult:
    budget_gib: int
    variant: str
    resident_bytes: int
    peak_bytes: int
    bpt: int | None
    kv_bytes_per_token: int | None
    ttft_ms: float | None
    tok_s: float | None
    p95_ms: float | None
    quality_delta: float | None
    endpoint_completed: bool
    evidence_id: str


def classify_variant(result: VariantResult, *, quality_threshold: float = -0.02,
                     latency_budget_ms: float = 2000) -> str:
    if result.peak_bytes > result.budget_gib * 1024**3 or not result.endpoint_completed:
        return "cannot_fit"
    if result.quality_delta is None or result.quality_delta < quality_threshold:
        return "quality_regression"
    if result.ttft_ms is None or result.tok_s is None or result.p95_ms is None:
        return "experimental_slow"
    if result.ttft_ms > latency_budget_ms or result.p95_ms > latency_budget_ms:
        return "experimental_slow"
    return "usable"


def create_experiment_report(metadata: Mapping[str, Any], results: Iterable[VariantResult]) -> dict[str, Any]:
    values = tuple(results)
    errors = [key for key in ("model_digest", "hardware", "corpus", "seed") if not metadata.get(key)]
    rows = [{**asdict(result), "status": classify_variant(result)} for result in values]
    pareto = [row for row in rows if row["status"] == "usable"]
    return {"schema": QWEN_EXPERIMENT_SCHEMA_V1, "status": "invalid" if errors else "measured",
            "metadata": dict(metadata), "errors": errors, "results": rows,
            "pareto_by_budget": {str(budget): [row for row in pareto if row["budget_gib"] == budget]
                                  for budget in (8, 16, 24, 32)},
            "alternatives": ["smaller-reference-model", "moe-reference-model"],
            "claims": [] if errors else ["Statuses are valid only for the recorded hardware, corpus, seed, and endpoint evidence."]}
