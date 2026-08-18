import tempfile
import unittest
from pathlib import Path

from local_data_plane.estimator import estimate_asset, estimate_resources


class EstimatorTests(unittest.TestCase):
    def test_kv_formula_and_total_are_provenance_labeled(self):
        estimate = estimate_resources(weight_bytes=100, context_tokens=4, layers=2,
                                      kv_heads=2, head_dim=8, dtype_bytes=2,
                                      recurrent_state_bytes=3, mtp_state_bytes=5,
                                      working_buffer_bytes=7, read_bytes=100)
        self.assertEqual(estimate.kv_cache.value, 512)
        self.assertEqual(estimate.kv_cache.semantics, "estimated")
        self.assertEqual(estimate.total_resident.value, 627)

    def test_unknown_is_null_not_zero(self):
        estimate = estimate_resources(weight_bytes=10)
        self.assertIsNone(estimate.kv_cache.value)
        self.assertEqual(estimate.kv_cache.semantics, "unknown")
        self.assertIsNone(estimate.total_resident.value)

    def test_asset_size_is_observed(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "tiny.gguf"
            path.write_bytes(b"GGUF")
            estimate = estimate_asset(path)
            self.assertEqual(estimate.weights.value, 4)
            self.assertEqual(estimate.weights.semantics, "observed")
            self.assertEqual(estimate.disk_footprint.value, 4)


if __name__ == "__main__":
    unittest.main()
