"""Managed installation and discovery for Atomic's TurboQuant llama-server.

Atomic Agent's production path is a patched llama.cpp server, not the Python
reference codec.  This module keeps that binary optional and auditable: it
selects an allow-listed release asset, extracts it into a versioned directory,
and writes a receipt that the provider can discover later. The selected tag and
asset come from Atomic Chat's platform manifest, avoiding a mutable GitHub
release scan and keeping the exact release in the install receipt.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import stat
import tempfile
import tarfile
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.request import Request, urlopen


ATOMIC_REPO = "AtomicBot-ai/atomic-llama-cpp-turboquant"
ATOMIC_CONFIG_MANIFEST = "https://raw.githubusercontent.com/AtomicBot-ai/atomic-chat-conf/main/backends/turboquant-manifest.json"
RELEASE_DOWNLOAD_BASE = f"https://github.com/{ATOMIC_REPO}/releases/download"
INSTALL_SCHEMA = "simplicio.local.turboquant-backend-install/v1"
MAX_ARCHIVE_BYTES = 2 * 1024 * 1024 * 1024


def _machine_name(value: str | None = None) -> str:
    machine = (value or platform.machine()).lower()
    return {
        "amd64": "x86_64",
        "x64": "x86_64",
        "aarch64": "arm64",
    }.get(machine, machine)


def platform_asset(system: str | None = None, machine: str | None = None) -> str | None:
    """Return the platform id used by Atomic's pinned backend manifest."""

    current_system = (system or platform.system()).lower()
    current_machine = _machine_name(machine)
    return {
        ("darwin", "arm64"): "macos-arm64",
        ("linux", "x86_64"): "linux-x64-vulkan",
        ("windows", "x86_64"): "windows-x64-vulkan",
    }.get((current_system, current_machine))


@dataclass(frozen=True)
class TurboQuantRelease:
    tag: str
    asset: str
    download_url: str
    size_bytes: int | None = None


def _safe_name(value: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in "-_." else "_" for char in value)
    if not cleaned or cleaned in {".", ".."}:
        raise ValueError("release tag is not a safe directory name")
    return cleaned


def _safe_member(root: Path, name: str) -> Path:
    target = (root / name).resolve()
    resolved_root = root.resolve()
    if target != resolved_root and resolved_root not in target.parents:
        raise ValueError(f"archive member escapes extraction root: {name!r}")
    return target


def _safe_link(root: Path, link: Path, destination: str) -> None:
    resolved_root = root.resolve()
    resolved_target = (link.parent / destination).resolve()
    if resolved_target != resolved_root and resolved_root not in resolved_target.parents:
        raise ValueError(f"archive link escapes extraction root: {destination!r}")


