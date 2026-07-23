import json
import unittest

from backend_contract import (GB, PROTOCOL, LeaseRegistry, admission_estimate,
                              build_receipt, capability_probe)


class BackendContractTest(unittest.TestCase):
    def test_probe_is_read_only_and_honest(self):
        report = capability_probe()
        self.assertEqual(report["protocol"], PROTOCOL)
        self.assertTrue(report["read_only"])
        self.assertFalse(report["model_payload_read"])
        self.assertEqual(report["capabilities"]["tool_execution"], "forbidden")
        self.assertIsNone(report["identity"]["effective_model"])

    def test_admission_is_bounded_and_interactive_fails_closed(self):
        allowed = admission_estimate(
            model_bytes=10 * GB, dense_bytes=6 * GB,
            available_memory=16 * GB, available_disk=400 * GB,
            hard_rss_limit=13 * GB, workload="deep-offline",
        )
        self.assertEqual(allowed["decision"], "admit")
        interactive = admission_estimate(
            model_bytes=10 * GB, dense_bytes=6 * GB,
            available_memory=16 * GB, available_disk=400 * GB,
            hard_rss_limit=13 * GB, workload="interactive",
        )
        self.assertEqual(interactive["decision"], "deny")
        self.assertIsNone(interactive["estimate"]["tokens_per_second"])

    def test_admission_never_exceeds_hard_limit(self):
        report = admission_estimate(
            model_bytes=10 * GB, dense_bytes=11 * GB,
            available_memory=16 * GB, available_disk=400 * GB,
            hard_rss_limit=13 * GB, workload="batch",
        )
        self.assertEqual(report["decision"], "deny")
        self.assertIn("projected-rss-exceeds-hard-limit", report["reasons"])

    def test_registry_is_single_flight_and_fenced(self):
        registry = LeaseRegistry()
        first = registry.acquire("lease-a", "glm", "int4")
        self.assertIs(first, registry.acquire("lease-a", "glm", "int4"))
        with self.assertRaisesRegex(RuntimeError, "already-leased"):
            registry.acquire("lease-b", "glm", "int4")
        first.transition("loading")
        first.transition("draining")
        first.transition("stopped")
        second = registry.acquire("lease-b", "glm", "int4")
        self.assertGreater(second.fence, first.fence)

    def test_receipt_has_hash_null_metrics_and_no_effect_authority(self):
        lease = LeaseRegistry().acquire("lease-a", "glm", "int4")
        receipt = build_receipt(
            lease, "request-a", "glm", "glm-int4", "completed", b"answer",
            {"peak_rss_bytes": 12 * GB},
        )
        self.assertEqual(receipt["effect_authority"], "none")
        self.assertEqual(len(receipt["output_sha256"]), 64)
        self.assertIsNone(receipt["metrics"]["tokens_per_second"])
        json.dumps(receipt)


if __name__ == "__main__":
    unittest.main()
