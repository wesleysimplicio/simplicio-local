"""Resumable content-addressed model cache with lifecycle operations."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen


CACHE_SCHEMA_V1 = "simplicio-local.model-cache/v1"


@dataclass(frozen=True)
class CacheArtifact:
    model_id: str
    quantization: str
    source: str
    size_bytes: int
    sha256: str
    provenance: dict[str, Any] | None = None

    @property
    def ref_id(self) -> str:
        safe_model = "".join(char if char.isalnum() or char in "._-" else "_" for char in self.model_id)
        safe_quant = "".join(char if char.isalnum() or char in "._-" else "_" for char in self.quantization)
        return f"{safe_model}--{safe_quant}--{self.sha256}"


class ModelCache:
    def __init__(self, root: str | os.PathLike[str]):
        self.root = Path(root)
        self.objects = self.root / "objects"
        self.refs = self.root / "refs"
        self.parts = self.root / "parts"
        for directory in (self.objects, self.refs, self.parts):
            directory.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _hash(path: Path) -> tuple[str, int]:
        digest = hashlib.sha256()
        size = 0
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
                size += len(chunk)
        return digest.hexdigest(), size

    def _ref_path(self, artifact: CacheArtifact) -> Path:
        return self.refs / f"{artifact.ref_id}.json"

    def _write_ref(self, artifact: CacheArtifact, object_path: Path, aliases: tuple[str, ...]) -> None:
        payload = {"schema": CACHE_SCHEMA_V1, "artifact": asdict(artifact), "object": str(object_path),
                   "aliases": list(aliases)}
        destination = self._ref_path(artifact)
        fd, temporary = tempfile.mkstemp(prefix=f".{destination.name}.", dir=self.refs)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(payload, stream, indent=2, sort_keys=True)
                stream.write("\n")
                os.fsync(stream.fileno())
            os.replace(temporary, destination)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def _open_source(self, source: str, offset: int):
        source_path = Path(source)
        if source_path.is_file():
            stream = source_path.open("rb")
            stream.seek(offset)
            return stream
        request = Request(source, headers={"Range": f"bytes={offset}-"} if offset else {})
        return urlopen(request, timeout=30)

    def download(self, artifact: CacheArtifact, *, aliases: tuple[str, ...] = ()) -> Path:
        if artifact.size_bytes <= 0 or len(artifact.sha256) != 64:
            raise ValueError("artifact size and SHA-256 are required")
        target = self.objects / artifact.sha256
        if target.is_file():
            digest, size = self._hash(target)
            if digest == artifact.sha256 and size == artifact.size_bytes:
                self._write_ref(artifact, target, aliases)
                return target
            target.unlink()
        part = self.parts / f"{artifact.sha256}.part"
        current = part.stat().st_size if part.exists() else 0
        if current > artifact.size_bytes:
            part.unlink()
            current = 0
        free = shutil.disk_usage(self.root).free
        if free < artifact.size_bytes - current:
            raise OSError("insufficient disk space for model artifact")
        try:
            with self._open_source(artifact.source, current) as source:
                # A server that ignores Range returns the full object; restart
                # safely instead of duplicating bytes in the partial file.
                if current and getattr(source, "status", 206) == 200:
                    part.unlink()
                    with self._open_source(artifact.source, 0) as fresh, part.open("wb") as reset:
                        shutil.copyfileobj(fresh, reset, length=1024 * 1024)
                        reset.flush()
                        os.fsync(reset.fileno())
                else:
                    with part.open("ab") as destination:
                        shutil.copyfileobj(source, destination, length=1024 * 1024)
                        destination.flush()
                        os.fsync(destination.fileno())
        except Exception:
            # Keep the .part file so the next invocation can resume.
            raise
        if part.stat().st_size != artifact.size_bytes:
            raise IOError("download did not reach the catalogued artifact size")
        digest, size = self._hash(part)
        if digest.casefold() != artifact.sha256.casefold() or size != artifact.size_bytes:
            raise ValueError("downloaded artifact failed checksum verification")
        os.replace(part, target)
        self._write_ref(artifact, target, aliases)
        return target

    def _load_ref(self, ref_id: str) -> dict[str, Any]:
        matches = sorted(self.refs.glob(f"{ref_id}.json"))
        if not matches:
            raise KeyError(ref_id)
        return json.loads(matches[0].read_text(encoding="utf-8"))

    def list(self) -> tuple[dict[str, Any], ...]:
        return tuple(json.loads(path.read_text(encoding="utf-8")) for path in sorted(self.refs.glob("*.json")))

    def verify(self, ref_id: str) -> bool:
        payload = self._load_ref(ref_id)
        artifact = CacheArtifact(**payload["artifact"])
        path = Path(payload["object"])
        if not path.is_file():
            return False
        digest, size = self._hash(path)
        return digest == artifact.sha256 and size == artifact.size_bytes

    def remove(self, ref_id: str) -> None:
        payload = self._load_ref(ref_id)
        ref_path = next(self.refs.glob(f"{ref_id}.json"))
        ref_path.unlink()
        remaining = list(self.refs.glob(f"*--{payload['artifact']['sha256']}.json"))
        object_path = Path(payload["object"])
        if not remaining and object_path.is_file():
            object_path.unlink()

    def repair(self, ref_id: str) -> Path:
        payload = self._load_ref(ref_id)
        artifact = CacheArtifact(**payload["artifact"])
        if self.verify(ref_id):
            return Path(payload["object"])
        return self.download(artifact, aliases=tuple(payload.get("aliases", ())))

    def status(self) -> dict[str, Any]:
        objects = tuple(path for path in self.objects.iterdir() if path.is_file())
        return {"schema": CACHE_SCHEMA_V1, "entries": len(self.list()),
                "objects": len(objects), "bytes": sum(path.stat().st_size for path in objects)}
