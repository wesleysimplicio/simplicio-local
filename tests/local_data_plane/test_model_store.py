import tempfile
import unittest
from pathlib import Path

from local_data_plane.model_store import ModelStore


class ModelStoreTests(unittest.TestCase):
    def test_content_addressing_offline_update_and_rollback(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "store"
            source = Path(temp) / "model.gguf"
            source.write_bytes(b"GGUF-v1")
            store = ModelStore(root)
            first = store.put_file(source, "qwen-tiny", revision="r1", license="Apache-2.0")
            self.assertTrue(store.verify("qwen-tiny"))
            self.assertEqual(store.resolve("qwen-tiny").name, first.sha256)
            source.write_bytes(b"GGUF-v2")
            second = store.put_file(source, "qwen-tiny", revision="r2", license="Apache-2.0")
            self.assertEqual(second.history, (first.sha256,))
            rolled = store.rollback("qwen-tiny")
            self.assertEqual(rolled.sha256, first.sha256)
            self.assertEqual(store.resolve("qwen-tiny").read_bytes(), b"GGUF-v1")

    def test_tampering_and_hash_mismatch_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "model.safetensors"
            source.write_bytes(b"weights")
            store = ModelStore(Path(temp) / "store")
            with self.assertRaises(ValueError):
                store.put_file(source, "safe", expected_sha256="0" * 64)
            record = store.put_file(source, "safe")
            (store.objects / record.sha256).write_bytes(b"tampered")
            self.assertFalse(store.verify("safe"))

    def test_model_id_cannot_escape_store(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "model.gguf"
            source.write_bytes(b"GGUF")
            store = ModelStore(Path(temp) / "store")
            with self.assertRaises(ValueError):
                store.put_file(source, "../outside")


if __name__ == "__main__":
    unittest.main()
