import unittest

from local_data_plane.kv_compression import KVCompressionObservation, select_kv_compression


class KVCompressionTests(unittest.TestCase):
    def _identity(self):
        return {"model_id": "qwen", "tokenizer_hash": "tok", "template_hash": "template",
                "session_id": "s1", "prefix_hash": "p1"}

    def test_recent_window_stays_reference_and_cold_region_can_compress(self):
        plan = select_kv_compression(identity=self._identity(), observation=KVCompressionObservation(0, 0.02, 0.01, 2.0, 100, True))
        self.assertTrue(plan.accepted)
        self.assertEqual(plan.recent_policy, "reference_recent_window")
        self.assertEqual(plan.cold_policy, "factorized_quantized_cold")

    def test_regression_is_fail_closed(self):
        plan = select_kv_compression(identity=self._identity(), observation=KVCompressionObservation(-0.2, 0.2, 0.2, 3.0, 100, True))
        self.assertFalse(plan.accepted)
        self.assertEqual(plan.cold_policy, "reference_cold")

    def test_unmeasured_path_is_off(self):
        plan = select_kv_compression(identity=self._identity(), observation=KVCompressionObservation(0, 0, 0, 3.0, 0, False))
        self.assertFalse(plan.accepted)
        self.assertIn("unmeasured", plan.reason)

    def test_identity_changes_invalidate_reuse(self):
        first = select_kv_compression(identity=self._identity(), observation=KVCompressionObservation(0, 0, 0, 2, 0, True))
        changed = self._identity(); changed["prefix_hash"] = "p2"
        second = select_kv_compression(identity=changed, observation=KVCompressionObservation(0, 0, 0, 2, 0, True))
        self.assertNotEqual(first.identity_key, second.identity_key)


if __name__ == "__main__":
    unittest.main()
