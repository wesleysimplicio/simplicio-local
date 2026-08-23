import unittest

from local_data_plane.clean_install_e2e import E2EAdapters, run_clean_install


class CleanInstallE2ETests(unittest.TestCase):
    def _adapters(self, *, chat_status=200):
        return E2EAdapters(
            resolve=lambda _: {"model_id": "qwen3-8b", "family": "qwen"},
            acquire=lambda _: {"verified": True, "sha256": "a" * 64},
            configure=lambda _: {"accepted": True, "backend": "cpu", "strategy": "baseline"},
            start=lambda _: {"base_url": "http://127.0.0.1:8080/v1", "backend": "cpu"},
            models=lambda _: {"status": 200, "model_id": "qwen3-8b"},
            chat=lambda _, __: {"status": chat_status, "text": "hello" if chat_status == 200 else ""},
        )

    def test_ready_requires_models_and_chat(self):
        result = run_clean_install('Qwen3 8B Q4', self._adapters())
        self.assertTrue(result["ready"])
        self.assertEqual(result["status"], "ready")
        self.assertEqual([step["name"] for step in result["steps"]],
                         ["resolve", "acquire_verify", "configure", "start", "health_models", "health_chat"])

    def test_chat_failure_cannot_report_ready(self):
        result = run_clean_install('Qwen3 8B Q4', self._adapters(chat_status=500))
        self.assertFalse(result["ready"])
        self.assertEqual(result["status"], "blocked")
        self.assertIn("chat", result["failure"])

    def test_unverified_artifact_stops_flow(self):
        adapters = self._adapters()
        broken = E2EAdapters(adapters.resolve, lambda _: {"verified": False}, adapters.configure,
                             adapters.start, adapters.models, adapters.chat)
        result = run_clean_install('Qwen3 8B Q4', broken)
        self.assertFalse(result["ready"])
        self.assertIn("verified", result["failure"])
        self.assertEqual(len(result["steps"]), 1)


if __name__ == "__main__":
    unittest.main()
