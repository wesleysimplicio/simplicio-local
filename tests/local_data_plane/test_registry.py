import tempfile
import unittest
from pathlib import Path

from local_data_plane.registry import BackendCapability, BackendRegistry, EvidenceLevel


class RegistryTests(unittest.TestCase):
    def test_duplicate_ids_fail_closed(self):
        item = BackendCapability("x", "engine", "linux", "x86_64", "cpu",
                                 EvidenceLevel.SOURCE_PRESENT, False, True, False, False)
        registry = BackendRegistry([item])
        with self.assertRaises(ValueError):
            registry.register(item)

    def test_source_presence_does_not_promote_execution(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "runtime" / "adapters" / "llama").mkdir(parents=True)
            registry = BackendRegistry.default(root)
            llama = registry.get("llama-cpp")
            self.assertIsNotNone(llama)
            self.assertEqual(llama.evidence_level, EvidenceLevel.SOURCE_PRESENT)
            self.assertFalse(llama.available)
            self.assertFalse(llama.tested)

    def test_catalog_is_sorted_and_proxy_is_distinct(self):
        catalog = BackendRegistry.default(Path.cwd()).catalog()
        self.assertEqual([row["backend"] for row in catalog], sorted(row["backend"] for row in catalog))
        proxy = next(row for row in catalog if row["backend"] == "ollama-proxy")
        self.assertEqual(proxy["kind"], "proxy")


if __name__ == "__main__":
    unittest.main()
