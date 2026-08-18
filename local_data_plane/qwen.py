"""Evidence boundary for Qwen hybrid state and recurrent/MTP separation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from .registry import EvidenceLevel


@dataclass(frozen=True)
class QwenHybridState:
    model_id: str
    weights_ref: str
    attention_kv_ref: str
    recurrent_state_ref: str
    mtp_state_ref: str

    def validate(self) -> None:
        refs = (self.weights_ref, self.attention_kv_ref, self.recurrent_state_ref, self.mtp_state_ref)
        if not self.model_id or any(not ref for ref in refs):
            raise ValueError("Qwen hybrid state requires all four component references")
        if len(set(refs)) != len(refs):
            raise ValueError("Qwen hybrid state components must not alias one another")

    def as_dict(self) -> dict[str, str]:
        self.validate()
        return self.__dict__.copy()


@dataclass(frozen=True)
class QwenProbe:
    architecture: str | None
    recurrent_layers: int | None
    mtp_depth: int | None
    hybrid: bool
    reason: str


def probe_metadata(metadata: Mapping[str, object]) -> QwenProbe:
    architecture = metadata.get("architecture")
    recurrent_layers = metadata.get("recurrent_layers")
    mtp_depth = metadata.get("mtp_depth")
    if not isinstance(architecture, str):
        return QwenProbe(None, None, None, False, "architecture metadata is missing")
    if not isinstance(recurrent_layers, int) or not isinstance(mtp_depth, int):
        return QwenProbe(architecture, None, None, False, "recurrent_layers and mtp_depth metadata are required")
    return QwenProbe(architecture, recurrent_layers, mtp_depth,
                     recurrent_layers > 0 or mtp_depth > 0, "architecture metadata is explicit")


@dataclass(frozen=True)
class QwenPromotion:
    promoted: bool
    evidence_level: EvidenceLevel
    requested_model: str
    effective_model: str | None
    reason: str
    state: QwenHybridState | None = None


def promote_hybrid(*, requested_model: str, metadata: Mapping[str, object], state: QwenHybridState,
                   reference: Sequence[str], candidate: Sequence[str], evidence: EvidenceLevel) -> QwenPromotion:
    probe = probe_metadata(metadata)
    try:
        state.validate()
    except ValueError as exc:
        return QwenPromotion(False, evidence, requested_model, None, str(exc))
    if not probe.hybrid:
        return QwenPromotion(False, evidence, requested_model, None, probe.reason)
    if list(reference) != list(candidate):
        return QwenPromotion(False, evidence, requested_model, None, "hybrid output parity failed")
    if evidence < EvidenceLevel.FIXTURE_EXECUTED:
        return QwenPromotion(False, evidence, requested_model, None, "observed execution evidence is required")
    return QwenPromotion(True, evidence, requested_model, requested_model,
                         "explicit architecture and output parity passed", state)
