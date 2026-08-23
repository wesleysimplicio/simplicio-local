import unittest

from local_data_plane.session_scheduler import MultiSessionScheduler, SessionRequest


class SessionSchedulerTests(unittest.TestCase):
    def _request(self, name, kv=100, priority=0):
        return SessionRequest(name, kv, "qwen", "template", priority)

    def test_admission_is_bounded_and_cancel_releases_budget(self):
        scheduler = MultiSessionScheduler(memory_budget_bytes=150, kv_budget_bytes=150, max_sessions=4)
        self.assertTrue(scheduler.admit(self._request("a")).accepted)
        self.assertFalse(scheduler.admit(self._request("b")).accepted)
        self.assertEqual(scheduler.admit(self._request("b")).status, "busy")
        self.assertTrue(scheduler.cancel("a"))
        self.assertTrue(scheduler.admit(self._request("b")).accepted)

    def test_batching_requires_non_regressive_evidence(self):
        scheduler = MultiSessionScheduler(memory_budget_bytes=1000, kv_budget_bytes=1000,
                                          batch_evidence={"throughput_gain": 0.1, "p95_regression": 0.05})
        scheduler.admit(self._request("slow", priority=1)); scheduler.admit(self._request("fast"))
        self.assertEqual(scheduler.form_batch(["fast", "slow"]), ("slow", "fast"))
        regressive = MultiSessionScheduler(memory_budget_bytes=1000, kv_budget_bytes=1000,
                                           batch_evidence={"throughput_gain": 0.2, "p95_regression": 0.5})
        regressive.admit(self._request("a")); regressive.admit(self._request("b"))
        self.assertEqual(regressive.form_batch(["a", "b"]), ("a",))

    def test_session_identity_is_not_shared_in_status(self):
        scheduler = MultiSessionScheduler(memory_budget_bytes=1000, kv_budget_bytes=1000)
        scheduler.admit(SessionRequest("a", 100, "qwen", "t1")); scheduler.admit(SessionRequest("b", 100, "qwen", "t2"))
        self.assertEqual(scheduler.status()["sessions"]["a"]["template_hash"], "t1")
        self.assertEqual(scheduler.status()["sessions"]["b"]["template_hash"], "t2")

    def test_duplicate_admission_does_not_double_count(self):
        scheduler = MultiSessionScheduler(memory_budget_bytes=100, kv_budget_bytes=100)
        scheduler.admit(self._request("a", 80))
        self.assertEqual(scheduler.admit(self._request("a", 80)).status, "reused")
        self.assertEqual(scheduler.status()["kv_used_bytes"], 80)


if __name__ == "__main__":
    unittest.main()
