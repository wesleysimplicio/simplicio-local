import unittest

from local_data_plane.telemetry_levels import collect_telemetry


class TelemetryLevelTests(unittest.TestCase):
    def test_minimal_has_small_guaranteed_surface(self):
        receipt = collect_telemetry(requested="minimal", available={"tok_s": 10, "plan_digest": "p"},
                                    overhead_ms=0.1, budget_ms=1)
        self.assertEqual(receipt.effective.value, "minimal")
        self.assertIn("tok_s", receipt.available_metrics)
        self.assertIn("ttft_ms", receipt.unavailable)

    def test_deep_degrades_when_budget_is_exceeded(self):
        receipt = collect_telemetry(requested="deep", available={"tok_s": 10, "ipc": 2},
                                    overhead_ms=20, budget_ms=1)
        self.assertEqual(receipt.effective.value, "minimal")

    def test_standard_keeps_standard_when_within_budget(self):
        receipt = collect_telemetry(requested="standard", available={"tok_s": 10, "transfer_bytes": 4},
                                    overhead_ms=1, budget_ms=2)
        self.assertEqual(receipt.effective.value, "standard")

    def test_invalid_level_and_budget_fail_closed(self):
        with self.assertRaises(ValueError):
            collect_telemetry(requested="unknown", available={}, overhead_ms=0, budget_ms=1)
        with self.assertRaises(ValueError):
            collect_telemetry(requested="minimal", available={}, overhead_ms=0, budget_ms=-1)


if __name__ == "__main__":
    unittest.main()
