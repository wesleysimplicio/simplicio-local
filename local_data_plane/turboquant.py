"""CPU reference executor for TurboQuant-style KV-cache compression.

This module implements the data-oblivious reference path described in
arXiv:2504.19874: a reproducible orthogonal rotation, a fixed Lloyd-Max
codebook, scalar indices, bit-packing, and per-vector norm correction. It is
an actual KV codec, not a claim that llama.cpp's attention loop has been
patched. The llama.cpp integration can consume this seam once its backend
exposes KV cache blocks.

NumPy is loaded lazily so the rest of the Local daemon remains usable on
minimal installations. No GPU or Torch dependency is required for this
reference executor.
"""

from __future__ import annotations

import base64
import functools
import math
from dataclasses import dataclass
from typing import Any, Iterable


TURBOQUANT_SCHEMA = "simplicio.local.turboquant-kv/v1"
SUPPORTED_BITS = frozenset({2, 3, 4})
MAX_ELEMENTS = 1_000_000


class TurboQuantError(ValueError):
    """A fail-closed TurboQuant codec error."""


def _numpy():
    try:
        import numpy as np
    except ImportError as exc:  # pragma: no cover - depends on host packaging
        raise TurboQuantError("TurboQuant CPU executor requires numpy") from exc
    return np


def _validate_bits(bits: int) -> int:
    if bits not in SUPPORTED_BITS:
        raise TurboQuantError(f"TurboQuant bits must be one of {sorted(SUPPORTED_BITS)}")
    return bits


def _is_power_of_two(value: int) -> bool:
    return value > 0 and value & (value - 1) == 0


def _hadamard(size: int, np: Any):
    matrix = np.array([[1.0]], dtype=np.float32)
    while matrix.shape[0] < size:
        matrix = np.block([[matrix, matrix], [matrix, -matrix]])
    return matrix / math.sqrt(size)


@functools.lru_cache(maxsize=32)
def _codebook(bits: int, dimension: int) -> tuple[float, ...]:
    """Build a deterministic normal/Beta approximation without input data."""

    np = _numpy()
    _validate_bits(bits)
    if dimension <= 0:
        raise TurboQuantError("TurboQuant dimension must be positive")
    rng = np.random.default_rng(0x5451 + bits * 97 + dimension * 13)
    samples = rng.standard_normal(32768).astype(np.float32) / math.sqrt(dimension)
    levels = 1 << bits
    centroids = np.quantile(samples, np.linspace(0.01, 0.99, levels)).astype(np.float32)
    for _ in range(12):
        assignments = np.abs(samples[:, None] - centroids[None, :]).argmin(axis=1)
        updated = centroids.copy()
        for index in range(levels):
            selected = samples[assignments == index]
            if selected.size:
                updated[index] = selected.mean()
        if np.allclose(updated, centroids, rtol=0, atol=1e-7):
            break
        centroids = updated
    return tuple(float(item) for item in centroids)


def _rotation(dimension: int, seed: int, np: Any):
    rng = np.random.default_rng(seed)
    if _is_power_of_two(dimension):
        signs = rng.choice(np.array([-1.0, 1.0], dtype=np.float32), size=dimension)
        return _hadamard(dimension, np), signs, "hadamard"
    raw = rng.standard_normal((dimension, dimension)).astype(np.float32)
    matrix, diagonal = np.linalg.qr(raw)
    signs = np.where(np.diag(diagonal) < 0, -1.0, 1.0).astype(np.float32)
    return matrix.astype(np.float32), signs, "qr"


def _pack(indices: Any, bits: int) -> bytes:
    mask = (1 << bits) - 1
    accumulator = 0
    available = 0
    output = bytearray()
    for value in indices.reshape(-1).tolist():
        accumulator |= (int(value) & mask) << available
        available += bits
        while available >= 8:
            output.append(accumulator & 0xFF)
            accumulator >>= 8
            available -= 8
    if available:
        output.append(accumulator & 0xFF)
    return bytes(output)


def _unpack(data: bytes, count: int, bits: int, np: Any):
    mask = (1 << bits) - 1
    values = np.empty(count, dtype=np.uint8)
    accumulator = 0
    available = 0
    offset = 0
    for byte in data:
        accumulator |= byte << available
        available += 8
        while available >= bits and offset < count:
            values[offset] = accumulator & mask
            accumulator >>= bits
            available -= bits
            offset += 1
    if offset != count:
        raise TurboQuantError("packed TurboQuant indices are truncated")
    return values


