import unittest
from pathlib import Path

from local_data_plane.mlx import MlxPromotionGate, MlxProvider
from local_data_plane.registry import EvidenceLevel


class MlxTests(unittest.TestCase):
    def test_non_apple_host_is_not_promoted(self):
        probe = MlxProvider(Path.cwd()).probe()
        if probe.reason == "MLX requires Apple Silicon":
            self.assertFalse(probe.available)

    def test_fixture_gate_requires_exact_parity(self):
        gate = MlxPromotionGate()
        fail = gate.promote_fixture(["a"], ["b"], "fixture.json")
        self.assertFalse(fail.promoted)
        success = gate.promote_fixture(["a", "b"], ["a", "b"], "fixture.json")
        self.assertEqual(success.evidence_level, EvidenceLevel.FIXTURE_EXECUTED)

    def test_benchmark_requires_real_model_evidence(self):
        gate = MlxPromotionGate()
        fixture = gate.promote_fixture(["a"], ["a"], "fixture.json")
        blocked = gate.promote_benchmark(fixture, hardware="M1", model="tiny", tokens=2,
                                         elapsed_ms=1, artifact="bench.json")
        self.assertFalse(blocked.promoted)
        real = gate.promote_real_model(["a"], ["a"], model="tiny", hardware="M1",
                                       elapsed_ms=1, artifact="real.json")
        benchmark = gate.promote_benchmark(real, hardware="M1", model="tiny", tokens=2,
                                           elapsed_ms=1, artifact="bench.json")
        self.assertEqual(benchmark.evidence_level, EvidenceLevel.BENCHMARKED_ON_TARGET)


if __name__ == "__main__":
    unittest.main()
