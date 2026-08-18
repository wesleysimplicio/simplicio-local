import hashlib
import tempfile
import unittest
from pathlib import Path

from local_data_plane.colibri import ColibriBackend, ExpertShard


class ColibriTests(unittest.TestCase):
    def test_disk_first_stream_reports_bytes_per_token_and_cache(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = root / "expert0.safetensors"
            second = root / "expert1.safetensors"
            first.write_bytes(b"expert-zero")
            second.write_bytes(b"expert-one")
            backend = ColibriBackend([
                ExpertShard("e0", str(first), hashlib.sha256(first.read_bytes()).hexdigest()),
                ExpertShard("e1", str(second)),
            ], cache_capacity=1)
            run = backend.stream(["e0", "e1", "e1"])
            self.assertEqual(run.status, "completed")
            self.assertEqual(run.metrics.tokens, 3)
            self.assertEqual(run.metrics.cache_hits, 1)
            self.assertEqual(run.metrics.read_bytes_per_token, (len(first.read_bytes()) + len(second.read_bytes())) / 3)
            self.assertEqual(run.metrics.swap_semantics, "unknown")

    def test_missing_or_corrupt_shards_fail_without_partial_success(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "expert.safetensors"
            path.write_bytes(b"good")
            backend = ColibriBackend([ExpertShard("e0", str(path), "0" * 64)])
            run = backend.stream(["e0"])
            self.assertEqual(run.status, "failed")
            self.assertEqual(run.output, ())

    def test_cancel_is_bounded(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "expert.safetensors"
            path.write_bytes(b"good")
            backend = ColibriBackend([ExpertShard("e0", str(path))])
            run = backend.stream(["e0"], cancelled=lambda: True)
            self.assertEqual(run.status, "cancelled")
            self.assertEqual(run.output, ())


if __name__ == "__main__":
    unittest.main()