@dataclass(frozen=True)
class TurboQuantPacket:
    shape: tuple[int, int]
    bits: int
    seed: int
    rotation_mode: str
    packed_indices: bytes
    norms: tuple[float, ...]
    centroids: tuple[float, ...]
    signs: tuple[float, ...]

    @property
    def element_count(self) -> int:
        return self.shape[0] * self.shape[1]

    @property
    def packed_bytes(self) -> int:
        return len(self.packed_indices)

    @property
    def uncompressed_bytes(self) -> int:
        return self.element_count * 4

    @property
    def compressed_bytes(self) -> int:
        return self.packed_bytes + len(self.norms) * 4 + len(self.signs) * 4 + len(self.centroids) * 4

    @property
    def compression_ratio(self) -> float:
        return self.uncompressed_bytes / max(1, self.compressed_bytes)

    def as_dict(self) -> dict[str, object]:
        return {
            "schema": TURBOQUANT_SCHEMA,
            "shape": list(self.shape),
            "bits": self.bits,
            "seed": self.seed,
            "rotation_mode": self.rotation_mode,
            "packed_indices_b64": base64.b64encode(self.packed_indices).decode("ascii"),
            "norms": list(self.norms),
            "centroids": list(self.centroids),
            "signs": list(self.signs),
        }

    @classmethod
    def from_dict(cls, payload: object) -> "TurboQuantPacket":
        if not isinstance(payload, dict) or payload.get("schema") != TURBOQUANT_SCHEMA:
            raise TurboQuantError("invalid TurboQuant packet schema")
        shape = payload.get("shape")
        bits = payload.get("bits")
        if not isinstance(shape, list) or len(shape) != 2 or not all(isinstance(item, int) for item in shape):
            raise TurboQuantError("TurboQuant packet shape is invalid")
        if not isinstance(bits, int):
            raise TurboQuantError("TurboQuant packet bits are invalid")
        _validate_bits(bits)
        encoded = payload.get("packed_indices_b64")
        try:
            packed = base64.b64decode(encoded, validate=True)
        except (TypeError, ValueError) as exc:
            raise TurboQuantError("TurboQuant packet indices are invalid base64") from exc
        values = (payload.get("norms"), payload.get("centroids"), payload.get("signs"))
        if not all(isinstance(value, list) and all(isinstance(item, (int, float)) for item in value)
                   for value in values):
            raise TurboQuantError("TurboQuant packet numeric fields are invalid")
        return cls(tuple(shape), bits, int(payload.get("seed", 0)), str(payload.get("rotation_mode", "unknown")),
                   packed, tuple(float(item) for item in values[0]),
                   tuple(float(item) for item in values[1]), tuple(float(item) for item in values[2]))


class TurboQuantExecutor:
    """Measured CPU reference codec for KV blocks."""

    backend = "turboquant-kv-numpy"
    profiles = frozenset({"quality", "balanced", "memory", "safe-compressed"})

    @staticmethod
    def available() -> bool:
        try:
            _numpy()
        except TurboQuantError:
            return False
        return True

    def compress(self, vectors: Iterable[Iterable[float]], *, bits: int = 4, seed: int = 0) -> TurboQuantPacket:
        np = _numpy()
        bits = _validate_bits(bits)
        values = np.asarray(list(vectors), dtype=np.float32)
        if values.ndim != 2 or values.shape[0] == 0 or values.shape[1] == 0:
            raise TurboQuantError("TurboQuant input must be a non-empty 2D matrix")
        rows, dimension = (int(values.shape[0]), int(values.shape[1]))
        if rows * dimension > MAX_ELEMENTS:
            raise TurboQuantError("TurboQuant input exceeds the bounded element limit")
        if not np.isfinite(values).all():
            raise TurboQuantError("TurboQuant input contains non-finite values")
        rotation, signs, mode = _rotation(dimension, int(seed), np)
        norms = np.linalg.norm(values, axis=1).astype(np.float32)
        safe_norms = np.where(norms > 0, norms, 1.0).astype(np.float32)
        rotated = (values * signs[None, :]) @ rotation
        normalized = rotated / safe_norms[:, None]
        centroids = np.asarray(_codebook(bits, dimension), dtype=np.float32)
        indices = np.abs(normalized[:, :, None] - centroids[None, None, :]).argmin(axis=2)
        return TurboQuantPacket((rows, dimension), bits, int(seed), mode, _pack(indices, bits),
                                tuple(float(item) for item in norms),
                                tuple(float(item) for item in centroids),
                                tuple(float(item) for item in signs))

    def decompress(self, packet: TurboQuantPacket) -> Any:
        np = _numpy()
        _validate_bits(packet.bits)
        rows, dimension = packet.shape
        if rows <= 0 or dimension <= 0 or rows * dimension > MAX_ELEMENTS:
            raise TurboQuantError("TurboQuant packet shape is outside the bounded range")
        if len(packet.norms) != rows or len(packet.signs) != dimension:
            raise TurboQuantError("TurboQuant packet metadata does not match its shape")
        indices = _unpack(packet.packed_indices, rows * dimension, packet.bits, np).reshape(packet.shape)
        centroids = np.asarray(packet.centroids, dtype=np.float32)
        if len(centroids) != 1 << packet.bits:
            raise TurboQuantError("TurboQuant packet codebook does not match its bit width")
        normalized = centroids[indices]
        rotation, _, _ = _rotation(dimension, packet.seed, np)
        values = (normalized * np.asarray(packet.norms, dtype=np.float32)[:, None]) @ rotation.T
        return values * np.asarray(packet.signs, dtype=np.float32)[None, :]

    def measure(self, vectors: Iterable[Iterable[float]], *, bits: int = 4, seed: int = 0) -> dict[str, object]:
        np = _numpy()
        source = np.asarray(list(vectors), dtype=np.float32)
        packet = self.compress(source, bits=bits, seed=seed)
        reconstructed = self.decompress(packet)
        error = reconstructed - source
        source_norm = np.linalg.norm(source)
        return {
            "schema": TURBOQUANT_SCHEMA,
            "backend": self.backend,
            "bits": packet.bits,
            "shape": list(packet.shape),
            "rotation_mode": packet.rotation_mode,
            "packed_bytes": packet.packed_bytes,
            "compressed_bytes": packet.compressed_bytes,
            "uncompressed_bytes": packet.uncompressed_bytes,
            "compression_ratio": packet.compression_ratio,
            "mse": float(np.mean(error * error)),
            "relative_l2_error": float(np.linalg.norm(error) / max(float(source_norm), 1e-12)),
            "finite": bool(np.isfinite(reconstructed).all()),
        }
