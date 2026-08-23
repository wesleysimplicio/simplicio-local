import unittest

from local_data_plane.conformance import run_conformance


class ConformanceTests(unittest.TestCase):
    def _evidence(self):
        return {"correctness": True, "endpoints": {"models": True, "chat_completions": True, "completions": False},
                "baseline_available": True, "artifact_sha256": "a" * 64, "backend_identity": "cpu-v1",
                "oom_safe": True, "plan_digest": "plan"}

    def test_supported_and_unsupported_endpoints_are_gated_correctly(self):
        report = run_conformance(self._evidence(), chaos_cases=["cancel"])
        self.assertEqual(report["status"], "blocked")
        self.assertIn("chaos:cancel", report["blockers"])
        self.assertNotIn("endpoint:completions", report["blockers"])

    def test_complete_evidence_passes(self):
        evidence = self._evidence()
        evidence["chaos"] = {"cancel": True, "stale_mmap": True}
        report = run_conformance(evidence, chaos_cases=["cancel", "stale_mmap"])
        self.assertTrue(report["ready"])
        self.assertEqual(report["status"], "passed")

    def test_correctness_and_oom_failures_cannot_be_waived(self):
        evidence = self._evidence()
        evidence["correctness"] = False
        evidence["oom_safe"] = False
        report = run_conformance(evidence)
        self.assertFalse(report["ready"])
        self.assertIn("correctness", report["blockers"])
        self.assertIn("oom-safety", report["blockers"])

    def test_performance_regression_is_not_silent(self):
        evidence = self._evidence()
        evidence["performance"] = {"regressed": True}
        report = run_conformance(evidence)
        gate = next(gate for gate in report["gates"] if gate["name"] == "performance-budget")
        self.assertFalse(gate["passed"])
        self.assertTrue(gate["waiver_allowed"])


if __name__ == "__main__":
    unittest.main()
