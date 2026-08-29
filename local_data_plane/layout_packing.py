"""Versioned tensor layouts, atomic packed artifacts and safe tiling plans."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal, Mapping, Sequence


LAYOUT_PACKING_SCHEMA_V1 = "simplicio-local.layout-packing/v1"
PACKED_LAYOUT_VERSION_V1 = "int8-column-major/v1"
TILING_POLICY_VERSION_V1 = "cache-tiling/v1"
PROMOTION_SPEEDUP = 0.02
MAX_P95_REGRESSION = 0.10


def _require_text(value: str, name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")


@dataclass(frozen=True)
class PackedLayoutKey:
    """All inputs that can make a packed tensor incompatible."""

    model_id: str
    tensor_id: str
    source_digest: str
    isa: str
    kernel_version: str
    layout_version: str = PACKED_LAYOUT_VERSION_V1

    def __post_init__(self) -> None:
        for name in ("model_id", "tensor_id", "source_digest", "isa", "kernel_version", "layout_version"):
            _require_text(getattr(self, name), name)

    def as_dict(self) -> dict[str, str]:
        return asdict(self)

    def canonical(self) -> str:
        return json.dumps(self.as_dict(), sort_keys=True, separators=(",", ":"))

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(self.canonical().encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class PackedLayoutArtifact:
    key: PackedLayoutKey
    rows: int
    columns: int
    values: bytes
    source_digest: str
    packed_digest: str
    schema: str = LAYOUT_PACKING_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != LAYOUT_PACKING_SCHEMA_V1:
            raise ValueError("unsupported packed layout schema")
        if isinstance(self.rows, bool) or isinstance(self.columns, bool) or self.rows <= 0 or self.columns <= 0:
            raise ValueError("packed layout dimensions must be positive")
        if len(self.values) != self.rows * self.columns:
            raise ValueError("packed layout payload has the wrong size")
        if self.source_digest != self.key.source_digest:
            raise ValueError("source digest does not match the cache key")

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "key": self.key.as_dict(),
            "rows": self.rows,
            "columns": self.columns,
            "values_b64": base64.b64encode(self.values).decode("ascii"),
            "source_digest": self.source_digest,
            "packed_digest": self.packed_digest,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "PackedLayoutArtifact":
        if value.get("schema") != LAYOUT_PACKING_SCHEMA_V1:
            raise ValueError("unsupported packed layout schema")
        key_data = value.get("key")
        if not isinstance(key_data, Mapping):
            raise ValueError("packed layout key is missing")
        key = PackedLayoutKey(**{name: key_data[name] for name in (
            "model_id", "tensor_id", "source_digest", "isa", "kernel_version", "layout_version")})
        encoded = value.get("values_b64")
        if not isinstance(encoded, str):
            raise ValueError("packed layout payload is missing")
        try:
            payload = base64.b64decode(encoded.encode("ascii"), validate=True)
        except (ValueError, UnicodeEncodeError) as exc:
            raise ValueError("packed layout payload is not valid base64") from exc
        return cls(key, int(value["rows"]), int(value["columns"]), payload,
                   str(value["source_digest"]), str(value["packed_digest"]))


def digest_int8(source: bytes | bytearray | Sequence[int]) -> str:
    """Return the digest of the signed int8 byte representation."""
    payload = _signed_payload(source)
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _signed_payload(source: bytes | bytearray | Sequence[int]) -> bytes:
    if isinstance(source, (bytes, bytearray)):
        return bytes(source)
    values: list[int] = []
    for value in source:
        if isinstance(value, bool) or not isinstance(value, int) or not -128 <= value <= 127:
            raise ValueError("int8 source values must be integers in [-128, 127]")
        values.append(value & 0xFF)
    return bytes(values)


def pack_int8_rhs(source: bytes | bytearray | Sequence[int], rows: int, columns: int,
                  key: PackedLayoutKey) -> PackedLayoutArtifact:
    """Pack row-major [rows][columns] data into column-major [columns][rows]."""
    if isinstance(rows, bool) or isinstance(columns, bool) or rows <= 0 or columns <= 0:
        raise ValueError("packing dimensions must be positive")
    raw = _signed_payload(source)
    if len(raw) != rows * columns:
        raise ValueError("source size does not match packing dimensions")
    source_digest = "sha256:" + hashlib.sha256(raw).hexdigest()
    if source_digest != key.source_digest:
        raise ValueError("source digest does not match the requested layout key")
    packed = bytes(raw[row * columns + column] for column in range(columns) for row in range(rows))
    return PackedLayoutArtifact(key, rows, columns, packed, source_digest,
                                "sha256:" + hashlib.sha256(packed).hexdigest())


def validate_packed_layout(artifact: PackedLayoutArtifact, key: PackedLayoutKey,
                           rows: int, columns: int) -> bool:
    """Validate identity, dimensions and both source/payload digests."""
    return (artifact.schema == LAYOUT_PACKING_SCHEMA_V1 and artifact.key == key
            and artifact.rows == rows and artifact.columns == columns
            and artifact.source_digest == key.source_digest
            and artifact.packed_digest == "sha256:" + hashlib.sha256(artifact.values).hexdigest())


class AtomicPackedCache:
    """A corruption-tolerant cache with atomic replacement and key invalidation."""

    def __init__(self, directory: str | os.PathLike[str]):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def _path(self, key: PackedLayoutKey) -> Path:
        return self.directory / (key.fingerprint + ".json")

    def store(self, artifact: PackedLayoutArtifact) -> Path:
        if not validate_packed_layout(artifact, artifact.key, artifact.rows, artifact.columns):
            raise ValueError("refusing to persist an invalid packed artifact")
        destination = self._path(artifact.key)
        handle, temporary_name = tempfile.mkstemp(prefix=destination.name + ".", suffix=".tmp",
                                                   dir=self.directory)
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                json.dump(artifact.as_dict(), stream, sort_keys=True, separators=(",", ":"))
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_name, destination)
        except BaseException:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
            raise
        return destination

    def load(self, key: PackedLayoutKey, rows: int, columns: int) -> PackedLayoutArtifact | None:
        try:
            value = json.loads(self._path(key).read_text(encoding="utf-8"))
            artifact = PackedLayoutArtifact.from_dict(value)
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
            return None
        return artifact if validate_packed_layout(artifact, key, rows, columns) else None

    def invalidate(self, key: PackedLayoutKey) -> bool:
        try:
            self._path(key).unlink()
        except FileNotFoundError:
            return False
        return True


@dataclass(frozen=True)
class TilingPlan:
    mode: Literal["decode", "prefill", "batch"]
    tile_rows: int
    tile_cols: int
    scratch_bytes: int
    enabled: bool
    reason: str
    schema: str = TILING_POLICY_VERSION_V1

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def select_tiling(rows: int, inner: int, columns: int, *, mode: Literal["decode", "prefill", "batch"] = "decode",
                  cache_budget_bytes: int = 32 * 1024, measured_speedup: float | None = None,
                  p95_regression: float = 0.0) -> TilingPlan:
    """Choose bounded tiles; promotion is disabled without non-regressive evidence."""
    if mode not in ("decode", "prefill", "batch"):
        raise ValueError("mode must be decode, prefill or batch")
    if any(isinstance(value, bool) or not isinstance(value, int) or value <= 0
           for value in (rows, inner, columns, cache_budget_bytes)):
        raise ValueError("tiling dimensions and budget must be positive integers")
    row_hint = {"decode": 1, "prefill": 32, "batch": 8}[mode]
    col_hint = {"decode": 128, "prefill": 128, "batch": 64}[mode]
    tile_rows = min(rows, row_hint)
    tile_cols = min(columns, col_hint)
    while tile_rows * inner + inner * tile_cols > cache_budget_bytes and (tile_rows > 1 or tile_cols > 1):
        if tile_cols >= tile_rows and tile_cols > 1:
            tile_cols = max(1, tile_cols // 2)
        else:
            tile_rows = max(1, tile_rows // 2)
    scratch = (tile_rows * inner) + (inner * tile_cols)
    evidence_ok = measured_speedup is not None and measured_speedup > PROMOTION_SPEEDUP
    regression_ok = 0.0 <= p95_regression <= MAX_P95_REGRESSION
    enabled = evidence_ok and regression_ok and scratch <= cache_budget_bytes
    if enabled:
        reason = "tiling-enabled-by-bounded-non-regressive-evidence"
    elif not regression_ok:
        reason = "p95-regression-auto-disabled"
    elif measured_speedup is None:
        reason = "no-measurement-auto-disabled"
    elif not evidence_ok:
        reason = "measurement-below-promotion-threshold"
    else:
        reason = "cache-budget-exceeded-auto-disabled"
    return TilingPlan(mode, tile_rows, tile_cols, scratch, enabled, reason)


@dataclass(frozen=True)
class BatchRequest:
    session_id: str
    model_id: str
    kv_bytes: int = 0
    priority: int = 0


@dataclass(frozen=True)
class BatchPlan:
    session_ids: tuple[str, ...]
    model_id: str | None
    isolated_kv: bool
    fair: bool
    enabled: bool
    reason: str


def form_isolated_batch(requests: Sequence[BatchRequest], *, max_batch_size: int = 8,
                        throughput_gain: float | None = None, p95_regression: float = 0.0) -> BatchPlan:
    """Batch only one model while retaining each session's identity and KV ownership."""
    if isinstance(max_batch_size, bool) or not isinstance(max_batch_size, int) or max_batch_size < 1:
        raise ValueError("max_batch_size must be positive")
    if not requests:
        return BatchPlan((), None, True, True, False, "empty-request-set")
    if len({request.session_id for request in requests}) != len(requests):
        raise ValueError("session ids must be unique within a batch")
    if any(request.kv_bytes < 0 for request in requests):
        raise ValueError("KV allocation cannot be negative")
    model_ids = {request.model_id for request in requests}
    if len(model_ids) != 1:
        return BatchPlan((requests[0].session_id,), requests[0].model_id, True, True, False,
                         "cross-model-batch-would-break-isolation")
    ordered = sorted(requests, key=lambda request: (-request.priority, request.session_id))
    evidence_ok = throughput_gain is not None and throughput_gain > PROMOTION_SPEEDUP
    regression_ok = 0.0 <= p95_regression <= MAX_P95_REGRESSION
    if not evidence_ok or not regression_ok:
        return BatchPlan((ordered[0].session_id,), ordered[0].model_id, True, True, False,
                         "batch-disabled-without-non-regressive-evidence")
    selected = tuple(request.session_id for request in ordered[:max_batch_size])
    return BatchPlan(selected, ordered[0].model_id, True, True, len(selected) > 1,
                     "batch-enabled-by-bounded-non-regressive-evidence")
