import io
import json
import tempfile
import unittest
import zipfile
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
        self.assertEqual(platform_asset("darwin", "arm64"), "llama-turboquant-macos-arm64.zip")
        self.assertEqual(platform_asset("linux", "amd64"), "llama-turboquant-linux-x64-vulkan.zip")
        self.assertIsNone(platform_asset("freebsd", "x86_64"))

    def test_install_extracts_and_records_provenance(self):
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as bundle:
            bundle.writestr("release/bin/llama-server", "#!/bin/sh\n")
            bundle.writestr("release/lib/libggml.so", "fixture")
        archive_bytes = archive.getvalue()
        api_payload = json.dumps([{
            "draft": False,
            "tag_name": "v-test",
            "assets": [{
                "name": "llama-turboquant-linux-x64-vulkan.zip",
                "browser_download_url": "https://example.invalid/turbo.zip",
                "size": len(archive_bytes),
            }],
        }]).encode("utf-8")

        def opener(request, timeout=0):
            return _Response(api_payload if request.full_url.endswith("releases?per_page=30") else archive_bytes)

        with tempfile.TemporaryDirectory() as temp:
            installer = TurboQuantBackendInstaller(temp, system="linux", machine="x86_64", opener=opener)
            receipt = installer.install()
            executable = Path(str(receipt["executable"]))
            self.assertTrue(executable.is_file())
            self.assertEqual(receipt["repository"], ATOMIC_REPO)
            current = Path(temp) / "backends" / "atomic-llama-cpp-turboquant" / "current.json"
            self.assertEqual(json.loads(current.read_text())["tag"], "v-test")
            self.assertEqual(installer.install()["archive_sha256"], receipt["archive_sha256"])


if __name__ == "__main__":
    unittest.main()
