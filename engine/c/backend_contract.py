#!/usr/bin/env python3
"""Governed, load-free integration contract for Simplicio local inference."""

from dataclasses import dataclass, field
import hashlib
import json
import os
import platform
from pathlib import Path
import shutil
import tempfile
import tarfile
import time
import urllib.parse
import urllib.request
import uuid
import zipfile


PROTOCOL = "simplicio.local-inference-backend/v1"
GB = 1_000_000_000
DEEP_WORKLOADS = frozenset(("background", "batch", "deep-offline"))
STATES = frozenset((
    "cold", "loading", "warming", "ready", "degraded", "draining",
    "stopped", "blocked",
))
TRANSITIONS = {
    "cold": {"loading", "blocked", "stopped"},
    "loading": {"warming", "degraded", "draining", "blocked"},
    "warming": {"ready", "degraded", "draining", "blocked"},
    "ready": {"degraded", "draining", "blocked"},
    "degraded": {"ready", "draining", "blocked"},
    "draining": {"stopped", "blocked"},
    "stopped": {"loading"},
    "blocked": {"cold", "stopped"},
}


def _source_status(path, host_supported):
    if not Path(path).is_file():
        return "planned"
    return "implemented" if host_supported else "implemented-unverified-on-host"


def capability_probe(repo_root=None, model=None):
    """Return capabilities without starting an engine or reading model payloads."""
    root = Path(repo_root or Path(__file__).resolve().parents[2])
    machine = platform.machine().lower()
    system = platform.system().lower()
    model_path = Path(model).expanduser().resolve() if model else None
    identity = {
        "backend": "simplicio-local-any-llm-16gb",
        "protocol": PROTOCOL,
        "engine": "colibri-c-vendored",
        "build_commit": os.environ.get("SIMPLICIO_LOCAL_COMMIT"),
        "requested_model": str(model_path) if model_path else None,
        "effective_model": None,
    }
    return {
        "protocol": PROTOCOL,
        "identity": identity,
        "state": "cold",
        "read_only": True,
        "model_payload_read": False,
        "capabilities": {
            "dense": "implemented",
            "moe": "implemented",
            "cpu": "implemented",
            "neon": _source_status(root / "runtime/neon/neon_matmul.cpp",
                                   machine in ("arm64", "aarch64")),
            "metal": _source_status(root / "runtime/metal/kernels/matmul.metal",
                                    system == "darwin" and machine == "arm64"),
            "mlx": _source_status(root / "runtime/mlx/mlx_bridge.cpp",
                                  system == "darwin" and machine == "arm64"),
            "streaming_sse": "implemented",
            "expert_streaming": "implemented",
            "layer_streaming": "experimental",
            "cancellation": "implemented",
            "deterministic_seed": "implemented",
            "tool_candidates": "planned-no-execution-authority",
            "tool_execution": "forbidden",
        },
        "routing": {
            "default_workloads": sorted(DEEP_WORKLOADS),
            "interactive": "deny-unless-explicit-runtime-policy",
        },
    }


def admission_estimate(*, model_bytes, dense_bytes, available_memory,
                       available_disk, hard_rss_limit, workload,
                       runtime_bytes=int(3.7 * GB), cache_bytes=0,
                       explicit_interactive=False):
    values = (model_bytes, dense_bytes, available_memory, available_disk,
              hard_rss_limit, runtime_bytes, cache_bytes)
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0
           for value in values):
        raise ValueError("resource values must be non-negative integers")
    if workload not in DEEP_WORKLOADS and workload != "interactive":
        raise ValueError("invalid workload class")
    projected_rss = dense_bytes + runtime_bytes + cache_bytes
    reasons = []
    if workload == "interactive" and not explicit_interactive:
        reasons.append("interactive-requires-explicit-runtime-policy")
    if projected_rss > hard_rss_limit:
        reasons.append("projected-rss-exceeds-hard-limit")
    if projected_rss > available_memory:
        reasons.append("projected-rss-exceeds-available-memory")
    if model_bytes > available_disk:
        reasons.append("insufficient-model-storage")
    return {
        "protocol": PROTOCOL,
        "decision": "deny" if reasons else "admit",
        "workload": workload,
        "reasons": reasons,
        "estimate": {
            "model_bytes": model_bytes,
            "projected_peak_rss_bytes": projected_rss,
            "available_memory_bytes": available_memory,
            "hard_rss_limit_bytes": hard_rss_limit,
            "available_disk_bytes": available_disk,
            "cold_start_seconds": None,
            "tokens_per_second": None,
            "unobserved_reason": "requires a measured model/hardware run",
        },
    }


