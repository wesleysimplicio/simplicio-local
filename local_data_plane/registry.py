"""Deterministic backend registry with honest evidence levels."""

from __future__ import annotations

import os
import platform
import shutil
import time
import hashlib
import importlib.util
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
from typing import Iterable

from .llama_cpp import LlamaCppProvider


class EvidenceLevel(IntEnum):
    SOURCE_PRESENT = 1
    LINKED = 2
    FIXTURE_EXECUTED = 3
    REAL_MODEL_EXECUTED = 4
    BENCHMARKED_ON_TARGET = 5

    @property
    def name_value(self) -> str:
        return (
            "source-present",
            "linked",
            "fixture-executed",
            "real-model-executed",
            "benchmarked-on-target",
        )[int(self) - 1]


@dataclass(frozen=True)
class BackendCapability:
    backend: str
    kind: str
    platform: str
    isa: str
    device: str
    evidence_level: EvidenceLevel
    available: bool
    supported: bool
    tested: bool
    preferred: bool
    requested_backend: str | None = None
    effective_backend: str | None = None
    version: str = "unknown"
    build_hash: str = "unknown"
    license: str = "unknown"
    model_families: tuple[str, ...] = ()
    formats: tuple[str, ...] = ()
    methods: tuple[str, ...] = ()
    reason: str | None = None
    artifact_refs: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, object]:
        return {
            "backend": self.backend,
            "kind": self.kind,
            "platform": self.platform,
            "isa": self.isa,
            "device": self.device,
            "evidence_level": self.evidence_level.name_value,
            "available": self.available,
            "supported": self.supported,
            "tested": self.tested,
            "preferred": self.preferred,
            "requested_backend": self.requested_backend,
            "effective_backend": self.effective_backend,
            "version": self.version,
            "build_hash": self.build_hash,
            "license": self.license,
            "model_families": list(self.model_families),
            "formats": list(self.formats),
            "methods": list(self.methods),
            "reason": self.reason,
            "artifact_refs": list(self.artifact_refs),
        }


