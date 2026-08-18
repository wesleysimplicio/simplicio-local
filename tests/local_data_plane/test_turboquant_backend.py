import io
import json
import tempfile
import unittest
import tarfile
from pathlib import Path

from local_data_plane.turboquant_backend import (
    ATOMIC_REPO,
    TurboQuantBackendInstaller,
    platform_asset,
)


class _Response:
    def __init__(self, payload: bytes):
        self.payload = io.BytesIO(payload)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def read(self, size=-1):
        return self.payload.read(size)


class TurboQuantBackendTests(unittest.TestCase):
    def test_atomic_platform_allowlist(self):
        self.assertEqual(platform_asset("darwin", "arm64"), "macos-arm64")
        self.assertEqual(platform_asset("linux", "amd64"), "linux-x64-vulkan")
        self.assertIsNone(platform_asset("freebsd", "x86_64"))

    def test_install_extracts_and_records_provenance(self):
        archive = io.BytesIO()
        with tarfile.open(fileobj=archive, mode="w:gz") as bundle:
            for name, payload, mode in (("release/bin/llama-server", b"#!/bin/sh\n", 0o755),
                                        ("release/lib/libggml.so", b"fixture", 0o644)):
                info = tarfile.TarInfo(name)
                info.size = len(payload)
                info.mode = mode
                bundle.addfile(info, io.BytesIO(payload))
            link = tarfile.TarInfo("release/lib/libllama.so")
            link.type = tarfile.SYMTYPE
            link.linkname = "libggml.so"
            bundle.addfile(link)
        archive_bytes = archive.getvalue()
        api_payload = json.dumps({"backends": [{
            "id": "linux-x64-vulkan",
            "tag": "b-test-1.0.0",
            "asset": "llama-turboquant-linux-x64-vulkan.tar.gz",
        }]}).encode("utf-8")

        def opener(request, timeout=0):
            return _Response(api_payload if request.full_url.endswith("turboquant-manifest.json") else archive_bytes)

        with tempfile.TemporaryDirectory() as temp:
            installer = TurboQuantBackendInstaller(temp, system="linux", machine="x86_64", opener=opener)
            receipt = installer.install()
            executable = Path(str(receipt["executable"]))
            self.assertTrue(executable.is_file())
            self.assertTrue((executable.parent.parent / "lib" / "libllama.so").is_symlink())
            self.assertEqual(receipt["repository"], ATOMIC_REPO)
            current = Path(temp) / "backends" / "atomic-llama-cpp-turboquant" / "current.json"
            self.assertEqual(json.loads(current.read_text())["tag"], "b-test-1.0.0")
            self.assertEqual(installer.install()["archive_sha256"], receipt["archive_sha256"])


if __name__ == "__main__":
    unittest.main()