@dataclass
class Lease:
    lease_id: str
    model: str
    profile: str
    fence: int
    state: str = "cold"
    idempotency_keys: set = field(default_factory=set)

    def transition(self, target):
        if target not in STATES:
            raise ValueError("invalid lifecycle state")
        if target not in TRANSITIONS[self.state]:
            raise ValueError(f"invalid lifecycle transition: {self.state}->{target}")
        self.state = target


class LeaseRegistry:
    """Reference single-flight registry. Runtime remains the authority/owner."""

    def __init__(self):
        self._leases = {}
        self._fence = 0

    def acquire(self, lease_id, model, profile):
        if not all(isinstance(value, str) and value.strip()
                   for value in (lease_id, model, profile)):
            raise ValueError("lease_id, model and profile are required")
        key = (model, profile)
        current = self._leases.get(key)
        if current and current.state not in ("stopped", "blocked"):
            if current.lease_id == lease_id:
                return current
            raise RuntimeError("model-profile-already-leased")
        self._fence += 1
        lease = Lease(lease_id, model, profile, self._fence)
        self._leases[key] = lease
        return lease

    def release(self, lease):
        lease.state = "stopped"


def build_receipt(lease, request_id, requested_model, effective_model,
                  status, output=b"", metrics=None, failure_reason=None):
    if status not in ("completed", "cancelled", "timeout", "failed"):
        raise ValueError("invalid receipt status")
    if not request_id:
        raise ValueError("request_id is required")
    metrics = dict(metrics or {})
    allowed_metrics = {
        "peak_rss_bytes", "swap_bytes", "read_bytes", "cache_hit_ratio",
        "ttft_ms", "tokens_per_second",
    }
    metrics = {name: metrics.get(name) for name in sorted(allowed_metrics)}
    return {
        "protocol": PROTOCOL,
        "request_id": request_id,
        "lease": {"id": lease.lease_id, "fence": lease.fence},
        "requested_model": requested_model,
        "effective_model": effective_model,
        "status": status,
        "failure_reason": failure_reason,
        "output_sha256": hashlib.sha256(output).hexdigest(),
        "metrics": metrics,
        "created_unix_ms": int(time.time() * 1000),
        "effect_authority": "none",
    }


def host_resources(path="."):
    memory = 0
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemAvailable:"):
                memory = int(line.split()[1]) * 1024
                break
    except OSError:
        pass
    return memory, shutil.disk_usage(path).free


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))

LITERT_MANIFEST_SCHEMA = "simplicio.local-litert-package/v1"
LITERT_INSTALL_PLAN_SCHEMA = "simplicio.local-litert-install-plan/v1"
LITERT_RECEIPT_SCHEMA = "simplicio.local-litert-install-receipt/v1"

_DEFAULT_LITERT_MANIFEST = {
    "schema": LITERT_MANIFEST_SCHEMA,
    "package": "litert-lm",
    "version": "0.11.0",
    "license": "Apache-2.0",
    "components": {
        "litert_lm": "0.11.0",
        "litert": "2.0.2",
    },
    "artifacts": {
        "linux-x86_64": {
            "name": "litert_lm_main.linux_x86_64",
            "source": "https://github.com/google-ai-edge/LiteRT-LM/releases/download/v0.11.0/litert_lm_main.linux_x86_64",
            "size_bytes": 29179864,
            "sha256": "8c50507ce5c7a1b52b2d1e9eba8ed2c878f0f12797febc693c44ee3216ab2359",
            "executable": True,
        },
        "darwin-arm64": {
            "name": "litert_lm_main.macos_arm64",
            "source": "https://github.com/google-ai-edge/LiteRT-LM/releases/download/v0.11.0/litert_lm_main.macos_arm64",
            "size_bytes": 19786096,
            "sha256": "6dc8134ae70b6c88a2611480c0bfcbd9d11c24528f81db4cfa2fbaa538f7966c",
            "executable": True,
        },
        "windows-x86_64": {
            "name": "litert_lm_main.windows_x86_64.exe",
            "source": "https://github.com/google-ai-edge/LiteRT-LM/releases/download/v0.11.0/litert_lm_main.windows_x86_64.exe",
            "size_bytes": 18072064,
            "sha256": "326da962fede2a98c5a66c6f32bcaff69c479dff36dd53f2cbe9a00a5978d8d1",
            "executable": True,
        },
    },
}


