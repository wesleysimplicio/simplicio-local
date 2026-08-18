"""Orthogonal inference profiles and evidence-gated TurboQuant.

The Runtime can request a TurboQuant profile, but Local may only report it as
active when an executor and the corresponding observed evidence are present.
This keeps a profile request from becoming a false claim about the physical
kernel that actually ran.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import FrozenSet

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


TURBOQUANT_PROFILES = frozenset({"compatibility", "quality", "balanced", "memory", "safe-compressed"})


@dataclass(frozen=True)
class TurboQuantCapabilities:
    """Advertised physical TurboQuant support for one Local backend."""

    backend: str
    executor_available: bool = False
    weight_profiles: FrozenSet[str] = frozenset()
    cache_profiles: FrozenSet[str] = frozenset()
    kv_profiles: FrozenSet[str] = frozenset()
    evidence_level: EvidenceLevel = EvidenceLevel.SOURCE_PRESENT
    reason: str = "TurboQuant executor is not installed"

    def validate(self) -> None:
        if not self.backend.strip():
            raise ValueError("TurboQuant capability backend is required")
        if not self.weight_profiles.issubset(TURBOQUANT_PROFILES):
            raise ValueError("unsupported TurboQuant weight profile")
        if not self.cache_profiles.issubset(TURBOQUANT_PROFILES):
            raise ValueError("unsupported TurboQuant cache profile")
        if not self.kv_profiles.issubset(TURBOQUANT_PROFILES):
            raise ValueError("unsupported TurboQuant KV profile")
        if not self.executor_available and not self.reason.strip():
            raise ValueError("unavailable TurboQuant capability requires a reason")


@dataclass(frozen=True)
class ResolvedTurboQuantProfile:
    requested: str
    effective: str
    active: bool
    degraded: bool
    reason: str
    backend: str
    evidence_level: EvidenceLevel

    def as_dict(self) -> dict[str, object]:
        return {
            "requested": self.requested,
            "effective": self.effective,
            "active": self.active,
            "degraded": self.degraded,
            "reason": self.reason,
            "backend": self.backend,
            "evidence_level": self.evidence_level.name_value,
        }


def resolve_turboquant_profile(
    requested: str | None,
    capabilities: TurboQuantCapabilities,
    *,
    allow_fallback: bool,
) -> ResolvedTurboQuantProfile:
    """Resolve a Runtime profile without silently enabling a missing kernel."""

    capabilities.validate()
    profile = (requested or "compatibility").strip().lower()
    if profile not in TURBOQUANT_PROFILES:
        raise ValueError(f"unsupported TurboQuant profile: {profile!r}")
    if profile == "compatibility":
        return ResolvedTurboQuantProfile(profile, profile, False, False,
                                          "compatibility profile does not require TurboQuant",
                                          capabilities.backend, capabilities.evidence_level)
    supported_profiles = capabilities.weight_profiles | capabilities.cache_profiles
    if capabilities.executor_available and profile in supported_profiles:
        return ResolvedTurboQuantProfile(profile, profile, True, False,
                                          "TurboQuant executor and profile are available",
                                          capabilities.backend, capabilities.evidence_level)
    reason = capabilities.reason or "requested TurboQuant profile is unavailable"
    if not allow_fallback:
        raise RuntimeError(f"TurboQuant profile {profile!r} unavailable: {reason}")
    return ResolvedTurboQuantProfile(profile, "compatibility", False, True,
                                     f"fallback to compatibility: {reason}",
                                     capabilities.backend, capabilities.evidence_level)


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
