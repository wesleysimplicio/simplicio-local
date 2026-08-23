import unittest

from local_data_plane.qphys import FactorizedRepresentation, promote_qphys


class QPhysTests(unittest.TestCase):
    def _representation(self):
        return FactorizedRepresentation("tensor_train", (128, 128), (8, 8), 4)

    def test_classical_factorized_plan_is_non_materializing(self):
        self._representation().validate()
        self.assertFalse(self._representation().materialize_full_precision)
        self.assertTrue(self._representation().experimental)

    def test_quality_is_absolute_promotion_gate(self):
        accepted = promote_qphys(baseline_quality=1.0, candidate_quality=0.995, baseline_bytes=1000,
                                 candidate_bytes=700, baseline_tok_s=10, candidate_tok_s=11,
                                 representation=self._representation())
        self.assertTrue(accepted.accepted)
        rejected = promote_qphys(baseline_quality=1.0, candidate_quality=0.95, baseline_bytes=1000,
                                 candidate_bytes=700, baseline_tok_s=10, candidate_tok_s=11,
                                 representation=self._representation())
        self.assertFalse(rejected.accepted)

    def test_invalid_quantization_or_materialization_fails_closed(self):
        with self.assertRaises(ValueError):
            FactorizedRepresentation("mps", (2, 2), (1,), 1).validate()
        with self.assertRaises(ValueError):
            FactorizedRepresentation("mps", (2, 2), (1,), 4, materialize_full_precision=True).validate()

    def test_receipt_is_versioned(self):
        result = promote_qphys(baseline_quality=1, candidate_quality=1, baseline_bytes=100,
                               candidate_bytes=50, baseline_tok_s=None, candidate_tok_s=None,
                               representation=self._representation())
        self.assertEqual(result.as_dict()["schema"], "simplicio-local.qphys/v1")


if __name__ == "__main__":
    unittest.main()
