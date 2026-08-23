import unittest

from local_data_plane.fused_contraction import healthy_path_materializes_dense, plan_fused_contraction


class FusedContractionTests(unittest.TestCase):
    def test_fused_path_requires_quality_and_measurement(self):
        plan = plan_fused_contraction(representation="tensor_train", dimensions=(4096, 4096), ranks=(8, 8),
                                      tile_m=32, tile_n=32, scratch_budget_bytes=8192,
                                      measured_speedup=0.1, quality_error=1e-5)
        self.assertTrue(plan.fused)
        self.assertFalse(healthy_path_materializes_dense(plan))

    def test_unsupported_isa_falls_back(self):
        plan = plan_fused_contraction(representation="mpo", dimensions=(4, 4), ranks=(2,), tile_m=4, tile_n=4,
                                      scratch_budget_bytes=1024, isa_supported=False, measured_speedup=0.5, quality_error=0)
        self.assertFalse(plan.fused)
        self.assertIn("ISA", plan.reason)

    def test_scratch_and_overflow_bounds_are_gates(self):
        plan = plan_fused_contraction(representation="mps", dimensions=(4, 4), ranks=(2,), tile_m=64, tile_n=64,
                                      scratch_budget_bytes=1024, measured_speedup=0.5, quality_error=0)
        self.assertFalse(plan.fused)
        with self.assertRaises(OverflowError):
            plan_fused_contraction(representation="mps", dimensions=(2**31 + 1,), ranks=(1,), tile_m=1, tile_n=1,
                                   scratch_budget_bytes=10, quality_error=0)

    def test_no_measurement_keeps_reference_path(self):
        plan = plan_fused_contraction(representation="low_rank", dimensions=(8, 8), ranks=(2,), tile_m=2, tile_n=2,
                                      scratch_budget_bytes=1024, quality_error=0)
        self.assertFalse(plan.fused)
        self.assertTrue(plan.accepted)


if __name__ == "__main__":
    unittest.main()
