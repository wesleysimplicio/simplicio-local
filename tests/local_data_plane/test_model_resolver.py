import unittest

from local_data_plane.model_resolver import ModelCandidate, ModelResolver, parse_model_request


class ModelResolverTests(unittest.TestCase):
    def setUp(self):
        self.candidates = (
            ModelCandidate("qwen3-8b-q4", "qwen", "3", 8, "Q4_K_M", "https://models.invalid/qwen3-8b-q4.gguf", 8, aliases=("Qwen 3 8B Q4",), workload_intents=("coding",)),
            ModelCandidate("llama3-8b-q4", "llama", "3", 8, "Q4_K_M", "https://models.invalid/llama3-8b-q4.gguf", 8, workload_intents=("chat",)),
            ModelCandidate("mistral-7b-q8", "mistral", "1", 7, "Q8_0", "https://models.invalid/mistral-7b-q8.gguf", 8),
        )

    def test_parses_family_size_quant_and_intent(self):
        request = parse_model_request("Qwen3 8B Q4_K_M for coding")
        self.assertEqual(request.family, "qwen")
        self.assertEqual(request.version, "3")
        self.assertEqual(request.parameter_billions, 8)
        self.assertEqual(request.quantization, "Q4_K_M")
        self.assertEqual(request.workload, "coding")

    def test_resolves_exact_alias(self):
        result = ModelResolver(self.candidates).resolve(parse_model_request("Qwen 3 8B Q4_K_M coding"))
        self.assertEqual(result.status, "resolved")
        self.assertEqual(result.selected.model_id, "qwen3-8b-q4")

    def test_ambiguous_request_returns_actionable_alternatives(self):
        result = ModelResolver(self.candidates).resolve(parse_model_request("8B Q4"))
        self.assertEqual(result.status, "ambiguous")
        self.assertTrue(result.alternatives)
        self.assertIn("family", result.explanation)

    def test_explicit_id_overrides_natural_language(self):
        result = ModelResolver(self.candidates).resolve(
            parse_model_request("anything", explicit_id="llama3-8b-q4"))
        self.assertEqual(result.status, "resolved")
        self.assertEqual(result.selected.model_id, "llama3-8b-q4")


if __name__ == "__main__":
    unittest.main()
