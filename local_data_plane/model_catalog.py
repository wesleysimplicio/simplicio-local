"""Trusted model catalog, deterministic source ranking, and verification."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.parse import urlparse


CATALOG_SCHEMA_V1 = "simplicio-local.model-catalog/v1"
_SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")


@dataclass(frozen=True)
class CatalogSource:
    name: str
    trust_rank: int
    base_url: str

    def validate(self) -> None:
        if not self.name.strip() or self.trust_rank < 0 or not self.base_url.startswith("https://"):
            raise ValueError("catalog source must have a name, non-negative trust rank, and HTTPS base_url")


@dataclass(frozen=True)
class CatalogArtifact:
    artifact_id: str
    source: str
    url: str
    size_bytes: int
    sha256: str
    platforms: tuple[str, ...] = ()
    backends: tuple[str, ...] = ()

    def validate(self) -> None:
        if not self.artifact_id.strip() or not self.source.strip() or not self.url.startswith("https://"):
            raise ValueError("artifact identity and HTTPS source are required")
        if self.size_bytes <= 0 or not _SHA256.fullmatch(self.sha256):
            raise ValueError("artifact size and SHA-256 are required")


@dataclass(frozen=True)
class CatalogEntry:
    model_id: str
    family: str
    version: str
    parameter_billions: float
    aliases: tuple[str, ...]
    quantizations: tuple[str, ...]
    artifacts: tuple[CatalogArtifact, ...]

    def validate(self) -> None:
        if not self.model_id.strip() or not self.family.strip() or not self.version.strip():
            raise ValueError("model_id, family, and version are required")
        if self.version.casefold() == "latest" or self.parameter_billions <= 0:
            raise ValueError("catalog entries require an immutable version and positive parameter count")
        if not self.quantizations or not self.artifacts:
            raise ValueError("catalog entry requires quantizations and artifacts")
        for artifact in self.artifacts:
            artifact.validate()


@dataclass(frozen=True)
class ArtifactVerificationReceipt:
    schema: str
    artifact_id: str
    accepted: bool
    reason: str
    observed_size_bytes: int | None
    observed_sha256: str | None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _artifact(payload: Mapping[str, Any]) -> CatalogArtifact:
    return CatalogArtifact(
        artifact_id=str(payload.get("artifact_id", "")), source=str(payload.get("source", "")),
        url=str(payload.get("url", "")), size_bytes=int(payload.get("size_bytes", 0)),
        sha256=str(payload.get("sha256", "")),
        platforms=tuple(str(item) for item in payload.get("platforms", ())),
        backends=tuple(str(item) for item in payload.get("backends", ())),
    )


def _entry(payload: Mapping[str, Any]) -> CatalogEntry:
    value = CatalogEntry(
        model_id=str(payload.get("model_id", "")), family=str(payload.get("family", "")),
        version=str(payload.get("version", "")), parameter_billions=float(payload.get("parameter_billions", 0)),
        aliases=tuple(str(item) for item in payload.get("aliases", ())),
        quantizations=tuple(str(item) for item in payload.get("quantizations", ())),
        artifacts=tuple(_artifact(item) for item in payload.get("artifacts", ())),
    )
    value.validate()
    return value


class TrustedModelCatalog:
    def __init__(self, sources: Iterable[CatalogSource], entries: Iterable[CatalogEntry], *, revision: str):
        self.sources = tuple(sources)
        self.entries = tuple(entries)
        self.revision = revision
        if not revision.strip() or revision.casefold() == "latest":
            raise ValueError("catalog revision must be immutable")
        for source in self.sources:
            source.validate()
        self._source_rank = {source.name: source.trust_rank for source in self.sources}
        if len(self._source_rank) != len(self.sources):
            raise ValueError("catalog source names must be unique")
        for entry in self.entries:
            entry.validate()
            for artifact in entry.artifacts:
                if artifact.source not in self._source_rank:
                    raise ValueError(f"artifact references unknown source: {artifact.source}")

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "TrustedModelCatalog":
        if payload.get("schema") != CATALOG_SCHEMA_V1:
            raise ValueError(f"schema must be {CATALOG_SCHEMA_V1}")
        return cls(tuple(CatalogSource(str(item["name"]), int(item["trust_rank"]), str(item["base_url"]))
                         for item in payload.get("sources", ())),
                   tuple(_entry(item) for item in payload.get("entries", ())),
                   revision=str(payload.get("revision", "")))

    def as_dict(self) -> dict[str, Any]:
        return {"schema": CATALOG_SCHEMA_V1, "revision": self.revision,
                "sources": [asdict(source) for source in self.sources],
                "entries": [asdict(entry) for entry in self.entries]}

    def find(self, model_id: str, *, family: str | None = None,
             parameter_billions: float | None = None) -> CatalogEntry:
        matches = tuple(entry for entry in self.entries if entry.model_id == model_id)
        if len(matches) != 1:
            raise KeyError(f"unknown canonical model id: {model_id}")
        entry = matches[0]
        if family is not None and entry.family != family:
            raise ValueError("requested family does not match canonical model")
        if parameter_billions is not None and entry.parameter_billions != parameter_billions:
            raise ValueError("requested parameter count does not match canonical model")
        return entry

    def rank_artifacts(self, model_id: str, *, platform: str | None = None,
                       backend: str | None = None) -> tuple[CatalogArtifact, ...]:
        entry = self.find(model_id)
        candidates = [artifact for artifact in entry.artifacts
                      if (not platform or not artifact.platforms or platform in artifact.platforms)
                      and (not backend or not artifact.backends or backend in artifact.backends)]
        return tuple(sorted(candidates, key=lambda artifact: (-self._source_rank[artifact.source], artifact.source,
                                                                artifact.artifact_id, artifact.url)))

    def refresh(self, payload: Mapping[str, Any]) -> "TrustedModelCatalog":
        return TrustedModelCatalog.from_payload(payload)


def verify_artifact(path: str | os.PathLike[str], artifact: CatalogArtifact) -> ArtifactVerificationReceipt:
    candidate = Path(path)
    if not candidate.is_file():
        return ArtifactVerificationReceipt(CATALOG_SCHEMA_V1, artifact.artifact_id, False, "artifact-missing", None, None)
    digest = hashlib.sha256()
    size = 0
    with candidate.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
            size += len(chunk)
    observed = digest.hexdigest()
    if size != artifact.size_bytes:
        return ArtifactVerificationReceipt(CATALOG_SCHEMA_V1, artifact.artifact_id, False,
                                            "artifact-size-mismatch", size, observed)
    if observed.casefold() != artifact.sha256.casefold():
        return ArtifactVerificationReceipt(CATALOG_SCHEMA_V1, artifact.artifact_id, False,
                                            "artifact-sha256-mismatch", size, observed)
    return ArtifactVerificationReceipt(CATALOG_SCHEMA_V1, artifact.artifact_id, True,
                                       "artifact-verified", size, observed)


def write_provenance(path: str | os.PathLike[str], *, catalog: TrustedModelCatalog,
                     entry: CatalogEntry, artifact: CatalogArtifact,
                     verification: ArtifactVerificationReceipt) -> None:
    if not verification.accepted:
        raise ValueError("cannot persist provenance for an unverified artifact")
    payload = {"schema": "simplicio-local.model-provenance/v1", "catalog_revision": catalog.revision,
               "model_id": entry.model_id, "family": entry.family,
               "parameter_billions": entry.parameter_billions, "artifact": asdict(artifact),
               "verification": verification.as_dict()}
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{destination.name}.", dir=destination.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, indent=2, sort_keys=True)
            stream.write("\n")
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