def _sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _litert_platform():
    system = platform.system().lower()
    machine = platform.machine().lower()
    if system == "darwin" and machine in ("arm64", "aarch64"):
        return "darwin-arm64"
    if system == "linux" and machine in ("x86_64", "amd64"):
        return "linux-x86_64"
    if system == "windows" and machine in ("x86_64", "amd64"):
        return "windows-x86_64"
    raise ValueError(f"unsupported LiteRT-LM host platform: {system}-{machine}")


def _default_litert_cache():
    override = os.environ.get("SIMPLICIO_LITERT_CACHE")
    if override:
        return Path(override).expanduser()
    if os.name == "nt":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home()))
    else:
        root = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return root / "simplicio" / "litert-lm"


def _load_litert_manifest(path=None):
    if path:
        manifest = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    else:
        manifest = json.loads(json.dumps(_DEFAULT_LITERT_MANIFEST))
    if manifest.get("schema") != LITERT_MANIFEST_SCHEMA:
        raise ValueError(f"unsupported LiteRT package manifest schema: {manifest.get('schema')!r}")
    for key in ("package", "version", "license", "components", "artifacts"):
        if not manifest.get(key):
            raise ValueError(f"LiteRT package manifest missing {key}")
    if not isinstance(manifest["components"], dict):
        raise ValueError("LiteRT package manifest components must be an object")
    if not isinstance(manifest["artifacts"], dict):
        raise ValueError("LiteRT package manifest artifacts must be an object")
    for key, artifact in manifest["artifacts"].items():
        if not isinstance(artifact, dict):
            raise ValueError(f"LiteRT artifact {key} must be an object")
        name = str(artifact.get("name", ""))
        digest = str(artifact.get("sha256", ""))
        size = artifact.get("size_bytes")
        if not name or "/" in name or "\\" in name or name in (".", ".."):
            raise ValueError(f"unsafe LiteRT artifact name for {key}")
        if not isinstance(size, int) or size < 0:
            raise ValueError(f"invalid LiteRT artifact size for {key}")
        if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest.lower()):
            raise ValueError(f"invalid LiteRT artifact SHA-256 for {key}")
        if not isinstance(artifact.get("source"), str) or not artifact["source"].strip():
            raise ValueError(f"missing LiteRT artifact source for {key}")
    return manifest


def _cache_outside_checkout(cache_dir, repo_root):
    cache = Path(cache_dir).expanduser().resolve()
    root = Path(repo_root or Path.cwd()).resolve()
    if cache == root or root in cache.parents:
        raise ValueError("LiteRT cache must be outside the checkout")
    if cache.exists() and cache.is_symlink():
        raise ValueError("LiteRT cache cannot be a symlink")
    return cache


def build_litert_install_plan(*, repo_root=None, manifest_path=None,
                              cache_dir=None, platform_key=None,
                              artifact_path=None):
    manifest = _load_litert_manifest(manifest_path)
    selected_platform = platform_key or _litert_platform()
    try:
        artifact = dict(manifest["artifacts"][selected_platform])
    except KeyError as error:
        raise ValueError(f"LiteRT package has no artifact for {selected_platform}") from error
    source = str(Path(artifact_path).expanduser().resolve()) if artifact_path else artifact["source"]
    source_kind = "local" if artifact_path else "remote"
    cache = _cache_outside_checkout(cache_dir or _default_litert_cache(), repo_root)
    destination = cache / manifest["package"] / manifest["version"] / selected_platform / artifact["name"]
    return {
        "schema": LITERT_INSTALL_PLAN_SCHEMA,
        "package": manifest["package"],
        "version": manifest["version"],
        "platform": selected_platform,
        "license": manifest["license"],
        "components": manifest["components"],
        "artifact": {
            "name": artifact["name"],
            "size_bytes": artifact["size_bytes"],
            "sha256": artifact["sha256"],
            "source": source,
            "source_kind": source_kind,
            "executable": bool(artifact.get("executable", False)),
        },
        "manifest_sha256": hashlib.sha256(canonical_json(manifest).encode()).hexdigest(),
        "cache_dir": str(cache),
        "destination": str(destination),
        "writes": False,
        "network": False,
        "runtime_effect": "package-cache-only",
    }


def _validate_archive_members(path):
    name = str(path).lower()
    members = []
    if name.endswith(".zip"):
        with zipfile.ZipFile(path) as archive:
            members = [(item.filename, item.is_dir(), False) for item in archive.infolist()]
    elif name.endswith((".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tar.xz")):
        with tarfile.open(path) as archive:
            members = [(item.name, item.isdir(), item.issym() or item.islnk())
                       for item in archive.getmembers()]
    for member, is_dir, is_link in members:
        normalized = member.replace("\\", "/")
        parts = normalized.split("/")
        if normalized.startswith("/") or normalized.startswith("../") or ".." in parts:
            raise ValueError(f"unsafe archive member: {member}")
        if is_link:
            raise ValueError(f"archive links are not allowed: {member}")
        if not is_dir and not normalized:
            raise ValueError("archive member has an empty name")


