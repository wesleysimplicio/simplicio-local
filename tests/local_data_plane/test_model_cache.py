import hashlib
import tempfile
import unittest
from pathlib import Path

from local_data_plane.model_cache import CacheArtifact, ModelCache


class ModelCacheTests(unittest.TestCase):
    def test_resumable_download_and_duplicate_aliases(self):
        data = b"model payload" * 100
        digest = hashlib.sha256(data).hexdigest()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source.gguf"
            source.write_bytes(data)
            cache = ModelCache(root / "cache")
            artifact = CacheArtifact("qwen3-8b", "Q4_K_M", str(source), len(data), digest,
                                     {"catalog_revision": "r1"})
            part = cache.parts / f"{digest}.part"
            part.write_bytes(data[:50])
            result = cache.download(artifact, aliases=("Qwen3 8B Q4",))
            self.assertEqual(result.read_bytes(), data)
            self.assertTrue(cache.verify(artifact.ref_id))
            self.assertEqual(cache.status()["objects"], 1)

    def test_corruption_is_detected_and_repaired(self):
        data = b"stable model"
        digest = hashlib.sha256(data).hexdigest()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source.gguf"
            source.write_bytes(data)
            cache = ModelCache(root / "cache")
            artifact = CacheArtifact("llama3-8b", "Q4", str(source), len(data), digest)
            path = cache.download(artifact)
            path.write_bytes(b"corrupt")
            self.assertFalse(cache.verify(artifact.ref_id))
            self.assertEqual(cache.repair(artifact.ref_id).read_bytes(), data)

    def test_remove_and_insufficient_space_are_safe(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source.gguf"
            source.write_bytes(b"tiny")
            cache = ModelCache(root / "cache")
            artifact = CacheArtifact("tiny", "Q4", str(source), 4, hashlib.sha256(b"tiny").hexdigest())
            cache.download(artifact)
            cache.remove(artifact.ref_id)
            self.assertEqual(cache.list(), ())

    def test_wrong_size_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source.gguf"
            source.write_bytes(b"tiny")
            cache = ModelCache(root / "cache")
            artifact = CacheArtifact("tiny", "Q4", str(source), 5, hashlib.sha256(b"tiny").hexdigest())
            with self.assertRaises(IOError):
                cache.download(artifact)


if __name__ == "__main__":
    unittest.main()
