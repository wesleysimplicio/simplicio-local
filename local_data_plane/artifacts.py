"""Fail-closed provenance checks for physical inference artifacts."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path


ARTIFACT_PIN_SCHEMA_V1 = "simplicio.inference-artifact-pin/v1"
_HEX64 = re.compile(r"^(?:sha256:)?[0-9a-fA-F]{64}$")


@dataclass(frozen=True)
class InferenceArtifactPin:
    schema: str
    artifact_id: str
    artifact_kind: str
    version: str
    sha256: str
    source_url: str
    upstream_commit: str
    license: str

    def validate(self) -> None:
        if self.schema != ARTIFACT_PIN_SCHEMA_V1:
            raise ValueError(f"unsupported artifact pin schema: {self.schema}")
        required = {
            "artifact_id": self.artifact_id,
            "artifact_kind": self.artifact_kind,
            "version": self.version,
            "source_url": self.source_url,
            "upstream_commit": self.upstream_commit,
            "license": self.license,
        }
        for label, value in required.items():
            if not value.strip():
                raise ValueError(f"{label} is required")
        if not _HEX64.fullmatch(self.sha256):
            raise ValueError("sha256 must contain exactly 64 hexadecimal characters")
        if self.version.casefold() == "latest" or "/" in self.version or " " in self.version:
            raise ValueError("version must be an immutable pin, not a mutable reference")
        if not self.source_url.startswith("https://"):
            raise ValueError("source_url must use https")

    @property
    def digest(self) -> str:
        return self.sha256.removeprefix("sha256:").lower()


@dataclass(frozen=True)
class ArtifactValidationReceipt:
    schema: str
    artifact_id: str
    accepted: bool
    reason: str
    sha256: str | None

    def as_dict(self) -> dict[str, object]:
        return self.__dict__.copy()


def validate_artifact(pin: InferenceArtifactPin) -> ArtifactValidationReceipt:
    try:
        pin.validate()
    except ValueError as exc:
        return ArtifactValidationReceipt(ARTIFACT_PIN_SCHEMA_V1, pin.artifact_id, False, str(exc), None)
    return ArtifactValidationReceipt(ARTIFACT_PIN_SCHEMA_V1, pin.artifact_id, True,
                                     "pinned-artifact-validated", pin.digest)


def pin_from_payload(payload: object) -> InferenceArtifactPin:
    if not isinstance(payload, dict):
        raise ValueError("artifact_pin must be an object")
    fields = ("schema", "artifact_id", "artifact_kind", "version", "sha256",
              "source_url", "upstream_commit", "license")
    values = {field: payload.get(field) for field in fields}
    if not all(isinstance(value, str) for value in values.values()):
        raise ValueError("artifact_pin contains missing or non-string fields")
    return InferenceArtifactPin(**values)


def digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
