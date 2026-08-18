"""Clean-install, side-by-side update and rollback primitives."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import tempfile
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass(frozen=True)
class PackageManifest:
    version: str
    protocol_min: int
    protocol_max: int
    platform: str
    architecture: str
    files: dict[str, str]
    license: str
    notice: str
    sbom: str
    provenance: str

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ServicePlan:
    mode: str
    command: tuple[str, ...]
    restart_budget: int
    log_policy: str


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def create_manifest(package_dir: str | os.PathLike[str], *, version: str,
                    protocol_min: int = 2, protocol_max: int = 2,
                    license: str = "LICENSE", notice: str = "NOTICE",
                    sbom: str = "sbom.spdx.json", provenance: str = "provenance.json") -> PackageManifest:
    root = Path(package_dir)
    files: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name == "manifest.json":
            continue
        relative = path.relative_to(root).as_posix()
        if relative.startswith("../") or Path(relative).is_absolute():
            raise ValueError("package file escaped package root")
        files[relative] = _sha256(path)
    return PackageManifest(version, protocol_min, protocol_max, platform.system().lower(),
                           platform.machine().lower(), files, license, notice, sbom, provenance)


class LocalInstaller:
    """Owns only managed installation files; user models/config stay separate."""

    def __init__(self, destination: str | os.PathLike[str], *, user_model_root: str | os.PathLike[str] | None = None):
        self.destination = Path(destination)
        self.versions = self.destination / "versions"
        self.active = self.destination / "active.json"
        self.user_model_root = Path(user_model_root or (self.destination / "models"))
        self.versions.mkdir(parents=True, exist_ok=True)
        self.user_model_root.mkdir(parents=True, exist_ok=True)

    def _load_manifest(self, package: Path) -> PackageManifest:
        data = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
        return PackageManifest(**data)

    def _verify(self, package: Path, manifest: PackageManifest) -> None:
        if manifest.platform != platform.system().lower() or manifest.architecture != platform.machine().lower():
            raise RuntimeError("package target does not match current platform/architecture")
        for relative, expected in manifest.files.items():
            path = package / relative
            if not path.is_file() or _sha256(path) != expected:
                raise RuntimeError(f"package checksum failed: {relative}")
        for name in (manifest.license, manifest.notice, manifest.sbom, manifest.provenance):
            if not (package / name).is_file():
                raise RuntimeError(f"package metadata is missing: {name}")

    def install(self, package_dir: str | os.PathLike[str], *, runtime_protocol: int = 2) -> PackageManifest:
        package = Path(package_dir)
        manifest = self._load_manifest(package)
        if not manifest.protocol_min <= runtime_protocol <= manifest.protocol_max:
            raise RuntimeError("Local/Runtime protocol version is incompatible")
        self._verify(package, manifest)
        target = self.versions / manifest.version
        staging = Path(tempfile.mkdtemp(prefix=f"{manifest.version}.", dir=self.versions))
        try:
            for relative in manifest.files:
                destination = staging / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(package / relative, destination)
            (staging / "manifest.json").write_text(json.dumps(manifest.as_dict(), sort_keys=True) + "\n", encoding="utf-8")
            if target.exists():
                shutil.rmtree(target)
            os.replace(staging, target)
            self._write_active(manifest.version)
        finally:
            if staging.exists():
                shutil.rmtree(staging)
        return manifest

    def _write_active(self, version: str) -> None:
        temporary = self.active.with_suffix(".tmp")
        temporary.write_text(json.dumps({"version": version}) + "\n", encoding="utf-8")
        os.replace(temporary, self.active)

    def active_version(self) -> str | None:
        if not self.active.is_file():
            return None
        return json.loads(self.active.read_text(encoding="utf-8"))["version"]

    def rollback(self) -> str:
        versions = sorted(path.name for path in self.versions.iterdir() if path.is_dir())
        current = self.active_version()
        previous = [version for version in versions if version != current]
        if not previous:
            raise RuntimeError("no previous installed version is available")
        self._write_active(previous[-1])
        return previous[-1]

    def uninstall(self) -> None:
        for version in list(self.versions.iterdir()):
            if version.is_dir():
                shutil.rmtree(version)
        if self.active.exists():
            self.active.unlink()

    def service_plan(self, *, standalone: bool = False, binary: str = "simplicio-local") -> ServicePlan:
        return ServicePlan("standalone" if standalone else "child-process", (binary, "daemon"),
                           restart_budget=3, log_policy="stderr-bounded")
