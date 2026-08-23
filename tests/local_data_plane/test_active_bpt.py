import unittest

from local_data_plane.active_bpt import estimate_active_cost, rank_by_active_cost


class ActiveBPTTests(unittest.TestCase):
    def test_dense_and_moe_use_explicit_active_cost(self):
        dense = estimate_active_cost(model_id="dense", architecture="dense", total_parameters=10_000,
                                     bytes_per_parameter=1, kv_bytes_per_token=10)
        moe = estimate_active_cost(model_id="moe", architecture="moe", total_parameters=100_000,
                                   bytes_per_parameter=1, active_parameters_per_token=5_000,
                                   measured_weight_bytes_per_token=5_500, expert_residency="measured")
        self.assertEqual(dense.active_parameters_per_token, 10_000)
        self.assertEqual(moe.weight_bytes_per_token, 5_500)
        self.assertEqual(rank_by_active_cost((dense, moe))[0].model_id, "moe")

    def test_moe_name_alone_does_not_claim_active_count(self):
        cost = estimate_active_cost(model_id="advertised-moe", architecture="moe", total_parameters=100,
                                    bytes_per_parameter=1)
        self.assertIsNone(cost.active_parameters_per_token)
        self.assertEqual(cost.confidence, "unknown")

    def test_invalid_architecture_and_parameters_fail_closed(self):
        with self.assertRaises(ValueError):
            estimate_active_cost(model_id="x", architecture="unknown", total_parameters=1, bytes_per_parameter=1)
        with self.assertRaises(ValueError):
            estimate_active_cost(model_id="x", architecture="dense", total_parameters=0, bytes_per_parameter=1)

    def test_bpt_is_explicitly_reported(self):
        cost = estimate_active_cost(model_id="dense", architecture="dense", total_parameters=100,
                                    bytes_per_parameter=2)
        self.assertEqual(cost.weight_bytes_per_token, 200)
        self.assertIn("schema", cost.as_dict())


if __name__ == "__main__":
    unittest.main()
