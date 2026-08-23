import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from local_data_plane.model_catalog import CATALOG_SCHEMA_V1, TrustedModelCatalog, verify_artifact, write_provenance


class ModelCatalogTests(unittest.TestCase):
    def _payload(self, digest, size):
        return {
            "schema": CATALOG_SCHEMA_V1, "revision": "catalog-2026-08-23",
            "sources": [
                {"name": "mirror", "trust_rank": 10, "base_url": "https://mirror.invalid"},
                {"name": "primary", "trust_rank": 20, "base_url": "https://primary.invalid"},
            ],
            "entries": [{
                "model_id": "qwen3-8b-q4", "family": "qwen", "version": "3", "parameter_billions": 8,
                "aliases": ["Qwen 3 8B Q4"], "quantizations": ["Q4_K_M"],
                "artifacts": [
                    {"artifact_id": "mirror-q4", "source": "mirror", "url": "https://mirror.invalid/q4", "size_bytes": size, "sha256": digest},
                    {"artifact_id": "primary-q4", "source": "primary", "url": "https://primary.invalid/q4", "size_bytes": size, "sha256": digest},
                ],
            }],
        }

    def test_ranking_is_deterministic_and_prefers_trusted_source(self):
        payload = self._payload("a" * 64, 4)
        catalog = TrustedModelCatalog.from_payload(payload)
        ranked = catalog.rank_artifacts("qwen3-8b-q4", backend="cuda")
        self.assertEqual(ranked[0].source, "primary")
        self.assertEqual(ranked[1].source, "mirror")

    def test_verification_requires_size_and_checksum(self):
        data = b"GGUF"
        digest = hashlib.sha256(data).hexdigest()
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "model.gguf"
            path.write_bytes(data)
            catalog = TrustedModelCatalog.from_payload(self._payload(digest, len(data)))
            artifact = catalog.rank_artifacts("qwen3-8b-q4")[0]
            receipt = verify_artifact(path, artifact)
            self.assertTrue(receipt.accepted)
            path.write_bytes(b"bad")
            self.assertFalse(verify_artifact(path, artifact).accepted)

    def test_family_and_parameter_mismatch_never_substitute(self):
        catalog = TrustedModelCatalog.from_payload(self._payload("a" * 64, 4))
        with self.assertRaises(ValueError):
            catalog.find("qwen3-8b-q4", family="llama")
        with self.assertRaises(ValueError):
            catalog.find("qwen3-8b-q4", parameter_billions=7)

    def test_provenance_is_written_only_after_verification(self):
        data = b"GGUF"
        digest = hashlib.sha256(data).hexdigest()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "model.gguf"
            path.write_bytes(data)
            catalog = TrustedModelCatalog.from_payload(self._payload(digest, len(data)))
            entry = catalog.find("qwen3-8b-q4")
            artifact = catalog.rank_artifacts(entry.model_id)[0]
            receipt = verify_artifact(path, artifact)
            destination = root / "provenance.json"
            write_provenance(destination, catalog=catalog, entry=entry, artifact=artifact, verification=receipt)
            self.assertEqual(json.loads(destination.read_text())["catalog_revision"], "catalog-2026-08-23")


if __name__ == "__main__":
    unittest.main()
