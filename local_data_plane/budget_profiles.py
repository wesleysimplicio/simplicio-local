"""Versioned first-class memory/bandwidth/placement budget profiles."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, asdict
from typing import Any, Mapping, Sequence


BUDGET_PROFILE_SCHEMA_V1 = "simplicio-local.budget-profile/v1"


@dataclass(frozen=True)
class BudgetProfile:
    profile_id: str
    memory_class: str
    resident_bytes: int
    headroom_fraction: float
    bandwidth_class: str
    preferred_placement: str
    quality_threshold: float
    max_context_default: int
    version: str
    notes: tuple[str, ...] = ()

    @property
    def digest(self) -> str:
        payload = json.dumps(asdict(self), sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(payload).hexdigest()

    def as_dict(self) -> dict[str, Any]:
        return {"schema": BUDGET_PROFILE_SCHEMA_V1, **asdict(self), "digest": self.digest}


def canonical_profiles() -> tuple[BudgetProfile, ...]:
    return (
        BudgetProfile("cpu-8gb", "8gb", 8 * 1024**3, 0.15, "low", "cpu", 0.99, 2048, "v1"),
        BudgetProfile("cpu-16gb", "16gb", 16 * 1024**3, 0.15, "medium", "cpu", 0.99, 4096, "v1"),
        BudgetProfile("cpu-32gb", "32gb", 32 * 1024**3, 0.15, "medium", "cpu", 0.99, 8192, "v1"),
        BudgetProfile("apple-unified-16gb", "unified-16gb", 16 * 1024**3, 0.15, "medium", "unified", 0.99, 4096, "v1"),
        BudgetProfile("apple-unified-48gb", "unified-48gb", 48 * 1024**3, 0.15, "high", "unified", 0.995, 16384, "v1"),
        BudgetProfile("cuda-12gb", "vram-12gb", 12 * 1024**3, 0.15, "high", "gpu", 0.99, 4096, "v1"),
    )


def select_budget_profile(*, platform: str, backend: str, available_bytes: int,
                          profiles: Sequence[BudgetProfile] | None = None) -> BudgetProfile:
    if available_bytes <= 0:
        raise ValueError("available memory must be positive")
    choices = tuple(profiles or canonical_profiles())
    known_platform = platform in {"linux", "darwin", "windows"}
    compatible = [profile for profile in choices
                  if profile.resident_bytes <= available_bytes and
                  known_platform and ((backend == "cuda" and profile.preferred_placement == "gpu") or
                   (platform == "darwin" and profile.preferred_placement == "unified") or
                   (backend == "cpu" and profile.preferred_placement == "cpu"))]
    if compatible:
        return max(compatible, key=lambda profile: profile.resident_bytes)
    return BudgetProfile("custom", "custom", available_bytes, 0.15, "measured", backend if backend in {"cpu", "gpu", "unified", "hybrid"} else "cpu",
                         0.99, 2048, "v1", ("no canonical profile matched; use measured values",))
