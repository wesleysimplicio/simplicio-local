"""Bounded disk-first expert streaming primitives for Colibri."""

from __future__ import annotations

import hashlib
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable


@dataclass(frozen=True)
class ExpertShard:
    expert_id: str
    path: str
    sha256: str | None = None


@dataclass(frozen=True)
class ColibriMetrics:
    bytes_read: int
    tokens: int
    cache_hits: int
    cache_misses: int
    evictions: int
    read_bytes_per_token: float | None
    swap: int | None = None
    swap_semantics: str = "unknown"


@dataclass(frozen=True)
class ColibriRun:
    output: tuple[bytes, ...]
    metrics: ColibriMetrics
    status: str
    error: str | None = None


class ExpertCache:
    def __init__(self, capacity: int):
        if capacity <= 0:
            raise ValueError("expert cache capacity must be positive")
        self.capacity = capacity
        self._items: OrderedDict[str, bytes] = OrderedDict()
        self.hits = 0
        self.misses = 0
        self.evictions = 0

    def get_or_load(self, expert_id: str, loader: Callable[[], bytes]) -> bytes:
        if expert_id in self._items:
            self.hits += 1
            value = self._items.pop(expert_id)
            self._items[expert_id] = value
            return value
        self.misses += 1
        value = loader()
        self._items[expert_id] = value
        if len(self._items) > self.capacity:
            self._items.popitem(last=False)
            self.evictions += 1
        return value


class ColibriBackend:
    def __init__(self, shards: Iterable[ExpertShard], *, cache_capacity: int = 2):
        self.shards = {shard.expert_id: shard for shard in shards}
        if len(self.shards) == 0:
            raise ValueError("Colibri requires at least one expert shard")
        self.cache = ExpertCache(cache_capacity)

    @staticmethod
    def _read(shard: ExpertShard) -> bytes:
        path = Path(shard.path)
        if not path.is_file():
            raise FileNotFoundError(f"expert shard is missing: {path}")
        data = path.read_bytes()
        if shard.sha256 is not None:
            digest = hashlib.sha256(data).hexdigest()
            if digest != shard.sha256:
                raise IOError(f"expert shard hash mismatch: {path}")
        return data

    def stream(self, routing: Iterable[str], *, cancelled: Callable[[], bool] | None = None) -> ColibriRun:
        outputs: list[bytes] = []
        tokens = 0
        bytes_read_before = 0
        try:
            for expert_id in routing:
                if cancelled and cancelled():
                    return ColibriRun((), self._metrics(tokens, bytes_read_before), "cancelled")
                shard = self.shards.get(expert_id)
                if shard is None:
                    return ColibriRun((), self._metrics(tokens, bytes_read_before), "failed",
                                      f"unknown expert shard: {expert_id}")
                was_miss = expert_id not in self.cache._items
                data = self.cache.get_or_load(expert_id, lambda s=shard: self._read(s))
                if was_miss:
                    bytes_read_before += len(data)
                outputs.append(data)
                tokens += 1
            return ColibriRun(tuple(outputs), self._metrics(tokens, bytes_read_before), "completed")
        except (OSError, IOError) as exc:
            return ColibriRun((), self._metrics(tokens, bytes_read_before), "failed", str(exc))

    def _metrics(self, tokens: int, bytes_read: int) -> ColibriMetrics:
        return ColibriMetrics(bytes_read, tokens, self.cache.hits, self.cache.misses,
                              self.cache.evictions, bytes_read / tokens if tokens else None)
