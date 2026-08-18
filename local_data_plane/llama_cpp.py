"""llama.cpp provider boundary used by the Local registry and daemon."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import socket
import subprocess
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .turboquant_backend import discover_installed_executable


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
    turboquant: bool = False


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
    """Real llama.cpp process provider; no fallback is hidden behind its identity."""

    def __init__(self, executable: str | None = None, *, turboquant: bool = False,
                 cache_type_k: str | None = None, cache_type_v: str | None = None,
                 flash_attn: str | None = None):
        requested_turboquant = os.environ.get("SIMPLICIO_LOCAL_LLAMA_TURBOQUANT", "").strip().lower()
        self.turboquant_enabled = turboquant or requested_turboquant in {"1", "true", "yes", "on"}
        managed = discover_installed_executable() if self.turboquant_enabled and executable is None else None
        self.executable = (executable or os.environ.get("SIMPLICIO_LOCAL_LLAMA_SERVER") or managed or
                           shutil.which("llama-server"))
        self.cache_type_k = (cache_type_k or os.environ.get("SIMPLICIO_LOCAL_LLAMA_CACHE_TYPE_K") or
                             ("turbo3" if self.turboquant_enabled else None))
        self.cache_type_v = (cache_type_v or os.environ.get("SIMPLICIO_LOCAL_LLAMA_CACHE_TYPE_V") or
                             ("turbo3" if self.turboquant_enabled else None))
        self.flash_attn = (flash_attn or os.environ.get("SIMPLICIO_LOCAL_LLAMA_FLASH_ATTN") or
                           ("auto" if self.turboquant_enabled else None))
        self.process: subprocess.Popen[bytes] | None = None
        self.port: int | None = None

    @staticmethod
    def _free_port() -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(("127.0.0.1", 0))
            return int(listener.getsockname()[1])

    @staticmethod
    def _env_int(name: str, default: int) -> int:
        value = os.environ.get(name)
        if value in (None, ""):
            return default
        parsed = int(value)
        if parsed < 1:
            raise ValueError(f"{name} must be positive")
        return parsed

    def probe(self, *, turboquant: bool | None = None) -> LlamaCppProbe:
        wants_turboquant = self.turboquant_enabled if turboquant is None else turboquant
        if not self.executable:
            return LlamaCppProbe(None, None, False, platform.system().lower(),
                                 "llama-server executable not found", False)
        try:
            result = subprocess.run([self.executable, "--version"], check=False,
                                    capture_output=True, text=True, timeout=5)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return LlamaCppProbe(self.executable, None, False, platform.system().lower(), str(exc), False)
        version = (result.stdout or result.stderr).strip().splitlines()
        if result.returncode != 0 or not version:
            return LlamaCppProbe(self.executable, None, False, platform.system().lower(),
                                 "llama-server version probe failed", False)
        if not wants_turboquant:
            return LlamaCppProbe(self.executable, version[0], True, platform.system().lower(),
                                 "version probe passed", False)
        try:
            help_result = subprocess.run([self.executable, "--help"], check=False,
                                         capture_output=True, text=True, timeout=5)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return LlamaCppProbe(self.executable, version[0], True, platform.system().lower(),
                                 f"TurboQuant help probe failed: {exc}", False)
        help_text = f"{help_result.stdout}\n{help_result.stderr}".lower()
        turboquant = (help_result.returncode == 0 and "--cache-type-k" in help_text and
                      "--cache-type-v" in help_text and "turbo3" in help_text)
        if not turboquant:
            return LlamaCppProbe(self.executable, version[0], True, platform.system().lower(),
                                 "llama-server is linked but does not advertise TurboQuant turbo3", False)
        return LlamaCppProbe(self.executable, version[0], True, platform.system().lower(),
                             "version and TurboQuant help probes passed", True)

    def load(self, model_path: str | os.PathLike[str]) -> GgufIdentity:
        identity = inspect_gguf(model_path)
        probe = self.probe()
        if not probe.linked:
            raise RuntimeError("llama.cpp is not linked; GGUF identity was validated only")
        if self.turboquant_enabled and not probe.turboquant:
            raise RuntimeError(probe.reason)
        return identity

    def server_args(self, model_path: str | os.PathLike[str], port: int, *, context_size: int,
                    parallel: int, threads: int, threads_batch: int, reasoning: str) -> list[str]:
        """Build the command line separately so the TurboQuant contract is testable."""

        identity = inspect_gguf(model_path)
        args = [self.executable or "llama-server", "--model", identity.path, "--host", "127.0.0.1",
                "--port", str(port), "--no-webui", "--metrics", "--load-mode", "mmap",
                "--ctx-size", str(context_size), "--parallel", str(parallel), "--threads", str(threads),
                "--threads-batch", str(threads_batch), "--reasoning", reasoning]
        if self.turboquant_enabled:
            args.extend(["--cache-type-k", self.cache_type_k or "turbo3",
                         "--cache-type-v", self.cache_type_v or "turbo3",
                         "--flash-attn", self.flash_attn or "auto", "-kvu"])
        return args

    def start_server(self, model_path: str | os.PathLike[str], port: int = 0) -> None:
        identity = self.load(model_path)
        assert self.executable is not None
        if self.process is not None and self.process.poll() is None:
            raise RuntimeError("llama.cpp server is already running")
        selected_port = port or self._free_port()
        context_size = self._env_int("SIMPLICIO_LOCAL_LLAMA_CTX", 1024)
        threads = self._env_int("SIMPLICIO_LOCAL_LLAMA_THREADS", os.cpu_count() or 1)
        threads_batch = self._env_int("SIMPLICIO_LOCAL_LLAMA_THREADS_BATCH", threads)
        parallel = self._env_int("SIMPLICIO_LOCAL_LLAMA_PARALLEL", 1)
        startup_timeout = float(os.environ.get("SIMPLICIO_LOCAL_LLAMA_STARTUP_TIMEOUT", "300"))
        reasoning = os.environ.get("SIMPLICIO_LOCAL_LLAMA_REASONING", "off").strip().lower()
        self.process = subprocess.Popen(
            self.server_args(identity.path, selected_port, context_size=context_size,
                             parallel=parallel, threads=threads, threads_batch=threads_batch,
                             reasoning=reasoning),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        self.port = selected_port
        deadline = time.monotonic() + startup_timeout
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                detail = self._stderr_tail()
                self.stop()
                raise RuntimeError(f"llama.cpp server exited during startup: {detail}")
            try:
                with urlopen(f"http://127.0.0.1:{selected_port}/health", timeout=2) as response:
                    if response.status == 200:
                        return
            except (OSError, HTTPError, URLError):
                pass
            time.sleep(0.25)
        self.stop()
        raise RuntimeError(f"llama.cpp server did not become ready within {startup_timeout:.0f}s")

    def _stderr_tail(self) -> str:
        if self.process is None or self.process.stderr is None:
            return "no stderr available"
        try:
            return self.process.stderr.read().decode("utf-8", "replace")[-2000:].strip()
        except (OSError, ValueError):
            return "unable to read stderr"

    def generate(self, prompt: str, max_tokens: int) -> dict[str, Any]:
        if self.port is None or self.process is None or self.process.poll() is not None:
            raise RuntimeError("llama.cpp server is not running")
        if max_tokens < 0 or max_tokens > 4096:
            raise ValueError("max_tokens is outside the bounded range")
        temperature = float(os.environ.get("SIMPLICIO_LOCAL_LLAMA_TEMPERATURE", "0"))
        body = {
            "model": "local",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,
        }
        timeout = float(os.environ.get("SIMPLICIO_LOCAL_LLAMA_REQUEST_TIMEOUT", "600"))
        request = Request(
            f"http://127.0.0.1:{self.port}/v1/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (OSError, HTTPError, URLError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"llama.cpp generation failed: {exc}") from exc
        choices = payload.get("choices") or []
        if not choices:
            raise RuntimeError("llama.cpp response contained no choices")
        choice = choices[0]
        message = choice.get("message") or {}
        text = str(message.get("content") or message.get("reasoning_content") or "")
        usage = payload.get("usage") or {}
        timings = payload.get("timings") or {}
        return {
            "text": text,
            "generated_tokens": int(usage.get("completion_tokens", 0)),
            "prompt_tokens": int(usage.get("prompt_tokens", 0)),
            "finish_reason": str(choice.get("finish_reason", "stop")),
            "timings": timings,
        }

    def stop(self) -> None:
        if self.process is None:
            return
        stderr = self.process.stderr
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        if stderr is not None:
            stderr.close()
        self.process = None
        self.port = None

    def __enter__(self) -> "LlamaCppProvider":
        return self

    def __exit__(self, *_: object) -> None:
        self.stop()
