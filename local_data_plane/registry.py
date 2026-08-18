"""Deterministic backend registry with honest evidence levels."""

from __future__ import annotations

import os
import platform
import shutil
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
from typing import Iterable


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
        ]

        llama_server = shutil.which("llama-server")
        if llama_server:
            items[1] = BackendCapability(**{**items[1].__dict__, "evidence_level": EvidenceLevel.LINKED,
                                            "available": True, "reason": "llama-server executable discovered",
                                            "artifact_refs": (llama_server,)})
        return cls(items)
