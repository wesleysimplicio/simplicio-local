"""Physical resource estimator with explicit value provenance."""

from __future__ import annotations

import os
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass(frozen=True)
class Measurement:
    value: int | float | None
    semantics: str
    unit: str
    reason: str | None = None
    source: str | None = None

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ResourceEstimate:
    weights: Measurement
    kv_cache: Measurement
    recurrent_state: Measurement
    mtp_state: Measurement
    working_buffers: Measurement
    disk_footprint: Measurement
    read_bytes: Measurement
    total_resident: Measurement

    def as_dict(self) -> dict[str, object]:
        return {key: value.as_dict() for key, value in asdict(self).items()}


def _unknown(unit: str, reason: str) -> Measurement:
    return Measurement(None, "unknown", unit, reason)


def estimate_resources(
    *,
    weight_bytes: int | None = None,
    context_tokens: int | None = None,
    layers: int | None = None,
    kv_heads: int | None = None,
    head_dim: int | None = None,
    dtype_bytes: int = 2,
    batch: int = 1,
    recurrent_state_bytes: int | None = None,
    mtp_state_bytes: int | None = None,
    working_buffer_bytes: int | None = None,
    disk_bytes: int | None = None,
    read_bytes: int | None = None,
) -> ResourceEstimate:
    """Estimate only when inputs are sufficient and label every derivation."""

    if weight_bytes is None:
        weights = _unknown("bytes", "weight size was not observed")
    else:
        weights = Measurement(weight_bytes, "observed", "bytes", source="asset.stat")
    if disk_bytes is None and weight_bytes is not None:
        disk = Measurement(weight_bytes, "derived", "bytes", "single asset footprint", "asset.stat")
    elif disk_bytes is None:
        disk = _unknown("bytes", "disk footprint was not observed")
    else:
        disk = Measurement(disk_bytes, "observed", "bytes", source="store.manifest")

    if all(value is not None for value in (context_tokens, layers, kv_heads, head_dim)):
        if min(context_tokens, layers, kv_heads, head_dim, dtype_bytes, batch) < 0:
            kv = _unknown("bytes", "KV dimensions must be non-negative")
        else:
            # K and V, every layer/head/token, with a declared element width.
            kv_value = 2 * context_tokens * layers * kv_heads * head_dim * dtype_bytes * batch
            kv = Measurement(kv_value, "estimated", "bytes", "KV formula from declared dimensions", "request/config")
    else:
        kv = _unknown("bytes", "context/layer/KV-head/head-dim metadata is incomplete")

    if recurrent_state_bytes is None:
        recurrent = _unknown("bytes", "recurrent state size is backend/model specific")
    else:
        recurrent = Measurement(recurrent_state_bytes, "estimated", "bytes", "declared recurrent state budget", "model metadata")
    if mtp_state_bytes is None:
        mtp = _unknown("bytes", "MTP state size is unavailable")
    else:
        mtp = Measurement(mtp_state_bytes, "estimated", "bytes", "declared MTP state budget", "model metadata")
    if working_buffer_bytes is None:
        buffers = _unknown("bytes", "working-buffer allocation was not observed")
    else:
        buffers = Measurement(working_buffer_bytes, "estimated", "bytes", "declared bounded buffer budget", "backend profile")
    if read_bytes is None:
        reads = _unknown("bytes", "I/O counters were not observed")
    else:
        reads = Measurement(read_bytes, "observed", "bytes", source="process I/O counter")

    terms = (weights.value, kv.value, recurrent.value, mtp.value, buffers.value)
    if all(value is not None for value in terms):
        resident = Measurement(sum(terms), "derived", "bytes", "sum of resident components")
    else:
        resident = _unknown("bytes", "one or more resident components are unknown")
    return ResourceEstimate(weights, kv, recurrent, mtp, buffers, disk, reads, resident)


def estimate_asset(path: str | os.PathLike[str], **metadata: int) -> ResourceEstimate:
    asset = Path(path)
    if not asset.is_file():
        raise FileNotFoundError(str(asset))
    return estimate_resources(weight_bytes=asset.stat().st_size, disk_bytes=asset.stat().st_size, **metadata)


def compare_observed(estimate: Measurement, observed: int | None) -> Measurement:
    if observed is None:
        return _unknown(estimate.unit, "observed value is unavailable")
    if estimate.value is None:
        return Measurement(None, "unknown", estimate.unit, "estimate is unknown; delta is not meaningful")
    return Measurement(observed - estimate.value, "derived", estimate.unit, "observed minus estimate")
