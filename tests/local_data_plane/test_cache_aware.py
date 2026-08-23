import unittest

from local_data_plane.cache_aware import plan_traversal, reorder_blocks


class CacheAwareTests(unittest.TestCase):
    def test_prefetch_requires_positive_measurement_and_stays_bounded(self):
        plan = plan_traversal(16, 64, prefetch_distance=4, input_bytes=16 * 64, measured_speedup=0.08)
        self.assertTrue(plan.prefetch_enabled)
        self.assertEqual(plan.prefetch_distance, 4)

    def test_regression_and_bounds_disable_prefetch(self):
        regression = plan_traversal(16, 64, prefetch_distance=4, input_bytes=16 * 64,
                                     measured_speedup=0.08, regression=True)
        out_of_bounds = plan_traversal(16, 64, prefetch_distance=4, input_bytes=8 * 64, measured_speedup=0.08)
        self.assertFalse(regression.prefetch_enabled)
        self.assertFalse(out_of_bounds.prefetch_enabled)

    def test_unaligned_blocks_preserve_upstream_fallback(self):
        plan = plan_traversal(4, 63, prefetch_distance=1, measured_speedup=0.2)
        self.assertFalse(plan.prefetch_enabled)
        self.assertIn("unaligned", plan.reason)

    def test_layout_reordering_does_not_mutate_public_blocks(self):
        blocks = (b"a", b"b", b"c")
        self.assertEqual(reorder_blocks(blocks), blocks)


if __name__ == "__main__":
    unittest.main()
