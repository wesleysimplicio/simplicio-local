"""Experimental tensor-network KV compression adapter for the KV policy."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, asdict
from typing import Any


KV_COMPRESSION_SCHEMA_V1 = "simplicio-local.qphys-kv-compression/v1"


@dataclass(frozen=True)
class KVCompressionObservation:
    quality_delta: float
    ttft_delta: float
    generation_delta: float
    compression_ratio: float
    scratch_bytes: int
    measured: bool


@dataclass(frozen=True)
class KVCompressionPlan:
    recent_policy: str
    cold_policy: str
    identity_key: str
    accepted: bool
    reason: str
    observation: KVCompressionObservation

    def as_dict(self) -> dict[str, Any]:
        return {"schema": KV_COMPRESSION_SCHEMA_V1, **asdict(self)}


def identity_key(*, model_id: str, tokenizer_hash: str, template_hash: str, session_id: str, prefix_hash: str) -> str:
    payload = {"model": model_id, "tokenizer": tokenizer_hash, "template": template_hash,
               "session": session_id, "prefix": prefix_hash}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def select_kv_compression(*, identity: dict[str, str], observation: KVCompressionObservation,
                          quality_tolerance: float = 0.01, ttft_tolerance: float = 0.10,
                          generation_tolerance: float = 0.10, minimum_ratio: float = 1.2) -> KVCompressionPlan:
    if not observation.measured:
        accepted = False
        reason = "unmeasured KV compression remains experimental/off"
    else:
        accepted = (observation.quality_delta >= -quality_tolerance and
                    observation.ttft_delta <= ttft_tolerance and
                    observation.generation_delta >= -generation_tolerance and
                    observation.compression_ratio >= minimum_ratio and observation.scratch_bytes >= 0)
        reason = "cold KV factorization passed quality/latency/compression gates" if accepted else "KV compression regressed or lacks ratio evidence"
    key = identity_key(**identity)
    return KVCompressionPlan("reference_recent_window", "factorized_quantized_cold" if accepted else "reference_cold",
                             key, accepted, reason, observation)
