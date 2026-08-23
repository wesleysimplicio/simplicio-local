import unittest

from local_data_plane.execution_plan_v2 import build_execution_plan, validate_execution_plan


class ExecutionPlanV2Tests(unittest.TestCase):
    def _build(self, **overrides):
        values = {
            "model": {"model_id": "qwen3"}, "artifact": {"sha256": "a" * 64},
            "topology": {"fingerprint": "topology"}, "workers": {"threads": 8},
            "kernel": {"selected": "scalar", "isa_requirements": []}, "placement": {"accepted": True},
            "kv": {"accepted": True, "max_context": 4096}, "mmap": {"generation": "g1"},
            "residency": {"accepted": True}, "speculative": {"strategy": "baseline"},
            "baseline": {"status": "measured"}, "measured_generation": "g1",
        }
        values.update(overrides)
        return build_execution_plan(**values)

    def test_same_inputs_have_same_digest(self):
        self.assertEqual(self._build().digest, self._build().digest)
        self.assertEqual(self._build().as_dict()["schema"], "simplicio-local.execution-plan/v2")

    def test_plan_rejects_cannot_fit_and_stale_tuning(self):
        cannot = self._build(kv={"accepted": False})
        self.assertEqual(validate_execution_plan(cannot), (False, "cannot_fit"))
        stale = self._build()
        self.assertEqual(validate_execution_plan(stale, current_tuning_generation="g2"),
                         (False, "stale-tuning-generation"))

    def test_isa_gate_is_explicit(self):
        plan = self._build(kernel={"selected": "avx2", "isa_requirements": ["avx2"]})
        self.assertEqual(validate_execution_plan(plan, available_isa=set()), (False, "unsupported-isa"))
        self.assertEqual(validate_execution_plan(plan, available_isa={"avx2"}), (True, "plan-valid"))

    def test_required_identity_is_fail_closed(self):
        with self.assertRaises(ValueError):
            self._build(artifact={"sha256": ""})


if __name__ == "__main__":
    unittest.main()