def _copy_litert_source(source, destination):
    parsed = urllib.parse.urlparse(source)
    local = Path(parsed.path if parsed.scheme == "file" else source).expanduser()
    if parsed.scheme in ("", "file") and local.is_file():
        shutil.copyfile(local, destination)
        return
    if parsed.scheme not in ("http", "https"):
        raise ValueError("LiteRT artifact source must be a local file or HTTPS URL")
    request = urllib.request.Request(source, headers={"User-Agent": "simplicio-local/1"})
    with urllib.request.urlopen(request, timeout=120) as response, destination.open("wb") as stream:
        shutil.copyfileobj(response, stream, length=1024 * 1024)


def install_litert_package(*, repo_root=None, manifest_path=None,
                           cache_dir=None, platform_key=None,
                           artifact_path=None, yes=False):
    if not yes:
        raise ValueError("LiteRT installation requires explicit --yes or --dry-run")
    plan = build_litert_install_plan(
        repo_root=repo_root, manifest_path=manifest_path, cache_dir=cache_dir,
        platform_key=platform_key, artifact_path=artifact_path,
    )
    cache = Path(plan["cache_dir"])
    destination = Path(plan["destination"])
    cache.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".litert-lm-", dir=str(cache)))
    staged = staging / plan["artifact"]["name"]
    try:
        _copy_litert_source(plan["artifact"]["source"], staged)
        observed_size = staged.stat().st_size
        observed_sha256 = _sha256_file(staged)
        expected_size = plan["artifact"]["size_bytes"]
        expected_sha256 = plan["artifact"]["sha256"]
        if observed_size != expected_size:
            raise ValueError(f"LiteRT artifact size mismatch: expected {expected_size}, observed {observed_size}")
        if observed_sha256 != expected_sha256:
            raise ValueError(f"LiteRT artifact SHA-256 mismatch: expected {expected_sha256}, observed {observed_sha256}")
        _validate_archive_members(staged)
        destination.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staged, destination)
        if plan["artifact"]["executable"] and os.name != "nt":
            destination.chmod(0o755)
        receipt = {
            "schema": LITERT_RECEIPT_SCHEMA,
            "status": "completed",
            "package": plan["package"],
            "version": plan["version"],
            "platform": plan["platform"],
            "license": plan["license"],
            "components": plan["components"],
            "artifact": {
                **plan["artifact"],
                "observed_size_bytes": observed_size,
                "observed_sha256": observed_sha256,
            },
            "manifest_sha256": plan["manifest_sha256"],
            "destination": str(destination),
            "cache_dir": str(cache),
            "runtime_effect": "package-cache-only",
            "created_unix_ms": int(time.time() * 1000),
        }
        receipt_path = destination.parent / "install-receipt.json"
        temporary_receipt = receipt_path.with_name(f".{receipt_path.name}.{uuid.uuid4().hex}.tmp")
        temporary_receipt.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temporary_receipt, receipt_path)
        return receipt
    finally:
        shutil.rmtree(staging, ignore_errors=True)


LITERT_VERIFY_SCHEMA = "simplicio.local-litert-verify/v1"
LITERT_ROLLBACK_SCHEMA = "simplicio.local-litert-rollback/v1"


def _litert_receipt_path(plan):
    destination = Path(plan["destination"]).resolve()
    cache = Path(plan["cache_dir"]).resolve()
    if cache not in destination.parents:
        raise ValueError("LiteRT receipt destination is outside the managed cache")
    return destination.parent / "install-receipt.json"


def _offline_failure(schema, plan, reason, **details):
    return {
        "schema": schema,
        "status": "failed",
        "offline": True,
        "network": False,
        "writes": False,
        "package": plan["package"],
        "version": plan["version"],
        "platform": plan["platform"],
        "cache_dir": plan["cache_dir"],
        "destination": plan["destination"],
        "failure_reason": reason,
        **details,
    }


