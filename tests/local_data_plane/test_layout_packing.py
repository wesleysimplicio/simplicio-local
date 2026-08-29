import tempfile
import unittest
from pathlib import Path

from local_data_plane.layout_packing import (
    AtomicPackedCache,
    BatchRequest,
    PackedLayoutKey,
    digest_int8,
    form_isolated_batch,
    pack_int8_rhs,
    select_tiling,
    validate_packed_layout,
)


class LayoutPackingTests(unittest.TestCase):
    def _key(self, data=b"\x01\x02\x03\x04"):
        return PackedLayoutKey("model", "weight", digest_int8(data), "avx2", "kernel-v1")

    def test_column_major_pack_is_versioned_and_validated(self):
        data = bytes((1, 2, 3, 4))
        artifact = pack_int8_rhs(data, 2, 2, self._key(data))
        self.assertEqual(artifact.values, bytes((1, 3, 2, 4)))
        self.assertTrue(validate_packed_layout(artifact, artifact.key, 2, 2))

    def test_cache_rebuilds_after_corruption_and_invalidates_by_key(self):
        data = bytes((1, 2, 3, 4))
        key = self._key(data)
        artifact = pack_int8_rhs(data, 2, 2, key)
        with tempfile.TemporaryDirectory() as directory:
            cache = AtomicPackedCache(directory)
            cache.store(artifact)
            self.assertEqual(cache.load(key, 2, 2), artifact)
            path = Path(directory) / (key.fingerprint + ".json")
            path.write_text("{broken", encoding="utf-8")
            self.assertIsNone(cache.load(key, 2, 2))
            cache.store(artifact)
            self.assertTrue(cache.invalidate(key))
            self.assertIsNone(cache.load(key, 2, 2))

    def test_tiling_is_fail_closed_without_evidence_or_with_regression(self):
        self.assertFalse(select_tiling(32, 128, 128).enabled)
        self.assertFalse(select_tiling(32, 128, 128, measured_speedup=0.2,
                                        p95_regression=0.2).enabled)
        self.assertTrue(select_tiling(32, 128, 128, mode="prefill",
                                      measured_speedup=0.2, p95_regression=0.05).enabled)

    def test_batch_preserves_session_identity_and_falls_back_safely(self):
        requests = [BatchRequest("b", "model", 20, 0), BatchRequest("a", "model", 20, 2)]
        fallback = form_isolated_batch(requests)
        self.assertEqual(fallback.session_ids, ("a",))
        selected = form_isolated_batch(requests, throughput_gain=0.1, p95_regression=0.05)
        self.assertEqual(selected.session_ids, ("a", "b"))
        self.assertTrue(selected.isolated_kv)
        cross_model = form_isolated_batch([BatchRequest("a", "m1"), BatchRequest("b", "m2")],
                                          throughput_gain=0.5)
        self.assertEqual(cross_model.session_ids, ("a",))


if __name__ == "__main__":
    unittest.main()
