"""Fail-closed target/draft placement planning for local inference."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


MEMORY_PLACEMENT_SCHEMA_V1 = "simplicio-local.memory-placement/v1"
_DEVICES = {"cpu", "cuda", "metal", "unified"}


@dataclass(frozen=True)
class MemoryRequirements:
    target_bytes: int
    draft_bytes: int = 0
    kv_cache_bytes: int = 0
    working_bytes: int = 0

    @property
    def total_bytes(self) -> int:
        return self.target_bytes + self.draft_bytes + self.kv_cache_bytes + self.working_bytes

    def validate(self) -> None:
        values = (self.target_bytes, self.draft_bytes, self.kv_cache_bytes, self.working_bytes)
        if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in values):
            raise ValueError("memory requirements must be non-negative integers")
        if self.target_bytes == 0:
            raise ValueError("target_bytes must be positive")


@dataclass(frozen=True)
class MemoryObservation:
    target_bytes: int | None = None
    draft_bytes: int | None = None
    kv_cache_bytes: int | None = None
    working_bytes: int | None = None

    def as_dict(self) -> dict[str, int | None]:
        return {
            "target_bytes": self.target_bytes,
            "draft_bytes": self.draft_bytes,
            "kv_cache_bytes": self.kv_cache_bytes,
            "working_bytes": self.working_bytes,
        }


@dataclass(frozen=True)
class PlacementPlan:
    target_device: str
    draft_device: str
    mode: str
    accepted: bool
    reason: str
    usable_memory_bytes: int
    estimated_total_bytes: int
    headroom_bytes: int
    estimated: MemoryRequirements
    observed: MemoryObservation = MemoryObservation()

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": MEMORY_PLACEMENT_SCHEMA_V1,
            "target_device": self.target_device,
            "draft_device": self.draft_device,
            "mode": self.mode,
            "accepted": self.accepted,
            "reason": self.reason,
            "usable_memory_bytes": self.usable_memory_bytes,
            "estimated_total_bytes": self.estimated_total_bytes,
            "headroom_bytes": self.headroom_bytes,
            "estimated": self.estimated.__dict__.copy(),
            "observed": self.observed.as_dict(),
        }


def _positive(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


class MemoryAwarePlacementPlanner:
    """Select full-device, hybrid, or CPU placement without trusting names."""

    def __init__(self, hardware: Mapping[str, Any], *, reserve_fraction: float = 0.15,
                 minimum_reserve_bytes: int = 512 * 1024 * 1024):
        self.hardware = dict(hardware)
        if not 0.0 <= reserve_fraction < 0.9:
            raise ValueError("reserve_fraction must be in [0, 0.9)")
        self.reserve_fraction = reserve_fraction
        self.minimum_reserve_bytes = _positive(minimum_reserve_bytes, "minimum_reserve_bytes")

    def _capacity(self, key: str) -> int:
        return _positive(self.hardware.get(key, 0), key)

    def _usable(self, capacity: int) -> int:
        reserve = max(self.minimum_reserve_bytes, int(capacity * self.reserve_fraction))
        return max(0, capacity - reserve)

    def plan(self, requirements: MemoryRequirements, *, observed: MemoryObservation | None = None) -> PlacementPlan:
        requirements.validate()
        backend = str(self.hardware.get("backend", "cpu")).lower()
        if backend not in _DEVICES:
            raise ValueError(f"unsupported backend: {backend}")
        system = self._capacity("available_system_bytes") or self._capacity("system_memory_bytes")
        gpu = self._capacity("available_gpu_bytes") or self._capacity("gpu_memory_bytes")
        unified = self._capacity("available_unified_bytes") or self._capacity("unified_memory_bytes")
        if backend == "unified":
            capacity = unified or system
        elif backend in {"cuda", "metal"}:
            capacity = gpu
        else:
            capacity = system
        usable = self._usable(capacity)
        total = requirements.total_bytes
        if usable >= total:
            device = "unified" if backend == "unified" else backend
            return PlacementPlan(device, device if requirements.draft_bytes else "none", "full-device", True,
                                 "estimated working set fits reserved device memory", usable, total, usable - total,
                                 requirements, observed or MemoryObservation())

        separate_draft = bool(self.hardware.get("separate_draft_device_supported", False))
        target_only = requirements.target_bytes + requirements.kv_cache_bytes + requirements.working_bytes
        system_usable = self._usable(system)
        if backend in {"cuda", "metal"} and separate_draft and system_usable >= total:
            return PlacementPlan(backend, "cpu", "hybrid-target-device-draft-cpu", True,
                                 "draft moved to CPU after device budget check", system_usable, total,
                                 system_usable - total, requirements, observed or MemoryObservation())
        if system_usable >= target_only:
            return PlacementPlan("cpu", "cpu" if requirements.draft_bytes else "none", "cpu-fallback", True,
                                 "device budget is insufficient; CPU working set fits", system_usable, total,
                                 system_usable - target_only, requirements, observed or MemoryObservation())
        return PlacementPlan("none", "none", "rejected", False,
                             "target, draft, KV cache, and headroom exceed every available placement",
                             max(usable, system_usable), total, 0, requirements, observed or MemoryObservation())


def plan_memory_placement(hardware: Mapping[str, Any], requirements: MemoryRequirements,
                          *, observed: MemoryObservation | None = None) -> PlacementPlan:
    return MemoryAwarePlacementPlanner(hardware).plan(requirements, observed=observed)
