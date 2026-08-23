"""Evidence-gated CPU worker and NUMA scheduling hints."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Mapping, Sequence


WORKER_SCHEDULE_SCHEMA_V1 = "simplicio-local.worker-schedule/v1"


@dataclass(frozen=True)
class WorkerSchedule:
    threads: int
    affinity_hint: tuple[int, ...]
    numa_node: int | None
    oversubscribed: bool
    accepted: bool
    reason: str
    evidence: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {"schema": WORKER_SCHEDULE_SCHEMA_V1, **asdict(self)}


def plan_workers(topology: Mapping[str, Any], *, workload: str = "generation",
                 measured: Sequence[Mapping[str, Any]] = (), migration_budget: int = 100,
                 p95_regression_budget: float = 0.10) -> WorkerSchedule:
    physical = topology.get("physical_cpus")
    logical = topology.get("logical_cpus")
    if not isinstance(logical, int) or logical < 1:
        return WorkerSchedule(1, (0,), None, False, True, "logical CPU count unavailable; one-worker fallback", ("safe-fallback",))
    physical_count = physical if isinstance(physical, int) and physical > 0 else logical
    candidates = [row for row in measured if isinstance(row.get("threads"), int) and row["threads"] > 0
                  and isinstance(row.get("throughput"), (int, float))]
    selected = None
    if candidates:
        baseline = max(float(row["throughput"]) for row in candidates)
        eligible = [row for row in candidates if int(row.get("migrations", 0)) <= migration_budget
                    and float(row.get("p95_regression", 0.0)) <= p95_regression_budget]
        if eligible:
            selected = max(eligible, key=lambda row: (float(row["throughput"]), -int(row["threads"])))
    threads = int(selected["threads"]) if selected else min(physical_count, logical)
    threads = max(1, min(threads, logical))
    numa_nodes = topology.get("numa_nodes")
    numa_node = 0 if isinstance(numa_nodes, int) and numa_nodes > 1 else None
    hint = tuple(range(threads))
    oversubscribed = threads > physical_count
    if selected:
        reason = f"selected {threads} threads from measured {workload} candidates"
        evidence = ("measured-throughput", "migration-budget", "tail-latency-budget")
    else:
        reason = "no promotion evidence; conservative physical-core fallback hint selected"
        evidence = ("safe-fallback", "topology-observation")
    if oversubscribed:
        reason += "; SMT oversubscription is explicit"
    return WorkerSchedule(threads, hint, numa_node, oversubscribed, True, reason, evidence)
