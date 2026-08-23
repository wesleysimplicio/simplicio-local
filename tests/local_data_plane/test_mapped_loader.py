import hashlib
import tempfile
import unittest
from pathlib import Path

from local_data_plane.mapped_loader import PersistentMappedLoader


class MappedLoaderTests(unittest.TestCase):
    def test_verified_mapping_is_read_only_and_generation_bound(self):
        data = b"GGUF" + b"payload" * 20
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "model.gguf"
            path.write_bytes(data)
            digest = hashlib.sha256(data).hexdigest()
            mapping = PersistentMappedLoader().map_verified(path, expected_sha256=digest, generation="g1")
            self.assertEqual(mapping.read(0, 4), b"GGUF")
            self.assertTrue(PersistentMappedLoader.can_replace(mapping, new_generation="g2"))
            mapping.close()

    def test_checksum_and_bounds_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "model.gguf"
            path.write_bytes(b"data")
            with self.assertRaises(ValueError):
                PersistentMappedLoader().map_verified(path, expected_sha256="0" * 64, generation="g1")
            digest = hashlib.sha256(b"data").hexdigest()
            mapping = PersistentMappedLoader().map_verified(path, expected_sha256=digest, generation="g1")
            with self.assertRaises(ValueError):
                mapping.read(3, 3)
            mapping.close()

    def test_active_mapping_blocks_remove_but_buffered_fallback_works(self):
        data = b"model"
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "model.gguf"
            path.write_bytes(data)
            digest = hashlib.sha256(data).hexdigest()
            loader = PersistentMappedLoader()
            mapping = loader.map_verified(path, expected_sha256=digest, generation="g1")
            with self.assertRaises(RuntimeError):
                loader.remove(path, active=mapping)
            mapping.close()
            self.assertEqual(loader.read_buffered(path, expected_sha256=digest), data)
            loader.remove(path)
            self.assertFalse(path.exists())

    def test_same_generation_is_not_silently_reused(self):
        self.assertTrue(PersistentMappedLoader.can_replace(None, new_generation="g1"))


if __name__ == "__main__":
    unittest.main()
