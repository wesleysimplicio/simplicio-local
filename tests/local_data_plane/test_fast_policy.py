import json
import tempfile
import unittest
from pathlib import Path

from local_data_plane.fast_policy import FastPolicyClient, FastPolicyRequest, write_receipt


class FastPolicyTests(unittest.TestCase):
    def _request(self, **kwargs):
        values = {
            "model_id": "qwen3",
            "backend": "cuda",
            "workload": "coding",
            "capabilities": ("ngram_prompt_lookup", "mtp"),
        }
        values.update(kwargs)
        return FastPolicyRequest(**values)

    def test_precedence_and_off_are_deterministic(self):
        client = FastPolicyClient()
        explicit = client.select(self._request(mode="explicit", explicit_strategy="mtp"))
        disabled = client.select(self._request(mode="off", explicit_strategy=None))
        self.assertEqual(explicit.strategy, "mtp")
        self.assertEqual(disabled.strategy, "baseline")
        self.assertIn("disabled", disabled.explanation)

    def test_fast_response_is_validated_and_capability_checked(self):
        client = FastPolicyClient(lambda _: {"strategy": "dflash", "explanation": "unsupported claim"})
        plan = client.select(self._request())
        self.assertEqual(plan.strategy, "baseline")
        self.assertTrue(plan.used_fallback)
        self.assertIn("unproven", plan.explanation)

    def test_receipt_persists_selection_and_evidence(self):
        client = FastPolicyClient(lambda _: {
            "strategy": "mtp", "fallback": "baseline", "max_draft_tokens": 3,
            "explanation": "MTP metadata and backend support match", "evidence": ["model-metadata"],
        })
        receipt = client.receipt(self._request())
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "receipt.json"
            write_receipt(receipt, path)
            payload = json.loads(path.read_text())
        self.assertEqual(payload["plan"]["strategy"], "mtp")
        self.assertEqual(payload["plan"]["evidence"], ["model-metadata"])
        self.assertEqual(payload["schema"], "simplicio-local.fast-policy/v1")

    def test_invalid_policy_falls_back(self):
        client = FastPolicyClient(lambda _: {"strategy": "not-a-strategy", "explanation": "bad"})
        plan = client.select(self._request())
        self.assertEqual(plan.strategy, "baseline")
        self.assertTrue(plan.used_fallback)


if __name__ == "__main__":
    unittest.main()
