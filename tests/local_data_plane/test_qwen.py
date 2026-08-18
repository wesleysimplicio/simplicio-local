import unittest

from local_data_plane.qwen import QwenHybridState, probe_metadata, promote_hybrid
from local_data_plane.registry import EvidenceLevel


class QwenTests(unittest.TestCase):
    def test_model_name_does_not_prove_hybrid_architecture(self):
        self.assertFalse(probe_metadata({"model_id": "Qwen3.6-27B"}).hybrid)

    def test_state_components_are_separate(self):
        state = QwenHybridState("qwen-tiny", "weights", "kv", "recurrent", "mtp")
        result = promote_hybrid(requested_model="Qwen3.6-27B",
                                metadata={"architecture": "qwen3_6", "recurrent_layers": 2, "mtp_depth": 1},
                                state=state, reference=["a"], candidate=["a"],
                                evidence=EvidenceLevel.FIXTURE_EXECUTED)
        self.assertTrue(result.promoted)
        self.assertEqual(result.state.as_dict()["attention_kv_ref"], "kv")

    def test_aliasing_or_missing_evidence_blocks_promotion(self):
        state = QwenHybridState("qwen", "weights", "same", "same", "mtp")
        result = promote_hybrid(requested_model="Qwen3.6-27B",
                                metadata={"architecture": "qwen3_6", "recurrent_layers": 2, "mtp_depth": 1},
                                state=state, reference=["a"], candidate=["a"],
                                evidence=EvidenceLevel.SOURCE_PRESENT)
        self.assertFalse(result.promoted)


if __name__ == "__main__":
    unittest.main()
