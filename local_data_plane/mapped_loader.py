"""Verified read-only mmap loader with generation-safe lifecycle."""

from __future__ import annotations

import hashlib
import mmap
import os
from dataclasses import dataclass
from pathlib import Path


MAPPED_LOADER_SCHEMA_V1 = "simplicio-local.mapped-loader/v1"


@dataclass(frozen=True)
class MappingIdentity:
    path: str
    sha256: str
    generation: str
    size_bytes: int


class ReadOnlyModelMapping:
    def __init__(self, file_handle, mapped: mmap.mmap, identity: MappingIdentity):
        self._file_handle = file_handle
        self._mapped = mapped
        self.identity = identity
        self._closed = False

    def read(self, start: int = 0, size: int | None = None) -> bytes:
        if self._closed:
            raise ValueError("mapping is closed")
        if start < 0 or start > self.identity.size_bytes:
            raise ValueError("mapping read start is outside artifact")
        length = self.identity.size_bytes - start if size is None else size
        if length < 0 or start + length > self.identity.size_bytes:
            raise ValueError("mapping read exceeds artifact bounds")
        return self._mapped[start:start + length]

    def close(self) -> None:
        if not self._closed:
            self._mapped.close()
            self._file_handle.close()
            self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


class PersistentMappedLoader:
    @staticmethod
    def _hash(path: Path) -> tuple[str, int]:
        digest = hashlib.sha256()
        size = 0
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
                size += len(chunk)
        return digest.hexdigest(), size

    def map_verified(self, path: str | os.PathLike[str], *, expected_sha256: str,
                     generation: str) -> ReadOnlyModelMapping:
        candidate = Path(path)
        if not candidate.is_file():
            raise FileNotFoundError(str(candidate))
        digest, size = self._hash(candidate)
        if digest.casefold() != expected_sha256.casefold():
            raise ValueError("artifact checksum does not match mapping identity")
        handle = candidate.open("rb")
        try:
            mapped = mmap.mmap(handle.fileno(), length=0, access=mmap.ACCESS_READ)
        except Exception:
            handle.close()
            raise
        return ReadOnlyModelMapping(handle, mapped, MappingIdentity(str(candidate), digest, generation, size))

    @staticmethod
    def read_buffered(path: str | os.PathLike[str], *, expected_sha256: str) -> bytes:
        candidate = Path(path)
        digest, _ = PersistentMappedLoader._hash(candidate)
        if digest.casefold() != expected_sha256.casefold():
            raise ValueError("artifact checksum does not match buffered identity")
        return candidate.read_bytes()

    @staticmethod
    def can_replace(active: ReadOnlyModelMapping | None, *, new_generation: str) -> bool:
        return active is None or active.identity.generation != new_generation

    @staticmethod
    def remove(path: str | os.PathLike[str], *, active: ReadOnlyModelMapping | None = None) -> None:
        candidate = Path(path)
        if active is not None and active.identity.path == str(candidate) and not active._closed:
            raise RuntimeError("mapped artifact is active; close the generation before removal")
        candidate.unlink()
