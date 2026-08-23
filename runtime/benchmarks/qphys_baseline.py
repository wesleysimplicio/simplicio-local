#!/usr/bin/env python3
"""Reproducible scientific comparison matrix for classical QPHYS methods."""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from typing import Any, Iterable, Mapping


QPHYS_BENCHMARK_SCHEMA_V1 = "simplicio-local.qphys-benchmark/v1"
METHODS = ("fp16", "q8", "q4", "q3", "q2", "low_rank", "tensor_train", "mps", "mpo", "tucker")


@dataclass(frozen=True)
class QPhysMeasurement:
    method: str
    rank: int | None
    quant_bits: int | None
    parameter_bytes: int | None
    resident_bytes: int | None
    bytes_moved_per_token: int | None
    tok_s: float | None
    ttft_ms: float | None
    perplexity: float | None
    task_quality: float | None
    reconstruction_error: float | None
    contraction_flops: int | None
    measured: bool = True


def validate_matrix(metadata: Mapping[str, Any], measurements: Iterable[QPhysMeasurement]) -> list[str]:
    errors: list[str] = []
    for key in ("seed", "corpus", "backend", "hardware", "model_digest"):
        if not str(metadata.get(key, "")).strip():
            errors.append(f"{key} is required")
    methods = {measurement.method for measurement in measurements}
    for required in ("fp16", "q4", "low_rank", "tensor_train", "mpo"):
        if required not in methods:
            errors.append(f"missing comparison method: {required}")
    return errors


def pareto_frontier(measurements: Iterable[QPhysMeasurement], *, quality_floor: float = 0.99) -> tuple[QPhysMeasurement, ...]:
    candidates = [measurement for measurement in measurements if measurement.measured and
                  measurement.resident_bytes is not None and measurement.tok_s is not None and
                  (measurement.task_quality is None or measurement.task_quality >= quality_floor)]
    frontier: list[QPhysMeasurement] = []
    for candidate in candidates:
        dominated = any((other.resident_bytes or 0) <= (candidate.resident_bytes or 0)
                        and (other.tok_s or 0) >= (candidate.tok_s or 0)
                        and ((other.resident_bytes or 0) < (candidate.resident_bytes or 0)
                             or (other.tok_s or 0) > (candidate.tok_s or 0))
                        for other in candidates if other is not candidate)
        if not dominated:
            frontier.append(candidate)
    return tuple(sorted(frontier, key=lambda measurement: (measurement.resident_bytes or 0, measurement.method)))


def create_receipt(metadata: Mapping[str, Any], measurements: Iterable[QPhysMeasurement]) -> dict[str, Any]:
    values = tuple(measurements)
    errors = validate_matrix(metadata, values)
    return {"schema": QPHYS_BENCHMARK_SCHEMA_V1, "status": "invalid" if errors else "measured",
            "metadata": dict(metadata), "errors": errors, "measurements": [asdict(item) for item in values],
            "pareto_frontier": [asdict(item) for item in pareto_frontier(values)],
            "claims": [] if errors else ["The frontier is valid only for the recorded model, corpus, seed, backend, and hardware."]}


def write_receipt(path: str, receipt: Mapping[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as stream:
        json.dump(dict(receipt), stream, indent=2, sort_keys=True)
        stream.write("\n")
