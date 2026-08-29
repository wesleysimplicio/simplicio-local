import tempfile
import unittest

from local_data_plane.kernel_dispatch import (
    KernelCandidate,
    PersistentTuningCache,
    run_bounded_autotune,
    select_kernel,
    tuning_key,
)


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

    def test_key_includes_isa_shape_and_layout_identity(self):
        base = tuning_key(hardware_fingerprint="h", backend="cpu", model_digest="m", runtime_version="v")
        changed = tuning_key(hardware_fingerprint="h", backend="cpu", model_digest="m", runtime_version="v",
                             isa_features=("avx2",), shape_class="decode", layout_version="packed-v2")
        self.assertNotEqual(base, changed)

    def test_bounded_autotune_requires_safe_baseline_and_p95_gate(self):
        candidates = (KernelCandidate("scalar", (), 0, 0, 0),
                      KernelCandidate("avx2", ("avx2",), None, 1e-5, 10),
                      KernelCandidate("bad", ("avx2",), None, 1e-5, 10))

        def benchmark(candidate):
            if candidate.name == "scalar":
                return {"p50_ms": 10, "p95_ms": 11, "runs": 4}
            if candidate.name == "avx2":
                return {"p50_ms": 7, "p95_ms": 11.5, "runs": 4}
            return {"p50_ms": 5, "p95_ms": 20, "runs": 4}

        result = run_bounded_autotune(candidates=candidates, benchmark=benchmark, isa_features=("avx2",))
        self.assertEqual(result.selected, "avx2")
        self.assertEqual(result.reason, "bounded-autotune-promoted")

    def test_persistent_cache_is_atomic_and_cache_only_falls_back(self):
        candidates = self._candidates()
        with tempfile.TemporaryDirectory() as directory:
            cache = PersistentTuningCache(f"{directory}/tuning.json")
            key = tuning_key(hardware_fingerprint="h", backend="cpu", model_digest="m", runtime_version="v")
            cache.store(key, "avx2", metadata={"isa": "avx2"})
            self.assertEqual(cache.load(key, candidates), "avx2")
            plan = select_kernel(isa_features=(), candidates=candidates,
                                 hardware_fingerprint="h", backend="cpu", model_digest="m", runtime_version="v",
                                 persistent_cache=cache, tuning_mode="cache-only")
            self.assertEqual(plan.selected, "scalar")


if __name__ == "__main__":
    unittest.main()
