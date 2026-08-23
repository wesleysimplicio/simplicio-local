import unittest

from local_data_plane.worker_scheduler import plan_workers


class WorkerSchedulerTests(unittest.TestCase):
    def test_measured_candidate_wins_within_migration_and_tail_budget(self):
        schedule = plan_workers({"physical_cpus": 8, "logical_cpus": 16, "numa_nodes": 2}, measured=[
            {"threads": 8, "throughput": 100, "migrations": 20, "p95_regression": 0.02},
            {"threads": 12, "throughput": 120, "migrations": 10, "p95_regression": 0.05},
        ])
        self.assertEqual(schedule.threads, 12)
        self.assertEqual(schedule.numa_node, 0)
        self.assertTrue(schedule.oversubscribed)

    def test_no_evidence_uses_conservative_physical_core_fallback(self):
        schedule = plan_workers({"physical_cpus": 8, "logical_cpus": 16})
        self.assertEqual(schedule.threads, 8)
        self.assertFalse(schedule.oversubscribed)
        self.assertIn("fallback", schedule.reason)

    def test_regressive_candidates_are_not_promoted(self):
        schedule = plan_workers({"physical_cpus": 4, "logical_cpus": 8}, measured=[
            {"threads": 8, "throughput": 200, "migrations": 1000, "p95_regression": 0.5},
        ])
        self.assertEqual(schedule.threads, 4)

    def test_missing_topology_remains_safe(self):
        schedule = plan_workers({}, measured=())
        self.assertEqual(schedule.threads, 1)
        self.assertTrue(schedule.accepted)


if __name__ == "__main__":
    unittest.main()
