"""Versioned, provenance-labelled hardware topology detection."""

from __future__ import annotations

import hashlib
import json
import os
import platform
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Mapping


HARDWARE_TOPOLOGY_SCHEMA_V1 = "simplicio-local.hardware-topology/v1"


@dataclass(frozen=True)
class CacheInfo:
    level: int
    kind: str
    size_bytes: int | None
    shared_cpu_list: str | None


@dataclass(frozen=True)
class HardwareTopology:
    schema: str
    platform: str
    architecture: str
    logical_cpus: int | None
    physical_cpus: int | None
    caches: tuple[CacheInfo, ...]
    cache_line_bytes: int | None
    isa_features: tuple[str, ...]
    numa_nodes: int | None
    system_memory_bytes: int | None
    available_memory_bytes: int | None
    core_classes: tuple[str, ...]
    gpu: Mapping[str, Any]
    unavailable: Mapping[str, str]
    fingerprint: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _stable_fingerprint(payload: Mapping[str, Any]) -> str:
    clone = dict(payload)
    clone.pop("fingerprint", None)
    clone.pop("unavailable", None)
    encoded = json.dumps(clone, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _parse_size(value: str) -> int | None:
    value = value.strip().upper()
    if not value:
        return None
    multipliers = {"B": 1, "K": 1024, "KB": 1024, "M": 1024 ** 2, "MB": 1024 ** 2,
                   "G": 1024 ** 3, "GB": 1024 ** 3}
    for suffix, multiplier in sorted(multipliers.items(), key=lambda item: -len(item[0])):
        if value.endswith(suffix):
            try:
                return int(float(value[:-len(suffix)].strip()) * multiplier)
            except ValueError:
                return None
    try:
        return int(value)
    except ValueError:
        return None


def topology_from_payload(payload: Mapping[str, Any]) -> HardwareTopology:
    if payload.get("schema") != HARDWARE_TOPOLOGY_SCHEMA_V1:
        raise ValueError(f"schema must be {HARDWARE_TOPOLOGY_SCHEMA_V1}")
    caches = tuple(CacheInfo(int(item["level"]), str(item["kind"]), item.get("size_bytes"), item.get("shared_cpu_list"))
                   for item in payload.get("caches", ()))
    base = {"schema": HARDWARE_TOPOLOGY_SCHEMA_V1, "platform": str(payload.get("platform", "unknown")),
            "architecture": str(payload.get("architecture", "unknown")), "logical_cpus": payload.get("logical_cpus"),
            "physical_cpus": payload.get("physical_cpus"), "caches": [asdict(cache) for cache in caches],
            "cache_line_bytes": payload.get("cache_line_bytes"), "isa_features": sorted(payload.get("isa_features", ())),
            "numa_nodes": payload.get("numa_nodes"), "system_memory_bytes": payload.get("system_memory_bytes"),
            "available_memory_bytes": payload.get("available_memory_bytes"), "core_classes": sorted(payload.get("core_classes", ())),
            "gpu": dict(payload.get("gpu", {})), "unavailable": dict(payload.get("unavailable", {}))}
    expected = _stable_fingerprint(base)
    fingerprint = str(payload.get("fingerprint", expected))
    if fingerprint != expected:
        raise ValueError("hardware topology fingerprint does not match payload")
    return HardwareTopology(fingerprint=fingerprint, caches=caches,
                            isa_features=tuple(base["isa_features"]),
                            core_classes=tuple(base["core_classes"]),
                            **{key: value for key, value in base.items()
                               if key not in {"caches", "isa_features", "core_classes"}})


def detect_hardware_topology(*, sys_root: str | os.PathLike[str] = "/sys",
                             proc_root: str | os.PathLike[str] = "/proc") -> HardwareTopology:
    sys_path, proc_path = Path(sys_root), Path(proc_root)
    unavailable: dict[str, str] = {}
    caches: list[CacheInfo] = []
    cache_root = sys_path / "devices/system/cpu/cpu0/cache"
    if cache_root.is_dir():
        for index in sorted(cache_root.glob("index*")):
            level = _read_int(index / "level")
            kind = _read(index / "type")
            size = _parse_size(_read(index / "size") or "")
            if level is not None:
                caches.append(CacheInfo(level, kind or "unknown", size, _read(index / "shared_cpu_list")))
    else:
        unavailable["caches"] = "sysfs cache topology is unavailable"
    cpuinfo = _read(proc_path / "cpuinfo") or ""
    flags: set[str] = set()
    for line in cpuinfo.splitlines():
        if line.lower().startswith(("flags", "features")) and ":" in line:
            flags.update(line.split(":", 1)[1].strip().split())
            break
    if not flags:
        unavailable["isa_features"] = "kernel did not expose /proc/cpuinfo flags"
    logical = os.cpu_count()
    physical = None
    core_ids = {(line.split(":", 1)[1].strip()) for line in cpuinfo.splitlines()
                if line.lower().startswith("core id") and ":" in line}
    if core_ids:
        physical = len(core_ids)
    else:
        unavailable["physical_cpus"] = "physical topology was not exposed"
    system_memory = None
    available_memory = None
    meminfo = _read(proc_path / "meminfo") or ""
    for line in meminfo.splitlines():
        if line.startswith("MemTotal:"):
            system_memory = _parse_size(line.split(":", 1)[1].strip().replace(" kB", " KB"))
        elif line.startswith("MemAvailable:"):
            available_memory = _parse_size(line.split(":", 1)[1].strip().replace(" kB", " KB"))
    if system_memory is None:
        unavailable["system_memory_bytes"] = "host memory was not exposed by procfs"
    numa_root = sys_path / "devices/system/node"
    numa_nodes = len(list(numa_root.glob("node*"))) if numa_root.is_dir() else None
    if numa_nodes is None:
        unavailable["numa_nodes"] = "NUMA topology is unavailable"
    base = {"schema": HARDWARE_TOPOLOGY_SCHEMA_V1, "platform": platform.system().lower(),
            "architecture": platform.machine().lower(), "logical_cpus": logical, "physical_cpus": physical,
            "caches": [asdict(cache) for cache in caches], "cache_line_bytes": None,
            "isa_features": sorted(flags), "numa_nodes": numa_nodes, "system_memory_bytes": system_memory,
            "available_memory_bytes": available_memory, "core_classes": [], "gpu": {}, "unavailable": unavailable}
    if base["cache_line_bytes"] is None:
        unavailable["cache_line_bytes"] = "cache line size was not exposed by the portable probe"
    if not base["gpu"]:
        unavailable["gpu"] = "GPU topology requires a backend-specific probe"
    base["fingerprint"] = _stable_fingerprint(base)
    return topology_from_payload(base)


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return None


def _read_int(path: Path) -> int | None:
    value = _read(path)
    try:
        return int(value) if value is not None else None
    except ValueError:
        return None
