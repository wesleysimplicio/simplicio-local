import json
import platform
import tempfile
import unittest
from pathlib import Path

from local_data_plane.distribution import LocalInstaller, create_manifest


class DistributionTests(unittest.TestCase):
    def _package(self, root: Path, version: str, payload: bytes) -> Path:
        package = root / f"package-{version}"
        package.mkdir()
        (package / "bin").mkdir()
        (package / "bin" / "simplicio-local").write_bytes(payload)
        for name, value in (("LICENSE", "MIT"), ("NOTICE", "notice"),
                            ("sbom.spdx.json", "{}"), ("provenance.json", "{}")):
            (package / name).write_text(value)
        manifest = create_manifest(package, version=version)
        (package / "manifest.json").write_text(json.dumps(manifest.as_dict()))
        return package

    def test_clean_install_update_rollback_and_model_preservation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            p1 = self._package(root, "1.0.0", b"one")
            p2 = self._package(root, "2.0.0", b"two")
            models = root / "user models"
            models.mkdir()
            (models / "owned.gguf").write_bytes(b"keep")
            installer = LocalInstaller(root / "install", user_model_root=models)
            installer.install(p1)
            installer.install(p2)
            self.assertEqual(installer.active_version(), "2.0.0")
            self.assertEqual(installer.rollback(), "1.0.0")
            self.assertEqual((models / "owned.gguf").read_bytes(), b"keep")
            self.assertEqual(installer.service_plan().mode, "child-process")
            installer.uninstall()
            self.assertTrue((models / "owned.gguf").exists())

    def test_protocol_and_checksum_gates_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            package = self._package(root, "1.0.0", b"one")
            installer = LocalInstaller(root / "install")
            with self.assertRaises(RuntimeError):
                installer.install(package, runtime_protocol=1)
            (package / "bin" / "simplicio-local").write_bytes(b"tampered")
            with self.assertRaises(RuntimeError):
                installer.install(package)


if __name__ == "__main__":
    unittest.main()
