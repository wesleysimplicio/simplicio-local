"""Experimental bounded dense layer streaming executor."""

from __future__ import annotations

import hashlib
import struct
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence


@dataclass(frozen=True)
class LayerDescriptor:
    path: str
    rows: int
    cols: int
    dtype: str = "float32"
    scale: float = 1.0
    offset: int = 0
    sha256: str | None = None

    @property
    def item_bytes(self) -> int:
        if self.dtype == "float32":
            return 4
        if self.dtype == "int8":
            return 1
        raise ValueError(f"unsupported dense stream dtype: {self.dtype}")

    @property
    def weight_bytes(self) -> int:
        return self.rows * self.cols * self.item_bytes

    def validate(self) -> None:
        if self.rows <= 0 or self.cols <= 0 or self.offset < 0:
            raise ValueError("layer dimensions and offset must be positive")
        path = Path(self.path)
        if not path.is_file():
            raise FileNotFoundError(self.path)
        if self.offset + self.weight_bytes > path.stat().st_size:
            raise ValueError("layer descriptor extends past container")


@dataclass(frozen=True)
class DenseStreamMetrics:
    layers: int
    bytes_read: int
    bytes_per_token: float | None
    peak_weight_bytes: int
    maximum_weight_slots: int
    elapsed_ms: float


@dataclass(frozen=True)
class DenseStreamResult:
    status: str
    output: tuple[float, ...]
    metrics: DenseStreamMetrics
    error: str | None = None


def _read_layer(layer: LayerDescriptor, rows_per_slab: int, cancelled: Callable[[], bool] | None):
    path = Path(layer.path)
    with path.open("rb") as stream:
        stream.seek(layer.offset)
        for first in range(0, layer.rows, rows_per_slab):
            if cancelled and cancelled():
                yield None
                return
            rows = min(rows_per_slab, layer.rows - first)
            payload = stream.read(rows * layer.cols * layer.item_bytes)
            if len(payload) != rows * layer.cols * layer.item_bytes:
                raise IOError("dense layer slab read was truncated")
            if layer.dtype == "float32":
                values = struct.unpack("!" + "f" * (rows * layer.cols), payload)
            else:
                values = tuple(value * layer.scale for value in struct.unpack("!" + "b" * len(payload), payload))
            yield first, rows, tuple(values)


class DenseStreamExecutor:
    def __init__(self, layers: Sequence[LayerDescriptor], *, rows_per_slab: int = 1,
                 workload: str = "deep-offline", experimental: bool = True):
        if rows_per_slab <= 0:
            raise ValueError("rows_per_slab must be positive")
        if not experimental or workload == "interactive":
            raise ValueError("dense layer streaming is experimental and non-interactive")
        self.layers = tuple(layers)
        self.rows_per_slab = rows_per_slab
        self.workload = workload

    def _load(self, layer: LayerDescriptor) -> list[float]:
        layer.validate()
        path = Path(layer.path)
        if layer.sha256 is not None:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest != layer.sha256:
                raise IOError("dense container checksum mismatch")
        values: list[float] = []
        for slab in _read_layer(layer, self.rows_per_slab, None):
            if slab is None:
                raise RuntimeError("unexpected cancellation")
            values.extend(slab[2])
        return values

    def run(self, input_values: Sequence[float], *, cancelled: Callable[[], bool] | None = None) -> DenseStreamResult:
        started = time.monotonic()
        bytes_read = 0
        peak = 0
        current = tuple(float(value) for value in input_values)
        try:
            for layer in self.layers:
                layer.validate()
                if layer.cols != len(current):
                    raise ValueError("dense layer dimensions do not form a valid chain")
                next_values = [0.0] * layer.rows
                for slab in _read_layer(layer, self.rows_per_slab, cancelled):
                    if slab is None:
                        return DenseStreamResult("cancelled", (), self._metrics(bytes_read, peak, started))
                    first, rows, weights = slab
                    slab_bytes = rows * layer.cols * layer.item_bytes
                    bytes_read += slab_bytes
                    peak = max(peak, slab_bytes * 2)
                    for row in range(rows):
                        base = row * layer.cols
                        next_values[first + row] = sum(weights[base + col] * current[col] for col in range(layer.cols))
                    if cancelled and cancelled():
                        return DenseStreamResult("cancelled", (), self._metrics(bytes_read, peak, started))
                current = tuple(next_values)
            return DenseStreamResult("completed", current, self._metrics(bytes_read, peak, started))
        except (OSError, ValueError, IOError) as exc:
            return DenseStreamResult("failed", (), self._metrics(bytes_read, peak, started), str(exc))

    def _metrics(self, bytes_read: int, peak: int, started: float) -> DenseStreamMetrics:
        return DenseStreamMetrics(len(self.layers), bytes_read,
                                  float(bytes_read) if bytes_read else None,
                                  peak, 2 if peak else 0, (time.monotonic() - started) * 1000.0)