class TurboQuantBackendInstaller:
    """Install the allow-listed Atomic llama-server release for this host."""

    def __init__(self, home: str | os.PathLike[str] | None = None,
                 *, system: str | None = None, machine: str | None = None,
                 opener: Callable[..., Any] = urlopen):
        self.home = Path(home or os.environ.get("SIMPLICIO_LOCAL_HOME", ".simplicio-local"))
        self.system = (system or platform.system()).lower()
        self.machine = _machine_name(machine)
        self.opener = opener

    @property
    def asset_name(self) -> str:
        platform_id = platform_asset(self.system, self.machine)
        if platform_id is None:
            raise RuntimeError(f"Atomic TurboQuant has no managed asset for {self.system}/{self.machine}")
        return platform_id

    @property
    def backend_root(self) -> Path:
        return self.home / "backends" / "atomic-llama-cpp-turboquant"

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "simplicio-local"}
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def _json(self, url: str) -> Any:
        request = Request(url, headers=self._headers())
        with self.opener(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))

    def discover_release(self) -> TurboQuantRelease:
        payload = self._json(ATOMIC_CONFIG_MANIFEST)
        if not isinstance(payload, dict) or not isinstance(payload.get("backends"), list):
            raise RuntimeError("Atomic TurboQuant manifest returned an invalid payload")
        wanted = self.asset_name
        for entry in payload["backends"]:
            if not isinstance(entry, dict) or entry.get("id") != wanted:
                continue
            tag = entry.get("tag")
            asset = entry.get("asset")
            if not isinstance(tag, str) or not isinstance(asset, str) or not tag or not asset:
                raise RuntimeError("Atomic TurboQuant manifest entry is incomplete")
            if not asset.startswith("llama-turboquant-") or not asset.endswith((".zip", ".tar.gz")):
                raise RuntimeError("Atomic TurboQuant manifest contains an unsafe asset name")
            url = f"{RELEASE_DOWNLOAD_BASE}/{tag}/{asset}"
            return TurboQuantRelease(tag, asset, url)
        raise RuntimeError(f"Atomic TurboQuant manifest has no backend for {wanted}")

    def _download(self, release: TurboQuantRelease, destination: Path) -> str:
        request = Request(release.download_url, headers=self._headers())
        digest = hashlib.sha256()
        total = 0
        with self.opener(request, timeout=60) as response, destination.open("wb") as output:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_ARCHIVE_BYTES:
                    raise RuntimeError("Atomic backend archive exceeds the safe download limit")
                digest.update(chunk)
                output.write(chunk)
        if release.size_bytes is not None and total != release.size_bytes:
            raise RuntimeError("downloaded Atomic backend size differs from GitHub metadata")
        return digest.hexdigest()

    def _extract(self, archive: Path, destination: Path) -> Path:
        destination.mkdir(parents=True, exist_ok=True)
        if archive.name.endswith(".zip"):
            with zipfile.ZipFile(archive) as bundle:
                for member in bundle.infolist():
                    target = _safe_member(destination, member.filename)
                    if member.is_dir():
                        target.mkdir(parents=True, exist_ok=True)
                        continue
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with bundle.open(member) as source, target.open("wb") as output:
                        shutil.copyfileobj(source, output)
                    mode = member.external_attr >> 16
                    if mode:
                        target.chmod(stat.S_IMODE(mode))
        elif archive.name.endswith(".tar.gz"):
            with tarfile.open(archive, "r:gz") as bundle:
                for member in bundle.getmembers():
                    target = _safe_member(destination, member.name)
                    if member.isdir():
                        target.mkdir(parents=True, exist_ok=True)
                        continue
                    if not member.isfile():
                        if member.issym():
                            _safe_link(destination, target, member.linkname)
                            target.parent.mkdir(parents=True, exist_ok=True)
                            target.unlink(missing_ok=True)
                            os.symlink(member.linkname, target)
                            continue
                        raise RuntimeError(f"archive contains unsupported tar member: {member.name!r}")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    source = bundle.extractfile(member)
                    if source is None:
                        raise RuntimeError(f"unable to read tar member: {member.name!r}")
                    with source, target.open("wb") as output:
                        shutil.copyfileobj(source, output)
                    target.chmod(stat.S_IMODE(member.mode))
        else:
            raise RuntimeError(f"unsupported Atomic backend archive: {archive.name}")
        candidates = [path for path in destination.rglob("llama-server*") if path.is_file()]
        if not candidates:
            raise RuntimeError("Atomic archive does not contain llama-server")
        candidates.sort(key=lambda path: (path.name != "llama-server", len(path.parts)))
        executable = candidates[0]
        if self.system != "windows":
            executable.chmod(executable.stat().st_mode | stat.S_IXUSR)
        return executable

    def install(self) -> dict[str, object]:
        release = self.discover_release()
        tag_dir = self.backend_root / _safe_name(release.tag)
        receipt_path = tag_dir / "install-receipt.json"
        if receipt_path.is_file():
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            executable = Path(str(receipt.get("executable", "")))
            if executable.is_file() and receipt.get("asset") == release.asset:
                self._write_current(receipt)
                return receipt

        self.backend_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".atomic-turboquant-", dir=self.backend_root) as staging_name:
            staging = Path(staging_name)
            archive = staging / release.asset
            archive_sha256 = self._download(release, archive)
            extracted = staging / "extracted"
            executable = self._extract(archive, extracted)
            if tag_dir.exists():
                raise RuntimeError(f"managed Atomic release directory is incomplete: {tag_dir}")
            shutil.move(str(extracted), str(tag_dir))
        installed_executable = tag_dir / executable.relative_to(staging / "extracted")
        receipt = {
            "schema": INSTALL_SCHEMA,
            "repository": ATOMIC_REPO,
            "tag": release.tag,
            "asset": release.asset,
            "download_url": release.download_url,
            "archive_sha256": archive_sha256,
            "executable": str(installed_executable),
            "installed_at_unix_ms": int(time.time() * 1000),
        }
        receipt_path = tag_dir / "install-receipt.json"
        receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        self._write_current(receipt)
        return receipt

    def _write_current(self, receipt: dict[str, object]) -> None:
        current = self.backend_root / "current.json"
        temporary = current.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temporary, current)


def discover_installed_executable(home: str | os.PathLike[str] | None = None) -> str | None:
    """Return the verified path recorded by the managed installer, if any."""

    root = Path(home or os.environ.get("SIMPLICIO_LOCAL_HOME", ".simplicio-local"))
    receipt_path = root / "backends" / "atomic-llama-cpp-turboquant" / "current.json"
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        executable = Path(str(receipt["executable"]))
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None
    return str(executable) if executable.is_file() else None
