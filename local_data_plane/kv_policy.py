"""KV-cache budgeting, tiering, quantization and deterministic reuse policy."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, asdict
from typing import Any


KV_POLICY_SCHEMA_V1 = "simplicio-local.kv-policy/v1"


@dataclass(frozen=True)
class KVFormat:
    name: str
    bytes_per_token: int
    device: str
    quantized: bool = False


@dataclass(frozen=True)
class KVRequest:
    requested_context: int
    minimum_context: int
    full_precision_bytes_per_token: int
    available_bytes: int
    reserved_bytes: int
    device: str
    quantized_bytes_per_token: int | None = None
    quantization_supported: bool = False
    paged_supported: bool = False
    requested_policy: str = "auto"


@dataclass(frozen=True)
class KVPlan:
    format: KVFormat
    max_context: int
    total_bytes: int
    headroom_bytes: int
    accepted: bool
    tier: str
    eviction: str
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {"schema": KV_POLICY_SCHEMA_V1, **asdict(self), "format": asdict(self.format)}


@dataclass(frozen=True)
class PrefixIdentity:
    model_id: str
    tokenizer_hash: str
    chat_template_hash: str
    generation_identity: str

    @property
    def key(self) -> str:
        payload = json.dumps(asdict(self), sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(payload).hexdigest()


class KVCachePlanner:
    def plan(self, request: KVRequest) -> KVPlan:
        values = (request.requested_context, request.minimum_context, request.full_precision_bytes_per_token,
                  request.available_bytes, request.reserved_bytes)
        if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in values):
            raise ValueError("KV dimensions must be non-negative integers")
        if request.minimum_context < 1 or request.requested_context < request.minimum_context:
            raise ValueError("requested_context must be at least minimum_context")
        usable = max(0, request.available_bytes - request.reserved_bytes)
        full = KVFormat("full_precision", request.full_precision_bytes_per_token, request.device)
        candidates = [full]
        if request.quantization_supported and request.quantized_bytes_per_token:
            candidates.append(KVFormat("quantized", request.quantized_bytes_per_token, request.device, True))
        selected = candidates[0]
        if request.requested_policy == "quantized" and len(candidates) > 1:
            selected = candidates[1]
        elif request.requested_policy == "paged" and request.paged_supported:
            selected = KVFormat("paged", request.full_precision_bytes_per_token, request.device)
        elif request.requested_policy not in {"auto", "full_precision", "quantized", "paged"}:
            raise ValueError("unsupported KV policy")
        context = min(request.requested_context, usable // max(1, selected.bytes_per_token))
        if context < request.minimum_context and selected.name == "full_precision" and len(candidates) > 1:
            selected = candidates[1]
            context = min(request.requested_context, usable // max(1, selected.bytes_per_token))
        accepted = context >= request.minimum_context
        total = context * selected.bytes_per_token
        tier = "hot-device" if accepted else "unavailable"
        eviction = "deterministic-oldest-session" if accepted else "none"
        reason = ("KV fits reserved budget" if accepted else "KV minimum context exceeds reserved budget")
        if selected.quantized:
            reason += "; quantized format selected with explicit backend support"
        return KVPlan(selected, context if accepted else 0, total if accepted else 0,
                      max(0, usable - total) if accepted else 0, accepted, tier, eviction, reason)

    @staticmethod
    def fair_share(available_bytes: int, sessions: int) -> tuple[int, ...]:
        if available_bytes < 0 or sessions < 1:
            raise ValueError("available_bytes must be non-negative and sessions positive")
        base, remainder = divmod(available_bytes, sessions)
        return tuple(base + (1 if index < remainder else 0) for index in range(sessions))

    @staticmethod
    def can_reuse_prefix(existing: PrefixIdentity, requested: PrefixIdentity) -> bool:
        return existing.key == requested.key
