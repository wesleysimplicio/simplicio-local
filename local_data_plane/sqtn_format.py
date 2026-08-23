"""Versioned mmap-safe SQTN (Simplicio Quantized Tensor Network) manifest."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Mapping


SQTN_SCHEMA_V1 = "simplicio-local.sqtn/v1"


@dataclass(frozen=True)
class SQTNTensor:
    name: str
    representation: str
    dimensions: tuple[int, ...]
    ranks: tuple[int, ...]
    quant_scheme: str
    offset: int
    length: int
    alignment: int
    sha256: str


@dataclass(frozen=True)
class SQTNManifest:
    schema: str
    model_id: str
    tokenizer_hash: str
    template_hash: str
    source_model_digest: str
    calibration_digest: str
    policy_digest: str
    tensors: tuple[SQTNTensor, ...]
    artifact_size: int
    quality_evidence: Mapping[str, Any]

    def validate(self) -> None:
        if self.schema != SQTN_SCHEMA_V1:
            raise ValueError("unsupported SQTN schema")
        for value in (self.tokenizer_hash, self.template_hash, self.source_model_digest,
                      self.calibration_digest, self.policy_digest):
            if not value or len(value) != 64:
                raise ValueError("SQTN identities must be SHA-256 digests")
        if self.artifact_size <= 0 or not self.tensors:
            raise ValueError("SQTN artifact must contain tensors and positive size")
        occupied: list[tuple[int, int]] = []
        for tensor in self.tensors:
            if not tensor.name or not tensor.representation or any(value < 1 for value in tensor.dimensions + tensor.ranks):
                raise ValueError("invalid SQTN tensor metadata")
            if tensor.offset < 0 or tensor.length <= 0 or tensor.alignment <= 0 or tensor.offset % tensor.alignment:
                raise ValueError("SQTN tensor offset/alignment is invalid")
            if tensor.offset + tensor.length > self.artifact_size or len(tensor.sha256) != 64:
                raise ValueError("SQTN tensor bounds/checksum metadata is invalid")
            occupied.append((tensor.offset, tensor.offset + tensor.length))
        for left, right in zip(sorted(occupied), sorted(occupied)[1:]):
            if left[1] > right[0]:
                raise ValueError("SQTN tensor ranges overlap")

    def as_dict(self) -> dict[str, Any]:
        return {**asdict(self), "tensors": [asdict(tensor) for tensor in self.tensors]}


def manifest_from_payload(payload: Mapping[str, Any]) -> SQTNManifest:
    manifest = SQTNManifest(
        str(payload.get("schema", "")), str(payload.get("model_id", "")), str(payload.get("tokenizer_hash", "")),
        str(payload.get("template_hash", "")), str(payload.get("source_model_digest", "")),
        str(payload.get("calibration_digest", "")), str(payload.get("policy_digest", "")),
        tuple(SQTNTensor(str(item["name"]), str(item["representation"]), tuple(item["dimensions"]), tuple(item["ranks"]),
                         str(item["quant_scheme"]), int(item["offset"]), int(item["length"]), int(item["alignment"]), str(item["sha256"]))
              for item in payload.get("tensors", ())), int(payload.get("artifact_size", 0)), dict(payload.get("quality_evidence", {})))
    manifest.validate()
    return manifest


def verify_sqtn_artifact(path: str | Path, manifest: SQTNManifest) -> dict[str, Any]:
    manifest.validate()
    candidate = Path(path)
    if not candidate.is_file() or candidate.stat().st_size != manifest.artifact_size:
        return {"schema": SQTN_SCHEMA_V1, "verified": False, "reason": "artifact-size-mismatch"}
    with candidate.open("rb") as stream:
        for tensor in manifest.tensors:
            stream.seek(tensor.offset)
            digest = hashlib.sha256(stream.read(tensor.length)).hexdigest()
            if digest != tensor.sha256:
                return {"schema": SQTN_SCHEMA_V1, "verified": False, "reason": f"tensor-checksum:{tensor.name}"}
    return {"schema": SQTN_SCHEMA_V1, "verified": True, "resident_factor_bytes": sum(tensor.length for tensor in manifest.tensors),
            "dense_materialized": False}
