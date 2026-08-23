import unittest

from local_data_plane.kernel_dispatch import KernelCandidate, select_kernel


class KernelDispatchTests(unittest.TestCase):
    def _candidates(self):
        return (KernelCandidate("scalar", (), 0, 0, 0),
                KernelCandidate("avx2", ("avx2",), 0.2, 1e-5, 10),
                KernelCandidate("amx", ("amx",), 0.5, 1e-3, 10))

    def test_isa_and_numeric_gates_select_best_safe_kernel(self):
        plan = select_kernel(isa_features=("avx2",), candidates=self._candidates(),
                             hardware_fingerprint="h", backend="cpu", model_digest="m", runtime_version="v")
        self.assertEqual(plan.selected, "avx2")
        self.assertFalse(plan.cache_hit)

    def test_unsupported_isa_uses_scalar_fallback(self):
        plan = select_kernel(isa_features=(), candidates=self._candidates(),
                             hardware_fingerprint="h", backend="cpu", model_digest="m", runtime_version="v")
        self.assertEqual(plan.selected, "scalar")

    def test_tuning_cache_key_invalidates_on_model_or_backend_change(self):
        first = select_kernel(isa_features=("avx2",), candidates=self._candidates(),
                              hardware_fingerprint="h", backend="cpu", model_digest="m", runtime_version="v")
        cached = select_kernel(isa_features=("avx2",), candidates=self._candidates(),
                               hardware_fingerprint="h", backend="cpu", model_digest="m", runtime_version="v",
                               tuning_cache={first.tuning_key: "avx2"})
        changed = select_kernel(isa_features=("avx2",), candidates=self._candidates(),
                                hardware_fingerprint="h", backend="cuda", model_digest="m", runtime_version="v",
                                tuning_cache={first.tuning_key: "avx2"})
        self.assertTrue(cached.cache_hit)
        self.assertFalse(changed.cache_hit)

    def test_numeric_error_and_startup_budget_gate_promotion(self):
        plan = select_kernel(isa_features=("avx2",), candidates=self._candidates(),
                             hardware_fingerprint="h", backend="cpu", model_digest="m", runtime_version="v",
                             numeric_tolerance=1e-6, tuning_budget_ms=5)
        self.assertEqual(plan.selected, "scalar")


if __name__ == "__main__":
    unittest.main()
