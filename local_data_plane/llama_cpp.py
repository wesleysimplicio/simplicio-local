"""llama.cpp provider boundary used by the Local registry and daemon."""

from __future__ import annotations

import hashlib
import os
import platform
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class GgufIdentity:
    path: str
    size_bytes: int
    sha256: str
    magic: str
    architecture: str | None = None
    chat_template: str | None = None
    recurrent_state: bool | None = None


@dataclass(frozen=True)
class LlamaCppProbe:
    executable: str | None
    version: str | None
    linked: bool
    platform: str
    reason: str


def inspect_gguf(path: str | os.PathLike[str]) -> GgufIdentity:
    """Validate the file identity without treating its filename as a model claim."""

    model_path = Path(path)
    if model_path.suffix.lower() != ".gguf":
        raise ValueError("llama.cpp provider requires a .gguf asset")
    if not model_path.is_file():
        raise FileNotFoundError(str(model_path))
    with model_path.open("rb") as stream:
        if stream.read(4) != b"GGUF":
            raise ValueError("asset does not contain a GGUF magic header")
        digest = hashlib.sha256()
        stream.seek(0)
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return GgufIdentity(str(model_path), model_path.stat().st_size, digest.hexdigest(), "GGUF")


class LlamaCppProvider:
    """Process provider; no fallback is hidden behind the requested identity."""

    def __init__(self, executable: str | None = None):
        self.executable = executable or shutil.which("llama-server")
        self.process: subprocess.Popen[bytes] | None = None

    def probe(self) -> LlamaCppProbe:
        if not self.executable:
            return LlamaCppProbe(None, None, False, platform.system().lower(),
                                 "llama-server executable not found")
        try:
            result = subprocess.run([self.executable, "--version"], check=False,
                                    capture_output=True, text=True, timeout=5)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return LlamaCppProbe(self.executable, None, False, platform.system().lower(), str(exc))
        version = (result.stdout or result.stderr).strip().splitlines()
        if result.returncode != 0 or not version:
            return LlamaCppProbe(self.executable, None, False, platform.system().lower(),
                                 "llama-server version probe failed")
        return LlamaCppProbe(self.executable, version[0], True, platform.system().lower(), "version probe passed")

    def load(self, model_path: str | os.PathLike[str]) -> GgufIdentity:
        identity = inspect_gguf(model_path)
        probe = self.probe()
        if not probe.linked:
            raise RuntimeError("llama.cpp is not linked; GGUF identity was validated only")
        return identity

    def start_server(self, model_path: str | os.PathLike[str], port: int) -> None:
        identity = self.load(model_path)
        assert self.executable is not None
        if self.process is not None and self.process.poll() is None:
            raise RuntimeError("llama.cpp server is already running")
        self.process = subprocess.Popen(
            [self.executable, "--model", identity.path, "--host", "127.0.0.1",
             "--port", str(port), "--no-webui"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def stop(self) -> None:
        if self.process is None:
            return
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        self.process = None

    def __enter__(self) -> "LlamaCppProvider":
        return self

    def __exit__(self, *_: object) -> None:
        self.stop()
