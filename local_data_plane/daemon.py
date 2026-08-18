"""Persistent, backend-neutral Local inference daemon.

The first implementation intentionally provides a deterministic fixture backend
so lifecycle and transport can be tested without silently claiming that a
large model or a platform-specific engine executed.  Real providers register
through the registry added in the following delivery lane.
"""

from __future__ import annotations

import argparse
import os
import queue
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO, Any

from .binary import ERROR, EVENT, REQUEST, RESPONSE, FrameError, read_frame, write_frame
from .protocol import METHODS, PROTOCOL_NAME, PROTOCOL_VERSION, error, ok
from .llama_cpp import LlamaCppProvider
from .registry import BackendRegistry
from .telemetry import ReceiptBuilder


@dataclass
class ModelHandle:
    handle_id: str
    model_id: str
    path: str | None = None
    backend: str = "fixture"
    provider: LlamaCppProvider | None = field(default=None, repr=False)
    state: str = "loaded"
    warmed: bool = False
    created_at: float = field(default_factory=time.monotonic)


class InferenceDaemon:
    """Owns physical lifecycle state and exposes only inference operations."""

    def __init__(self, home: str | os.PathLike[str] | None = None, *, standalone: bool = False,
                 repo_root: str | os.PathLike[str] | None = None):
        self.home = Path(home or os.environ.get("SIMPLICIO_LOCAL_HOME", ".simplicio-local"))
        self.standalone = standalone
        self.state = "cold"
        self.draining = False
        self.handles: dict[str, ModelHandle] = {}
        self._cancelled: dict[int, threading.Event] = {}
        self._lock = threading.RLock()
        self._started_at = time.monotonic()
        self._request_count = 0
        self.registry = BackendRegistry.default(repo_root)

    def _identity(self) -> dict[str, object]:
        return {
            "protocol": PROTOCOL_NAME,
            "protocol_version": PROTOCOL_VERSION,
            "effect_authority": "none",
            "standalone": self.standalone,
            "build": "python-data-plane-fixture",
        }

    def handle(self, request: dict[str, Any], request_id: int = 0) -> list[tuple[int, dict[str, Any]]]:
        if not isinstance(request, dict) or not isinstance(request.get("method"), str):
            return [(ERROR, error("unknown", "invalid_request", "request must contain a method"))]
        method = request["method"]
        if method not in METHODS:
            return [(ERROR, error(method, "unknown_method", method))]
        with self._lock:
            self._request_count += 1
            if method == "handshake":
                self.state = "ready"
                return [(RESPONSE, ok(method, **self._identity(), methods=list(METHODS), state=self.state))]
            if method == "capabilities":
                return [(RESPONSE, ok(method, capabilities=self.registry.catalog(),
                                       release_matrix=self.registry.release_matrix()))]
            if method == "estimate":
                return [(RESPONSE, ok(method, weights_bytes=0, kv_bytes=0, io_bytes=0,
                                       source="unknown", value_semantics="unknown"))]
            if method == "load":
                if self.draining:
                    return [(ERROR, error(method, "draining", "daemon is draining"))]
                model_id = str(request.get("model_id", "fixture"))
                backend = str(request.get("backend", "fixture")).strip().lower() or "fixture"
                path = request.get("path")
                if path is not None and not Path(str(path)).is_file():
                    return [(ERROR, error(method, "model_unavailable", "model path is unavailable"))]
                if backend == "turboquant":
                    return [(ERROR, error(method, "backend_unavailable",
                                          "TurboQuant is an evidence gate in this build; no executor is installed"))]
                if backend not in {"fixture", "llama-cpp"}:
                    return [(ERROR, error(method, "backend_unavailable",
                                          f"backend {backend!r} has no executable provider"))]
                handle_id = str(request.get("handle_id") or uuid.uuid4().hex)
                if handle_id in self.handles:
                    handle = self.handles[handle_id]
                    return [(RESPONSE, ok(method, handle_id=handle.handle_id, state=handle.state, idempotent=True))]
                provider = None
                if backend == "llama-cpp":
                    if path is None:
                        return [(ERROR, error(method, "model_unavailable",
                                              "llama-cpp requires an explicit GGUF path"))]
                    try:
                        provider = LlamaCppProvider(executable=request.get("executable"))
                        provider.start_server(str(path), int(request.get("port", 0)))
                    except (OSError, RuntimeError, ValueError) as exc:
                        if provider is not None:
                            provider.stop()
                        return [(ERROR, error(method, "backend_start_failed", str(exc)))]
                self.state = "ready"
                handle = ModelHandle(handle_id, model_id, str(path) if path else None, backend, provider)
                self.handles[handle_id] = handle
                return [(RESPONSE, ok(method, handle_id=handle_id, state=handle.state,
                                       model_id=model_id, backend=backend))]
            if method == "warm":
                handle = self._get_handle(request)
                if handle is None:
                    return [(ERROR, error(method, "unknown_handle", "model handle is not loaded"))]
                handle.warmed = True
                handle.state = "loaded"
                return [(RESPONSE, ok(method, handle_id=handle.handle_id, state="warmed"))]
            if method == "generate":
                return self._generate(request, request_id)
            if method == "cancel":
                target = int(request.get("request_id", -1))
                event = self._cancelled.get(target)
                if event is None:
                    return [(RESPONSE, ok(method, request_id=target, cancelled=False, reason="unknown_request"))]
                event.set()
                return [(RESPONSE, ok(method, request_id=target, cancelled=True))]
            if method == "status":
                return [(RESPONSE, ok(method, state=self.state, draining=self.draining,
                                       handles=[{"handle_id": h.handle_id, "model_id": h.model_id,
                                                 "state": h.state, "warmed": h.warmed,
                                                 "backend": h.backend}
                                                for h in self.handles.values()],
                                       requests=self._request_count, effect_authority="none"))]
            if method == "drain":
                self.draining = True
                self.state = "draining"
                return [(RESPONSE, ok(method, state=self.state, accepted_requests=0))]
            if method == "unload":
                handle_id = str(request.get("handle_id", ""))
                handle = self.handles.pop(handle_id, None)
                if handle is not None and handle.provider is not None:
                    handle.provider.stop()
                removed = handle is not None
                return [(RESPONSE, ok(method, handle_id=handle_id, unloaded=removed))]
            if method == "shutdown":
                for event in self._cancelled.values():
                    event.set()
                for handle in self.handles.values():
                    if handle.provider is not None:
                        handle.provider.stop()
                self.state = "stopped"
                return [(RESPONSE, ok(method, state=self.state))]
        return [(ERROR, error(method, "internal_error", "unreachable protocol branch"))]

    def _get_handle(self, request: dict[str, Any]) -> ModelHandle | None:
        handle_id = request.get("handle_id")
        if handle_id is None:
            return next(iter(self.handles.values()), None)
        return self.handles.get(str(handle_id))

    def _generate(self, request: dict[str, Any], request_id: int) -> list[tuple[int, dict[str, Any]]]:
        handle = self._get_handle(request)
        if handle is None:
            return [(ERROR, error("generate", "unknown_handle", "model handle is not loaded"))]
        prompt = str(request.get("prompt", ""))
        max_tokens = int(request.get("max_tokens", 8))
        if max_tokens < 0 or max_tokens > 4096:
            return [(ERROR, error("generate", "invalid_argument", "max_tokens is outside the bounded range"))]
        requested_backend = str(request.get("backend", handle.backend)).strip().lower() or handle.backend
        if requested_backend != handle.backend:
            return [(ERROR, error("generate", "backend_mismatch",
                                  f"handle is loaded with backend {handle.backend!r}"))]
        if handle.backend == "llama-cpp":
            return self._generate_llama(handle, prompt, max_tokens, request, request_id)
        if handle.backend != "fixture":
            return [(ERROR, error("generate", "backend_unavailable",
                                  f"backend {handle.backend!r} has no executable provider"))]
        cancelled = threading.Event()
        self._cancelled[request_id] = cancelled
        receipt_builder = ReceiptBuilder(request_id, requested_backend=str(request.get("backend", "fixture")),
                                         effective_backend="fixture", model=handle.model_id,
                                         profile=str(request.get("profile", "resident")))
        receipt_builder.record_prompt(prompt)
        events: list[tuple[int, dict[str, Any]]] = []
        started = time.monotonic()
        try:
            for index in range(max_tokens):
                if cancelled.is_set() or self.draining:
                    receipt = receipt_builder.finish("cancelled", error_code="cancelled", error_message="generation cancelled")
                    events.append((RESPONSE, error("generate", "cancelled", "generation cancelled", receipt=receipt.as_dict())))
                    break
                token = " " + ("ok" if not prompt else prompt.split()[index % max(1, len(prompt.split()))])
                events.append((EVENT, {"method": "generate", "event": "token", "request_id": request_id,
                                       "index": index, "text": token}))
                time.sleep(0.0005)
            else:
                text = "".join(item[1]["text"] for item in events if item[0] == EVENT)
                receipt_builder.record_output(text)
                receipt_builder.record("tokens.generated", max_tokens, "tokens", "fixture decoder")
                receipt = receipt_builder.finish("completed")
                events.append((RESPONSE, ok("generate", request_id=request_id, handle_id=handle.handle_id,
                                            text=text,
                                            generated_tokens=max_tokens, stop_reason="length",
                                            elapsed_ms=(time.monotonic() - started) * 1000.0,
                                            requested_backend=str(request.get("backend", "fixture")), effective_backend="fixture",
                                            receipt=receipt.as_dict())))
        finally:
            self._cancelled.pop(request_id, None)
        return events

    def _generate_llama(self, handle: ModelHandle, prompt: str, max_tokens: int,
                        request: dict[str, Any], request_id: int) -> list[tuple[int, dict[str, Any]]]:
        assert handle.provider is not None
        cancelled = threading.Event()
        self._cancelled[request_id] = cancelled
        receipt_builder = ReceiptBuilder(request_id, requested_backend="llama-cpp",
                                         effective_backend="llama-cpp", model=handle.model_id,
                                         profile=str(request.get("profile", "resident")))
        receipt_builder.record_prompt(prompt)
        started = time.monotonic()
        try:
            if cancelled.is_set() or self.draining:
                receipt = receipt_builder.finish("cancelled", error_code="cancelled",
                                                error_message="generation cancelled")
                return [(RESPONSE, error("generate", "cancelled", "generation cancelled",
                                          receipt=receipt.as_dict()))]
            result = handle.provider.generate(prompt, max_tokens)
            text = str(result["text"])
            generated_tokens = int(result.get("generated_tokens", 0))
            events = [(EVENT, {"method": "generate", "event": "text", "request_id": request_id,
                               "index": 0, "text": text})]
            receipt_builder.record_output(text)
            receipt_builder.record("tokens.generated", generated_tokens, "tokens", "llama-server usage")
            if result.get("prompt_tokens") is not None:
                receipt_builder.record("tokens.prompt", int(result["prompt_tokens"]), "tokens", "llama-server usage")
            timings = result.get("timings") or {}
            if timings.get("prompt_ms") is not None:
                receipt_builder.record("latency.prompt_ms", float(timings["prompt_ms"]), "milliseconds", "llama-server timings")
            if timings.get("predicted_ms") is not None:
                receipt_builder.record("latency.decode_ms", float(timings["predicted_ms"]), "milliseconds", "llama-server timings")
            receipt = receipt_builder.finish("completed")
            events.append((RESPONSE, ok("generate", request_id=request_id, handle_id=handle.handle_id,
                                        text=text, generated_tokens=generated_tokens,
                                        stop_reason=str(result.get("finish_reason", "stop")),
                                        elapsed_ms=(time.monotonic() - started) * 1000.0,
                                        requested_backend="llama-cpp", effective_backend="llama-cpp",
                                        receipt=receipt.as_dict())))
            return events
        except (OSError, RuntimeError, ValueError) as exc:
            receipt = receipt_builder.finish("failed", error_code="backend_error", error_message=str(exc))
            return [(ERROR, error("generate", "backend_error", str(exc), receipt=receipt.as_dict()))]
        finally:
            self._cancelled.pop(request_id, None)

    def serve(self, input_stream: BinaryIO, output_stream: BinaryIO) -> None:
        """Serve framed requests on stdio until EOF or shutdown."""
        writer_lock = threading.Lock()
        workers: list[threading.Thread] = []

        def write(kind: int, request_id: int, payload: dict[str, Any]) -> None:
            with writer_lock:
                write_frame(output_stream, kind, request_id, payload)

        def run(request_id: int, payload: dict[str, Any]) -> None:
            try:
                for kind, response in self.handle(payload, request_id):
                    write(kind, request_id, response)
            except Exception as exc:  # pragma: no cover - defensive process boundary
                write(ERROR, request_id, error(str(payload.get("method", "unknown")), "internal_error", str(exc)))

        while True:
            try:
                frame = read_frame(input_stream)
            except FrameError as exc:
                write(ERROR, 0, error("unknown", "malformed_frame", str(exc)))
                break
            if frame is None:
                break
            kind, request_id, payload = frame
            if kind != REQUEST:
                write(ERROR, request_id, error("unknown", "invalid_kind", "stdin accepts request frames only"))
                continue
            worker = threading.Thread(target=run, args=(request_id, payload), daemon=True)
            workers.append(worker)
            worker.start()
            if payload.get("method") == "shutdown":
                break
        for worker in workers:
            worker.join(timeout=5.0)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Simplicio Local binary inference daemon")
    parser.add_argument("--home", default=None)
    parser.add_argument("--repo", default=None)
    parser.add_argument("--standalone", action="store_true")
    args = parser.parse_args(argv)
    InferenceDaemon(args.home, standalone=args.standalone, repo_root=args.repo).serve(__import__("sys").stdin.buffer, __import__("sys").stdout.buffer)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
