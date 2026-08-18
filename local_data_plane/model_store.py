"""Offline, content-addressed model store with atomic update and rollback."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path


MODEL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


@dataclass(frozen=True)
class ModelRecord:
    model_id: str
    revision: str
    sha256: str
    size_bytes: int
    source_name: str
    license: str
    format: str
    history: tuple[str, ...] = ()


class ModelStore:
    """A store that never downloads or overwrites user-owned model files."""

    def __init__(self, root: str | os.PathLike[str]):
        self.root = Path(root)
        self.objects = self.root / "objects" / "sha256"
        self.refs = self.root / "refs"
        self.parts = self.root / ".parts"
        for directory in (self.objects, self.refs, self.parts):
            directory.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _validate_id(model_id: str) -> None:
        if not MODEL_ID.fullmatch(model_id):
            raise ValueError("model_id contains unsupported path characters")

    @staticmethod
    def _hash(path: Path) -> tuple[str, int]:
        digest = hashlib.sha256()
        size = 0
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
                size += len(chunk)
        return digest.hexdigest(), size

    @staticmethod
    def _format(path: Path) -> str:
        suffix = path.suffix.lower()
        return suffix[1:] if suffix else "unknown"

    def _manifest_path(self, model_id: str) -> Path:
        self._validate_id(model_id)
        return self.refs / f"{model_id}.json"

    def _write_manifest(self, record: ModelRecord) -> None:
        destination = self._manifest_path(record.model_id)
        fd, name = tempfile.mkstemp(prefix=f"{record.model_id}.", suffix=".tmp", dir=self.refs)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(asdict(record), stream, sort_keys=True, separators=(",", ":"))
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, destination)
        finally:
            if os.path.exists(name):
                os.unlink(name)

    def _copy_resumable(self, source: Path, digest: str) -> int:
        part = self.parts / f"{digest}.part"
        source_size = source.stat().st_size
        current = part.stat().st_size if part.exists() else 0
        if current > source_size:
            part.unlink()
            current = 0
        with source.open("rb") as source_stream:
            source_stream.seek(current)
            with part.open("ab") as destination:
                shutil.copyfileobj(source_stream, destination, length=1024 * 1024)
                destination.flush()
                os.fsync(destination.fileno())
        if part.stat().st_size != source_size:
            raise IOError("resumable copy did not reach source size")
        target = self.objects / digest
        if target.exists():
            if self._hash(target)[0] != digest:
                raise IOError("existing content-addressed object has a hash collision")
            part.unlink()
        else:
            os.replace(part, target)
        return source_size

    def put_file(self, source: str | os.PathLike[str], model_id: str, *, revision: str = "unknown",
                 license: str = "unknown", expected_sha256: str | None = None) -> ModelRecord:
        self._validate_id(model_id)
        source_path = Path(source)
        if not source_path.is_file():
            raise FileNotFoundError(str(source_path))
        digest, size = self._hash(source_path)
        if expected_sha256 is not None and digest != expected_sha256:
            raise ValueError("source hash does not match expected_sha256")
        self._copy_resumable(source_path, digest)
        previous = self.get(model_id)
        history = (previous.history + (previous.sha256,)) if previous else ()
        record = ModelRecord(model_id, revision, digest, size, source_path.name,
                             license, self._format(source_path), history)
        self._write_manifest(record)
        return record

    def get(self, model_id: str) -> ModelRecord | None:
        path = self._manifest_path(model_id)
        if not path.is_file():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return ModelRecord(**{**data, "history": tuple(data.get("history", ()))})

    def resolve(self, model_id: str) -> Path:
        record = self.get(model_id)
        if record is None:
            raise KeyError(model_id)
        path = self.objects / record.sha256
        if not path.is_file() or self._hash(path)[0] != record.sha256:
            raise IOError(f"content-addressed object is missing or corrupt: {model_id}")
        return path

    def verify(self, model_id: str) -> bool:
        try:
            self.resolve(model_id)
        except (KeyError, IOError):
            return False
        return True

    def rollback(self, model_id: str) -> ModelRecord:
        current = self.get(model_id)
        if current is None or not current.history:
            raise ValueError("no previous model revision is available")
        previous_digest = current.history[0]
        previous_path = self.objects / previous_digest
        if not previous_path.is_file() or self._hash(previous_path)[0] != previous_digest:
            raise IOError("previous model object is missing or corrupt")
        remaining = current.history[1:]
        record = ModelRecord(current.model_id, current.revision, previous_digest,
                             previous_path.stat().st_size, current.source_name,
                             current.license, current.format, remaining)
        self._write_manifest(record)
        return record
