"""Hardware-aware automatic backend and runtime configuration planning."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .memory_placement import MemoryObservation, MemoryRequirements, PlacementPlan, plan_memory_placement


EXECUTION_PLAN_SCHEMA_V1 = "simplicio-local.execution-plan/v1"


@dataclass(frozen=True)
class HardwareProfile:
    platform: str
    architecture: str
    system_memory_bytes: int
    available_system_bytes: int
    gpu_memory_bytes: int = 0
    available_gpu_bytes: int = 0
    unified_memory_bytes: int = 0
    available_unified_bytes: int = 0
    has_cuda: bool = False
    has_metal: bool = False
    separate_draft_device_supported: bool = False
    cpu_threads: int = 1

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class ModelFootprint:
    target_bytes: int
    draft_bytes: int = 0
    kv_bytes_per_token: int = 0
    working_bytes: int = 0


@dataclass(frozen=True)
class ExecutionPlan:
    backend: str
    context_tokens: int
    gpu_offload: str
    kv_cache_policy: str
    threads: int
    batch_size: int
    fast_strategy: str
    accepted: bool
    explanation: str
    placement: PlacementPlan

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": EXECUTION_PLAN_SCHEMA_V1,
            "backend": self.backend,
            "context_tokens": self.context_tokens,
            "gpu_offload": self.gpu_offload,
            "kv_cache_policy": self.kv_cache_policy,
            "threads": self.threads,
            "batch_size": self.batch_size,
            "fast_strategy": self.fast_strategy,
            "accepted": self.accepted,
            "explanation": self.explanation,
            "placement": self.placement.as_dict(),
        }


def _positive(value: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


class AutomaticRuntimePlanner:
    def __init__(self, *, minimum_context_tokens: int = 512):
        if minimum_context_tokens < 1:
            raise ValueError("minimum_context_tokens must be positive")
        self.minimum_context_tokens = minimum_context_tokens

    @staticmethod
    def _backend(profile: HardwareProfile, requested: str | None) -> str:
        if requested:
            if requested == "cuda" and not profile.has_cuda:
                raise ValueError("requested CUDA backend is unavailable")
            if requested == "metal" and not profile.has_metal:
                raise ValueError("requested Metal backend is unavailable")
            if requested not in {"cuda", "metal", "cpu", "unified"}:
                raise ValueError("unsupported backend override")
            return requested
        if profile.has_cuda and profile.available_gpu_bytes:
            return "cuda"
        if profile.has_metal and (profile.available_unified_bytes or profile.unified_memory_bytes):
            return "unified" if profile.platform == "darwin" else "metal"
        return "cpu"

    @staticmethod
    def _hardware_map(profile: HardwareProfile, backend: str) -> Mapping[str, Any]:
        return {
            "backend": backend,
            "available_system_bytes": profile.available_system_bytes,
            "system_memory_bytes": profile.system_memory_bytes,
            "available_gpu_bytes": profile.available_gpu_bytes,
            "gpu_memory_bytes": profile.gpu_memory_bytes,
            "available_unified_bytes": profile.available_unified_bytes,
            "unified_memory_bytes": profile.unified_memory_bytes,
            "separate_draft_device_supported": profile.separate_draft_device_supported,
        }

    def plan(self, profile: HardwareProfile, footprint: ModelFootprint, *, requested_context: int = 4096,
             requested_backend: str | None = None, fast_strategy: str = "baseline",
             dry_run: bool = False) -> ExecutionPlan:
        requested_context = _positive(requested_context, "requested_context")
        if requested_context == 0 or footprint.kv_bytes_per_token < 0:
            raise ValueError("requested_context must be positive and KV cost cannot be negative")
        backend = self._backend(profile, requested_backend)
        available = profile.available_system_bytes or profile.system_memory_bytes
        if backend in {"cuda", "metal"}:
            available = profile.available_gpu_bytes
        elif backend == "unified":
            available = profile.available_unified_bytes or profile.available_system_bytes
        reserve = max(512 * 1024 * 1024, int(available * 0.15))
        room = max(0, available - reserve - footprint.target_bytes - footprint.draft_bytes - footprint.working_bytes)
        context = requested_context if footprint.kv_bytes_per_token == 0 else min(
            requested_context, room // footprint.kv_bytes_per_token)
        if context < self.minimum_context_tokens:
            context = 0
        requirements = MemoryRequirements(
            target_bytes=footprint.target_bytes,
            draft_bytes=footprint.draft_bytes,
            kv_cache_bytes=context * footprint.kv_bytes_per_token,
            working_bytes=footprint.working_bytes,
        )
        placement = plan_memory_placement(self._hardware_map(profile, backend), requirements)
        accepted = placement.accepted and context >= self.minimum_context_tokens
        gpu_offload = "full" if placement.mode == "full-device" else ("hybrid" if placement.accepted else "none")
        kv_policy = "device" if placement.target_device in {"cuda", "metal", "unified"} else "cpu"
        threads = max(1, min(profile.cpu_threads, 32))
        batch = 512 if context >= 2048 else 128
        reason = placement.reason if accepted else "requested model and context exceed reserved memory"
        explanation = (f"backend={backend}; context={context or 'rejected'}; {reason}; "
                       f"Fast strategy={fast_strategy}; dry_run={str(dry_run).lower()}")
        return ExecutionPlan(backend, context, gpu_offload, kv_policy, threads, batch, fast_strategy,
                             accepted, explanation, placement)
