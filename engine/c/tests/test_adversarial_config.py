"""Regression coverage for hostile model configuration dimensions (issue #122).

These tests intentionally stop before loading any tensor data.  ``load_cfg`` is the
trust boundary for untrusted ``config.json`` files, so malformed dimensions must be
rejected with an actionable diagnostic and an ordinary exit code rather than reaching
the allocator or corrupting a fixed-size work buffer.
"""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
ENGINE_DIR = HERE.parent
GLM_BIN = ENGINE_DIR / "glm"


BASE_CONFIG = {
    "hidden_size": 64,
    "num_hidden_layers": 2,
    "num_attention_heads": 4,
    "n_routed_experts": 8,
    "num_experts_per_tok": 2,
    "moe_intermediate_size": 128,
    "intermediate_size": 128,
    "first_k_dense_replace": 0,
    "q_lora_rank": 16,
    "kv_lora_rank": 8,
    "qk_nope_head_dim": 8,
    "qk_rope_head_dim": 8,
    "v_head_dim": 8,
    "n_shared_experts": 1,
    "vocab_size": 128,
    "index_topk": 0,
    "index_n_heads": 0,
    "index_head_dim": 0,
}


class AdversarialConfigTest(unittest.TestCase):
    """Every case must fail cleanly at the config choke point."""

    @classmethod
    def setUpClass(cls):
        if GLM_BIN.is_file():
            return
        result = subprocess.run(
            ["make", "glm"], cwd=ENGINE_DIR, capture_output=True, text=True, timeout=120
        )
        if result.returncode != 0 or not GLM_BIN.is_file():
            raise unittest.SkipTest(f"engine build unavailable: {result.stderr[-400:]}")

    def run_invalid_config(self, overrides):
        config = dict(BASE_CONFIG)
        config.update(overrides)
        with tempfile.TemporaryDirectory() as directory:
            snapshot = Path(directory)
            (snapshot / "config.json").write_text(
                json.dumps(config), encoding="utf-8"
            )
            result = subprocess.run(
                [str(GLM_BIN), "1", "16", "16"],
                cwd=ENGINE_DIR,
                env=dict(os.environ, SNAP=str(snapshot)),
                capture_output=True,
                text=True,
                timeout=10,
            )
        self.assertGreater(result.returncode, 0, result.stderr)
        self.assertGreaterEqual(result.returncode, 0, "config rejection must not be a signal")
        self.assertNotIn("Segmentation fault", result.stderr)
        return result.stderr

    def test_rejects_dimensions_that_exceed_fixed_work_buffer_contracts(self):
        cases = (
            ({"qk_rope_head_dim": 257}, "qk_rope_head_dim"),
            ({"index_n_heads": 65, "index_head_dim": 8}, "index_n_heads"),
            ({"num_experts_per_tok": 65}, "num_experts_per_tok"),
        )
        for overrides, field in cases:
            with self.subTest(field=field):
                self.assertIn(field, self.run_invalid_config(overrides))

    def test_rejects_inconsistent_group_and_indexer_dimensions(self):
        cases = (
            ({"n_group": 3}, "nao e' divisivel"),
            ({"index_n_heads": 1, "index_head_dim": 4}, "index_head_dim"),
            ({"qk_rope_head_dim": -1}, "qk_rope_head_dim"),
        )
        for overrides, diagnostic in cases:
            with self.subTest(diagnostic=diagnostic):
                self.assertIn(diagnostic, self.run_invalid_config(overrides))


if __name__ == "__main__":
    unittest.main()
