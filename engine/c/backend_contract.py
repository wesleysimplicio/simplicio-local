#!/usr/bin/env python3
"""Governed, load-free integration contract for Simplicio local inference."""

from dataclasses import dataclass, field
import hashlib
import json
import os
import platform
from pathlib import Path
import shutil
import time


PROTOCOL = "simplicio.local-inference-backend/v1"
GB = 1_000_000_000
DEEP_WORKLOADS = frozenset(("background", "batch", "deep-offline"))
STATES = frozenset((
    "cold", "loading", "warming", "ready", "degraded", "draining",
    "stopped", "blocked",
))
TRANSITIONS = {
    "cold": {"loading", "blocked", "stopped"},
    "loading": {"warming", "degraded", "draining", "blocked"},
    "warming": {"ready", "degraded", "draining", "blocked"},
    "ready": {"degraded", "draining", "blocked"},
    "degraded": {"ready", "draining", "blocked"},
    "draining": {"stopped", "blocked"},
    "stopped": {"loading"},
    "blocked": {"cold", "stopped"},
}


def _source_status(path, host_supported):
    if not Path(path).is_file():
        return "planned"
    return "implemented" if host_supported else "implemented-unverified-on-host"


def capability_probe(repo_root=None, model=None):
    """Return capabilities without starting an engine or reading model payloads."""
    root = Path(repo_root or Path(__file__).resolve().parents[2])
    machine = platform.machine().lower()
    system = platform.system().lower()
    model_path = Path(model).expanduser().resolve() if model else None
    identity = {
        "backend": "simplicio-local-any-llm-16gb",
        "protocol": PROTOCOL,
        "engine": "colibri-c-vendored",
        "build_commit": os.environ.get("SIMPLICIO_LOCAL_COMMIT"),
        "requested_model": str(model_path) if model_path else None,
        "effective_model": None,
    }
    return {
        "protocol": PROTOCOL,
        "identity": identity,
        "state": "cold",
        "read_only": True,
        "model_payload_read": False,
        "capabilities": {
            "dense": "implemented",
            "moe": "implemented",
            "cpu": "implemented",
            "neon": _source_status(root / "runtime/neon/neon_matmul.cpp",
                                   machine in ("arm64", "aarch64")),
            "metal": _source_status(root / "runtime/metal/kernels/matmul.metal",
                                    system == "darwin" and machine == "arm64"),
            "mlx": _source_status(root / "runtime/mlx/mlx_bridge.cpp",
                                  system == "darwin" and machine == "arm64"),
            "streaming_sse": "implemented",
            "expert_streaming": "implemented",
            "layer_streaming": "experimental",
            "cancellation": "implemented",
            "deterministic_seed": "implemented",
            "tool_candidates": "planned-no-execution-authority",
            "tool_execution": "forbidden",
        },
        "routing": {
            "default_workloads": sorted(DEEP_WORKLOADS),
            "interactive": "deny-unless-explicit-runtime-policy",
        },
    }


def admission_estimate(*, model_bytes, dense_bytes, available_memory,
                       available_disk, hard_rss_limit, workload,
                       runtime_bytes=int(3.7 * GB), cache_bytes=0,
                       explicit_interactive=False):
    values = (model_bytes, dense_bytes, available_memory, available_disk,
              hard_rss_limit, runtime_bytes, cache_bytes)
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0
           for value in values):
        raise ValueError("resource values must be non-negative integers")
    if workload not in DEEP_WORKLOADS and workload != "interactive":
        raise ValueError("invalid workload class")
    projected_rss = dense_bytes + runtime_bytes + cache_bytes
    reasons = []
    if workload == "interactive" and not explicit_interactive:
        reasons.append("interactive-requires-explicit-runtime-policy")
    if projected_rss > hard_rss_limit:
        reasons.append("projected-rss-exceeds-hard-limit")
    if projected_rss > available_memory:
        reasons.append("projected-rss-exceeds-available-memory")
    if model_bytes > available_disk:
        reasons.append("insufficient-model-storage")
    return {
        "protocol": PROTOCOL,
        "decision": "deny" if reasons else "admit",
        "workload": workload,
        "reasons": reasons,
        "estimate": {
            "model_bytes": model_bytes,
            "projected_peak_rss_bytes": projected_rss,
            "available_memory_bytes": available_memory,
            "hard_rss_limit_bytes": hard_rss_limit,
            "available_disk_bytes": available_disk,
            "cold_start_seconds": None,
            "tokens_per_second": None,
            "unobserved_reason": "requires a measured model/hardware run",
        },
    }


@dataclass
class Lease:
    lease_id: str
    model: str
    profile: str
    fence: int
    state: str = "cold"
    idempotency_keys: set = field(default_factory=set)

    def transition(self, target):
        if target not in STATES:
            raise ValueError("invalid lifecycle state")
        if target not in TRANSITIONS[self.state]:
            raise ValueError(f"invalid lifecycle transition: {self.state}->{target}")
        self.state = target


class LeaseRegistry:
    """Reference single-flight registry. Runtime remains the authority/owner."""

    def __init__(self):
        self._leases = {}
        self._fence = 0

    def acquire(self, lease_id, model, profile):
        if not all(isinstance(value, str) and value.strip()
                   for value in (lease_id, model, profile)):
            raise ValueError("lease_id, model and profile are required")
        key = (model, profile)
        current = self._leases.get(key)
        if current and current.state not in ("stopped", "blocked"):
            if current.lease_id == lease_id:
                return current
            raise RuntimeError("model-profile-already-leased")
        self._fence += 1
        lease = Lease(lease_id, model, profile, self._fence)
        self._leases[key] = lease
        return lease

    def release(self, lease):
        lease.state = "stopped"


def build_receipt(lease, request_id, requested_model, effective_model,
                  status, output=b"", metrics=None, failure_reason=None):
    if status not in ("completed", "cancelled", "timeout", "failed"):
        raise ValueError("invalid receipt status")
    if not request_id:
        raise ValueError("request_id is required")
    metrics = dict(metrics or {})
    allowed_metrics = {
        "peak_rss_bytes", "swap_bytes", "read_bytes", "cache_hit_ratio",
        "ttft_ms", "tokens_per_second",
    }
    metrics = {name: metrics.get(name) for name in sorted(allowed_metrics)}
    return {
        "protocol": PROTOCOL,
        "request_id": request_id,
        "lease": {"id": lease.lease_id, "fence": lease.fence},
        "requested_model": requested_model,
        "effective_model": effective_model,
        "status": status,
        "failure_reason": failure_reason,
        "output_sha256": hashlib.sha256(output).hexdigest(),
        "metrics": metrics,
        "created_unix_ms": int(time.time() * 1000),
        "effect_authority": "none",
    }


def host_resources(path="."):
    memory = 0
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemAvailable:"):
                memory = int(line.split()[1]) * 1024
                break
    except OSError:
        pass
    return memory, shutil.disk_usage(path).free


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))
