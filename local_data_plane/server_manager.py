"""Lifecycle manager for a local OpenAI-compatible inference server."""

from __future__ import annotations

import json
import os
import secrets
import signal
import socket
import subprocess
import tempfile
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


SERVER_METADATA_SCHEMA_V1 = "simplicio-local.connection-metadata/v1"


@dataclass(frozen=True)
class ServerSpec:
    model_id: str
    backend: str
    quantization: str
    command: tuple[str, ...]
    host: str = "127.0.0.1"
    port: int = 0
    strategy: str = "baseline"
    auth_enabled: bool = False


@dataclass(frozen=True)
class ConnectionMetadata:
    schema: str
    base_url: str
    model_id: str
    backend: str
    quantization: str
    strategy: str
    api_key: str | None
    pid: int
    health: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class OpenAICompatibleServerManager:
    def __init__(self, state_root: str | os.PathLike[str]):
        self.state_root = Path(state_root)
        self.state_root.mkdir(parents=True, exist_ok=True)
        self.metadata_path = self.state_root / "connection.json"
        self.key_path = self.state_root / "api-key"
        self._processes: dict[int, subprocess.Popen[bytes]] = {}

    @staticmethod
    def _free_port(host: str) -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind((host, 0))
            return int(sock.getsockname()[1])

    @staticmethod
    def _url(base_url: str, path: str) -> str:
        return base_url.rstrip("/") + "/" + path.lstrip("/")

    def _health(self, base_url: str, api_key: str | None = None) -> bool:
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        try:
            with urlopen(Request(self._url(base_url, "/models"), headers=headers), timeout=1.5) as response:
                return response.status == 200
        except (OSError, HTTPError, URLError):
            return False

    def health(self, metadata: ConnectionMetadata) -> dict[str, Any]:
        models = self._health(metadata.base_url, metadata.api_key)
        return {"ready": models, "models": models, "chat_completions": models,
                "base_url": metadata.base_url}

    def _load_metadata(self) -> ConnectionMetadata | None:
        if not self.metadata_path.is_file():
            return None
        return ConnectionMetadata(**json.loads(self.metadata_path.read_text(encoding="utf-8")))

    def _write_metadata(self, metadata: ConnectionMetadata) -> None:
        fd, temporary = tempfile.mkstemp(prefix=".connection.", dir=self.state_root)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(metadata.as_dict(), stream, indent=2, sort_keys=True)
                stream.write("\n")
                os.fsync(stream.fileno())
            os.replace(temporary, self.metadata_path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def _api_key(self, enabled: bool) -> str | None:
        if not enabled:
            return None
        if self.key_path.is_file():
            return self.key_path.read_text(encoding="utf-8").strip()
        value = secrets.token_urlsafe(32)
        self.key_path.write_text(value + "\n", encoding="utf-8")
        try:
            self.key_path.chmod(0o600)
        except OSError:
            pass
        return value

    def start(self, spec: ServerSpec, *, timeout: float = 30.0) -> ConnectionMetadata:
        current = self._load_metadata()
        if current and current.model_id == spec.model_id and current.backend == spec.backend and \
                current.quantization == spec.quantization and self._health(current.base_url, current.api_key):
            return current
        if current:
            self.stop()
        port = spec.port or self._free_port(spec.host)
        base_url = f"http://{spec.host}:{port}/v1"
        api_key = self._api_key(spec.auth_enabled)
        command = tuple(item.format(host=spec.host, port=port, api_key=api_key or "") for item in spec.command)
        process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        self._processes[process.pid] = process
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if process.poll() is not None:
                detail = (process.stderr.read() if process.stderr else b"").decode("utf-8", "replace")[-1000:]
                raise RuntimeError(f"server exited before readiness: {detail}")
            if self._health(base_url, api_key):
                metadata = ConnectionMetadata(SERVER_METADATA_SCHEMA_V1, base_url, spec.model_id, spec.backend,
                                              spec.quantization, spec.strategy, api_key, process.pid, "ready")
                self._write_metadata(metadata)
                return metadata
            time.sleep(0.1)
        process.terminate()
        raise TimeoutError("OpenAI-compatible server did not become ready")

    def status(self) -> dict[str, Any]:
        metadata = self._load_metadata()
        if metadata is None:
            return {"schema": SERVER_METADATA_SCHEMA_V1, "state": "empty", "health": {"ready": False}}
        return {**metadata.as_dict(), "state": "running" if self._health(metadata.base_url, metadata.api_key) else "stale",
                "health": self.health(metadata)}

    def stop(self) -> dict[str, Any]:
        metadata = self._load_metadata()
        if metadata is None:
            return {"schema": SERVER_METADATA_SCHEMA_V1, "stopped": False, "reason": "no-managed-server"}
        try:
            os.kill(metadata.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        except PermissionError as exc:
            raise RuntimeError(f"cannot stop managed server: {exc}") from exc
        process = self._processes.pop(metadata.pid, None)
        if process is not None:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            if process.stderr is not None:
                process.stderr.close()
        else:
            try:
                os.waitpid(metadata.pid, 0)
            except (ChildProcessError, OSError):
                # A manager restarted in another process cannot reap the child;
                # the metadata cleanup is still safe and idempotent.
                pass
        self.metadata_path.unlink(missing_ok=True)
        return {"schema": SERVER_METADATA_SCHEMA_V1, "stopped": True, "pid": metadata.pid}