class BackendRegistry:
    def __init__(self, capabilities: Iterable[BackendCapability] = ()):
        self._items: dict[str, BackendCapability] = {}
        for item in capabilities:
            self.register(item)

    def register(self, capability: BackendCapability) -> None:
        if capability.backend in self._items:
            raise ValueError(f"duplicate backend id: {capability.backend}")
        self._items[capability.backend] = capability

    def get(self, backend: str) -> BackendCapability | None:
        return self._items.get(backend)

    def catalog(self) -> list[dict[str, object]]:
        return [self._items[key].as_dict() for key in sorted(self._items)]

    def release_matrix(self) -> list[dict[str, object]]:
        return [
            {
                "platform": item["platform"],
                "backend": item["backend"],
                "evidence_level": item["evidence_level"],
                "available": item["available"],
                "reason": item["reason"],
            }
            for item in self.catalog()
        ]

    def runtime_discovery(self, *, model_id: str = "unresolved-model") -> list[dict[str, object]]:
        """Expose the Runtime v2 discovery shape without inventing capability evidence."""

        now_ms = int(time.time() * 1000)
        build_hash = hashlib.sha256(b"simplicio-local-python-data-plane").hexdigest()
        discoveries: list[dict[str, object]] = []
        for item in self._items.values():
            if item.available:
                state = "ready"
                evidence = "measured" if item.evidence_level >= EvidenceLevel.FIXTURE_EXECUTED else "probed"
                unavailable_reason = None
            elif item.supported:
                state = "degraded"
                evidence = "advertised"
                unavailable_reason = item.reason or "backend is not executable on this host"
            else:
                state = "absent"
                evidence = "unknown"
                unavailable_reason = item.reason or "backend is not present"
            backend_hash = hashlib.sha256(item.backend.encode()).hexdigest()
            model_hash = hashlib.sha256(model_id.encode()).hexdigest()
            devices = {item.device if item.device in {"cpu", "metal", "mlx", "cuda", "vulkan", "npu"} else "auto"}
            storage_modes = {"resident", "auto"}
            if "gguf" in item.formats:
                storage_modes.add("mmap")
            discoveries.append({
                "schema": "simplicio.inference-backend/v2",
                "state": state,
                "identity": {
                    "protocol_min": 2,
                    "protocol_max": 2,
                    "daemon_version": "python-data-plane",
                    "build_commit": "unknown",
                    "build_hash": build_hash,
                    "license": item.license,
                    "backend": {"id": item.backend, "revision": item.version,
                                "sha256": backend_hash, "architecture": item.isa},
                    "model": {"id": model_id, "revision": "unresolved",
                              "sha256": model_hash, "architecture": item.isa},
                    "tokenizer_hash": "unknown",
                    "chat_template_hash": "unknown",
                    "requested_backend": item.backend,
                    "effective_backend": item.effective_backend or item.backend,
                    "requested_model": model_id,
                    "effective_model": model_id,
                    "requested_device": next(iter(devices)),
                    "effective_device": next(iter(devices)),
                    "profile_hash": hashlib.sha256(b"compatibility").hexdigest(),
                },
                "capabilities": {
                    "lifecycle_methods": sorted(set(item.methods) | {"handshake", "capabilities", "estimate"}),
                    "formats": sorted(item.formats),
                    "model_families": sorted(item.model_families),
                    "streaming": "generate" in item.methods,
                    "grammar": False,
                    "embeddings": False,
                    "vision": False,
                    "kv_codecs": [],
                    "recurrent_codecs": [],
                    "mtp_codecs": [],
                    "storage_modes": sorted(storage_modes),
                    "devices": sorted(devices),
                    "evidence_level": evidence,
                    "unavailable_reason": unavailable_reason,
                },
                "estimate": None,
                "generated_at_unix_ms": now_ms,
                "extensions": {"local_evidence_level": item.evidence_level.name_value,
                               "kind": item.kind, "preferred": item.preferred},
            })
        return sorted(discoveries, key=lambda value: value["identity"]["effective_backend"])

    @classmethod
    def default(cls, repo_root: str | os.PathLike[str] | None = None) -> "BackendRegistry":
        root = Path(repo_root or Path.cwd())
        current_platform = platform.system().lower()
        current_isa = platform.machine().lower()
        apple = current_platform == "darwin"

        def source_capability(
            backend: str,
            markers: tuple[str, ...],
            *,
            kind: str = "engine",
            formats: tuple[str, ...] = (),
            families: tuple[str, ...] = (),
            reason: str | None = None,
        ) -> BackendCapability:
            found = tuple(str(root / marker) for marker in markers if (root / marker).exists())
            level = EvidenceLevel.SOURCE_PRESENT if found else EvidenceLevel.SOURCE_PRESENT
            return BackendCapability(
                backend=backend,
                kind=kind,
                platform=current_platform,
                isa=current_isa,
                device="apple-silicon" if apple else "cpu",
                evidence_level=level,
                available=False,
                supported=bool(found),
                tested=False,
                preferred=False,
                formats=formats,
                model_families=families,
                methods=("load", "warm", "generate", "cancel"),
                reason=reason or ("source present; executable probe not run" if found else "source not found"),
                artifact_refs=found,
            )

        items = [
            BackendCapability(
                backend="fixture", kind="engine", platform=current_platform, isa=current_isa,
                device="cpu", evidence_level=EvidenceLevel.FIXTURE_EXECUTED,
                available=True, supported=True, tested=True, preferred=False,
                formats=("fixture",), methods=("handshake", "load", "warm", "generate", "cancel"),
                reason="bounded deterministic fixture", artifact_refs=("tests/local_data_plane/test_daemon.py",),
            ),
            source_capability("llama-cpp", ("runtime/adapters/llama", "docs/protocols"),
                              formats=("gguf",), families=("llama", "qwen", "gemma")),
            source_capability("mlx-lm", ("runtime/mlx", "scripts/openai_serve.py"),
                              formats=("safetensors",), families=("qwen", "llama"),
                              reason="source present; MLX is unavailable on this host" if not apple else None),
            source_capability("mlx-native", ("runtime/mlx/native_mlx_backend.cpp",),
                              formats=("safetensors",), families=("qwen", "llama")),
            source_capability("metal-native", ("runtime/metal",), formats=("gguf", "safetensors")),
            source_capability("colibri", ("engine/c", "runtime/moe"),
                              formats=("safetensors",), families=("deepseek", "glm", "kimi")),
            source_capability("litert-lm", ("runtime",), kind="adapter", reason="LiteRT provider is not linked in this build"),
            source_capability("dense-stream", ("runtime/dense/layer_stream.cpp",),
                              formats=("stream-container",), reason="experimental source path; real-model probe required"),
            BackendCapability(
                backend="ollama-proxy", kind="proxy", platform=current_platform, isa=current_isa,
                device="external", evidence_level=EvidenceLevel.LINKED,
                available=bool(os.environ.get("OLLAMA_HOST")), supported=True, tested=False, preferred=False,
                methods=("generate",), reason="external proxy; never an engine capability",
            ),
            BackendCapability(
                backend="custom-openai", kind="proxy", platform=current_platform, isa=current_isa,
                device="external", evidence_level=EvidenceLevel.LINKED,
                available=bool(os.environ.get("SIMPLICIO_LOCAL_OPENAI_URL")), supported=True, tested=False,
                preferred=False, methods=("generate",), reason="external adapter; never an engine capability",
            ),
            BackendCapability(
                backend="turboquant-kv", kind="cache-codec", platform=current_platform, isa=current_isa,
                device="cpu", evidence_level=EvidenceLevel.FIXTURE_EXECUTED,
                available=importlib.util.find_spec("numpy") is not None,
                supported=True, tested=importlib.util.find_spec("numpy") is not None, preferred=False,
                formats=("kv-cache", "fp32"), methods=("turboquant_compress", "turboquant_decompress"),
                reason=("CPU NumPy reference executor" if importlib.util.find_spec("numpy") is not None
                        else "NumPy is not installed"),
            ),
        ]

        turbo_probe = LlamaCppProvider(turboquant=True).probe(turboquant=True)
        items.append(BackendCapability(
            backend="llama-cpp-turboquant", kind="engine", platform=current_platform, isa=current_isa,
            device="vulkan" if current_platform == "linux" else ("metal" if apple else "cpu"),
            evidence_level=(EvidenceLevel.LINKED if turbo_probe.linked else EvidenceLevel.SOURCE_PRESENT),
            available=turbo_probe.turboquant,
            supported=turbo_probe.linked,
            tested=False,
            preferred=False,
            version=turbo_probe.version or "unknown",
            formats=("gguf",), model_families=("llama", "qwen", "gemma"),
            methods=("load", "warm", "generate", "cancel"),
            reason=turbo_probe.reason,
            artifact_refs=((turbo_probe.executable,) if turbo_probe.executable else ()),
        ))

        llama_server = shutil.which("llama-server")
        if llama_server:
            items[1] = BackendCapability(**{**items[1].__dict__, "evidence_level": EvidenceLevel.LINKED,
                                            "available": True, "reason": "llama-server executable discovered",
                                            "artifact_refs": (llama_server,)})
        return cls(items)
