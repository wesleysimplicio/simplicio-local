"""Explicit telemetry levels, overhead budgets and graceful degradation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping


TELEMETRY_SCHEMA_V1 = "simplicio-local.telemetry-levels/v1"


class TelemetryLevel(str, Enum):
    MINIMAL = "minimal"
    STANDARD = "standard"
    DEEP = "deep"


_METRICS = {
    TelemetryLevel.MINIMAL: ("tok_s", "ttft_ms", "peak_memory_bytes", "acceptance_rate", "plan_digest"),
    TelemetryLevel.STANDARD: ("tok_s", "ttft_ms", "peak_memory_bytes", "acceptance_rate", "plan_digest",
                              "bandwidth_class", "transfer_bytes", "kv_bytes_per_token", "placement"),
    TelemetryLevel.DEEP: ("tok_s", "ttft_ms", "peak_memory_bytes", "acceptance_rate", "plan_digest",
                          "bandwidth_class", "transfer_bytes", "kv_bytes_per_token", "placement",
                          "ipc", "cache_misses", "energy_per_token", "roofline"),
}


@dataclass(frozen=True)
class TelemetryReceipt:
    requested: TelemetryLevel
    effective: TelemetryLevel
    available_metrics: tuple[str, ...]
    unavailable: Mapping[str, str]
    overhead_ms: float | None
    budget_ms: float
    metrics: Mapping[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {"schema": TELEMETRY_SCHEMA_V1, "requested": self.requested.value,
                "effective": self.effective.value, "available_metrics": list(self.available_metrics),
                "unavailable": dict(self.unavailable), "overhead_ms": self.overhead_ms,
                "budget_ms": self.budget_ms, "metrics": dict(self.metrics)}


def collect_telemetry(*, requested: str, available: Mapping[str, Any], overhead_ms: float | None,
                      budget_ms: float) -> TelemetryReceipt:
    try:
        requested_level = TelemetryLevel(requested)
    except ValueError as exc:
        raise ValueError("requested telemetry level must be minimal, standard, or deep") from exc
    if budget_ms < 0:
        raise ValueError("telemetry budget must be non-negative")
    effective = requested_level
    if overhead_ms is not None and overhead_ms > budget_ms and requested_level == TelemetryLevel.DEEP:
        effective = TelemetryLevel.STANDARD
    if overhead_ms is not None and overhead_ms > budget_ms and effective == TelemetryLevel.STANDARD:
        effective = TelemetryLevel.MINIMAL
    requested_metrics = set(_METRICS[effective])
    metrics = {key: available[key] for key in requested_metrics if key in available}
    unavailable = {key: "metric unavailable or unsupported at effective level" for key in _METRICS[effective] if key not in metrics}
    return TelemetryReceipt(requested_level, effective, tuple(sorted(metrics)), unavailable,
                            overhead_ms, budget_ms, metrics)
