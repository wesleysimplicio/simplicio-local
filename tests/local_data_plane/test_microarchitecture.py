import unittest

from local_data_plane.microarchitecture import MicroarchitectureAwarePlanner


class MicroarchitectureTests(unittest.TestCase):
    def _inputs(self, *, measured=True, prefetch=True, accepted=True):
        return {
            "topology": {"schema": "simplicio-local.hardware-topology/v1", "fingerprint": "abc"},
            "baseline": {"status": "measured" if measured else "incomplete",
                          "cases": [{"roofline": {"classification": "memory-bandwidth-bound"}}]},
            "traversal": {"prefetch_enabled": prefetch},
            "kv": {"format": {"name": "full_precision"}, "max_context": 4096, "accepted": accepted},
            "execution": {"backend": "cpu", "accepted": accepted, "placement": {"draft_device": "cpu"}},
        }

    def test_measured_plan_can_enable_prefetch_but_not_cache_pinning(self):
        values = self._inputs()
        plan = MicroarchitectureAwarePlanner().plan(**values)
        self.assertTrue(plan.accepted)
        self.assertTrue(plan.prefetch_enabled)
        self.assertEqual(plan.traversal_mode, "cache-aware")
        self.assertIn("cache-observation-not-pinning", plan.evidence)

    def test_missing_evidence_disables_optimization(self):
        plan = MicroarchitectureAwarePlanner().plan(**self._inputs(measured=False))
        self.assertFalse(plan.prefetch_enabled)
        self.assertEqual(plan.traversal_mode, "upstream-fallback")
        self.assertIn("benchmark evidence unavailable", plan.reason)

    def test_memory_rejection_propagates(self):
        plan = MicroarchitectureAwarePlanner().plan(**self._inputs(accepted=False))
        self.assertFalse(plan.accepted)
        self.assertIn("fallback", plan.reason)

    def test_unversioned_topology_is_rejected(self):
        values = self._inputs()
        values["topology"] = {"fingerprint": "abc"}
        with self.assertRaises(ValueError):
            MicroarchitectureAwarePlanner().plan(**values)


if __name__ == "__main__":
    unittest.main()
