"""Orthogonal inference profiles and evidence-gated TurboQuant."""

from __future__ import annotations

from dataclasses import dataclass

from .registry import EvidenceLevel


@dataclass(frozen=True)
class InferenceProfile:
    storage: str = "resident"
    weight_quantization: str = "native"
    kv_quantization: str = "native"
    offload: str = "none"
    speculation: str = "disabled"
    workload: str = "interactive"
    experimental: bool = False

    def validate(self) -> None:
        allowed = {
            "storage": {"resident", "mmap", "expert-stream", "layer-stream"},
            "weight_quantization": {"native", "int8", "int4", "q4_k_m", "turboquant"},
            "kv_quantization": {"native", "int8", "int4", "turboquant"},
            "offload": {"none", "cpu", "metal", "cuda", "ane"},
            "speculation": {"disabled", "mtp", "draft"},
            "workload": {"interactive", "background", "deep-offline"},
        }
        for name, values in allowed.items():
            if getattr(self, name) not in values:
                raise ValueError(f"unsupported {name}: {getattr(self, name)!r}")
        if self.storage == "layer-stream" and self.workload == "interactive":
            raise ValueError("layer-stream requires explicit background or deep-offline workload")
        if self.storage == "expert-stream" and self.workload == "interactive":
            raise ValueError("expert-stream is not an interactive profile")
        if self.weight_quantization == "turboquant" and self.kv_quantization == "turboquant":
            raise ValueError("weight and KV TurboQuant promotion must be evidenced independently")

    def as_dict(self) -> dict[str, object]:
        self.validate()
        return self.__dict__.copy()


@dataclass(frozen=True)
class TurboQuantResult:
    requested: bool
    active: bool
    evidence_level: EvidenceLevel
    reason: str
    backend: str
    quality_error: float | None = None


def validate_turboquant(
    *,
    requested: bool,
    backend: str,
    backend_evidence: EvidenceLevel,
    reference: list[float] | None,
    candidate: list[float] | None,
    max_relative_error: float = 0.02,
) -> TurboQuantResult:
    if not requested:
        return TurboQuantResult(False, False, backend_evidence, "not requested", backend)
    if backend_evidence < EvidenceLevel.FIXTURE_EXECUTED:
        return TurboQuantResult(True, False, backend_evidence,
                                "backend has no observed execution evidence", backend)
    if reference is None or candidate is None or len(reference) != len(candidate) or not reference:
        return TurboQuantResult(True, False, backend_evidence,
                                "reference and candidate quality vectors are required", backend)
    error = max(abs(a - b) / max(1.0, abs(a)) for a, b in zip(reference, candidate))
    if error > max_relative_error:
        return TurboQuantResult(True, False, backend_evidence,
                                "quality gate exceeded", backend, error)
    level = max(backend_evidence, EvidenceLevel.FIXTURE_EXECUTED)
    return TurboQuantResult(True, True, level, "quality gate passed", backend, error)