def verify_litert_package(*, repo_root=None, manifest_path=None,
                          cache_dir=None, platform_key=None):
    plan = build_litert_install_plan(
        repo_root=repo_root, manifest_path=manifest_path,
        cache_dir=cache_dir, platform_key=platform_key,
    )
    receipt_path = _litert_receipt_path(plan)
    if receipt_path.is_symlink() or not receipt_path.is_file():
        return _offline_failure(
            LITERT_VERIFY_SCHEMA, plan, "offline-cache-miss",
            receipt_path=str(receipt_path),
        )
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        return _offline_failure(
            LITERT_VERIFY_SCHEMA, plan, "offline-receipt-invalid",
            receipt_path=str(receipt_path), detail=str(error),
        )
    destination = Path(plan["destination"])
    if receipt.get("schema") != LITERT_RECEIPT_SCHEMA:
        return _offline_failure(
            LITERT_VERIFY_SCHEMA, plan, "offline-receipt-schema-mismatch",
            receipt_path=str(receipt_path),
        )
    if receipt.get("status") != "completed":
        return _offline_failure(
            LITERT_VERIFY_SCHEMA, plan, "offline-receipt-not-completed",
            receipt_path=str(receipt_path),
        )
    if Path(str(receipt.get("destination", ""))).resolve() != destination.resolve():
        return _offline_failure(
            LITERT_VERIFY_SCHEMA, plan, "offline-receipt-destination-mismatch",
            receipt_path=str(receipt_path),
        )
    if receipt.get("manifest_sha256") != plan["manifest_sha256"]:
        return _offline_failure(
            LITERT_VERIFY_SCHEMA, plan, "offline-manifest-mismatch",
            receipt_path=str(receipt_path),
        )
    if destination.is_symlink() or not destination.is_file():
        return _offline_failure(
            LITERT_VERIFY_SCHEMA, plan, "offline-cache-miss",
            receipt_path=str(receipt_path),
        )
    observed_size = destination.stat().st_size
    observed_sha256 = _sha256_file(destination)
    expected_size = plan["artifact"]["size_bytes"]
    expected_sha256 = plan["artifact"]["sha256"]
    if observed_size != expected_size or observed_sha256 != expected_sha256:
        return _offline_failure(
            LITERT_VERIFY_SCHEMA, plan, "offline-integrity-failure",
            receipt_path=str(receipt_path), expected_size_bytes=expected_size,
            observed_size_bytes=observed_size, expected_sha256=expected_sha256,
            observed_sha256=observed_sha256,
        )
    return {
        "schema": LITERT_VERIFY_SCHEMA,
        "status": "verified",
        "offline": True,
        "network": False,
        "writes": False,
        "package": plan["package"],
        "version": plan["version"],
        "platform": plan["platform"],
        "cache_dir": plan["cache_dir"],
        "destination": str(destination),
        "receipt_path": str(receipt_path),
        "artifact": {
            **plan["artifact"],
            "observed_size_bytes": observed_size,
            "observed_sha256": observed_sha256,
        },
        "manifest_sha256": plan["manifest_sha256"],
        "runtime_effect": "package-cache-only",
    }


def rollback_litert_package(*, repo_root=None, manifest_path=None,
                            cache_dir=None, platform_key=None, yes=False):
    if not yes:
        raise ValueError("LiteRT rollback requires explicit --yes")
    plan = build_litert_install_plan(
        repo_root=repo_root, manifest_path=manifest_path,
        cache_dir=cache_dir, platform_key=platform_key,
    )
    receipt_path = _litert_receipt_path(plan)
    if receipt_path.is_symlink() or not receipt_path.is_file():
        raise ValueError("managed LiteRT receipt not found")
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ValueError(f"managed LiteRT receipt is invalid: {error}") from error
    destination = Path(plan["destination"])
    if Path(str(receipt.get("destination", ""))).resolve() != destination.resolve():
        raise ValueError("managed LiteRT receipt destination mismatch")
    if destination.is_symlink() or not destination.is_file():
        raise ValueError("managed LiteRT artifact is missing or unsafe")
    if receipt.get("manifest_sha256") != plan["manifest_sha256"]:
        raise ValueError("managed LiteRT receipt manifest mismatch")
    removed = []
    for path in (destination, receipt_path):
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"managed LiteRT path is missing or unsafe: {path}")
        path.unlink()
        removed.append(str(path))
    cache = Path(plan["cache_dir"]).resolve()
    directory = destination.parent
    while directory != cache and cache in directory.parents:
        try:
            directory.rmdir()
        except OSError:
            break
        directory = directory.parent
    return {
        "schema": LITERT_ROLLBACK_SCHEMA,
        "status": "rolled_back",
        "offline": True,
        "network": False,
        "writes": True,
        "package": plan["package"],
        "version": plan["version"],
        "platform": plan["platform"],
        "cache_dir": str(cache),
        "removed": removed,
        "preserved": "unmanaged cache files, models, and configuration",
        "runtime_effect": "package-cache-only",
    }
