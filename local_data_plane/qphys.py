"""Reversible quantum-inspired tensor-network metadata and promotion gates.

This module describes classical tensor decompositions; it does not require or
claim qubits, quantum memory, or quantum hardware.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Mapping


QPHYS_SCHEMA_V1 = "simplicio-local.qphys/v1"
METHODS = {"low_rank", "tensor_train", "mps", "mpo", "tucker", "tensor_ring"}


@dataclass(frozen=True)
class FactorizedRepresentation:
    method: str
    original_shape: tuple[int, ...]
    ranks: tuple[int, ...]
    quant_bits: int
    materialize_full_precision: bool = False
    experimental: bool = True

    def validate(self) -> None:
        if self.method not in METHODS:
            raise ValueError("unsupported QPHYS method")
        if not self.original_shape or any(value < 1 for value in self.original_shape):
            raise ValueError("original_shape must contain positive dimensions")
        if not self.ranks or any(value < 1 for value in self.ranks):
            raise ValueError("ranks must contain positive dimensions")
        if self.quant_bits not in {2, 3, 4, 8, 16}:
            raise ValueError("quant_bits is unsupported")
        if self.materialize_full_precision:
            raise ValueError("QPHYS representation cannot materialize full precision weights")


@dataclass(frozen=True)
class QPhysPromotion:
    accepted: bool
    method: str
    reason: str
    representation: FactorizedRepresentation | None
    metrics: Mapping[str, float | int | None]

    def as_dict(self) -> dict[str, Any]:
        return {"schema": QPHYS_SCHEMA_V1, "accepted": self.accepted, "method": self.method,
                "reason": self.reason, "representation": asdict(self.representation) if self.representation else None,
                "metrics": dict(self.metrics)}


def promote_qphys(*, baseline_quality: float, candidate_quality: float, baseline_bytes: int,
                  candidate_bytes: int, baseline_tok_s: float | None, candidate_tok_s: float | None,
                  representation: FactorizedRepresentation, max_quality_drop: float = 0.01,
                  minimum_memory_reduction: float = 0.10) -> QPhysPromotion:
    representation.validate()
    if baseline_bytes <= 0 or candidate_bytes <= 0 or baseline_quality <= 0 or candidate_quality <= 0:
        raise ValueError("baseline and candidate measurements must be positive")
    quality_drop = (baseline_quality - candidate_quality) / baseline_quality
    memory_reduction = 1 - candidate_bytes / baseline_bytes
    speedup = None if baseline_tok_s in (None, 0) or candidate_tok_s is None else candidate_tok_s / baseline_tok_s - 1
    metrics = {"quality_drop": quality_drop, "memory_reduction": memory_reduction, "speedup": speedup,
               "baseline_bytes": baseline_bytes, "candidate_bytes": candidate_bytes}
    accepted = quality_drop <= max_quality_drop and memory_reduction >= minimum_memory_reduction
    reason = "quality and memory gates passed" if accepted else "QPHYS candidate remains experimental; promotion gates failed"
    return QPhysPromotion(accepted, representation.method, reason, representation if accepted else None, metrics)
