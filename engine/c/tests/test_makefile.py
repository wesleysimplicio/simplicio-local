"""Build-graph regressions for the vendored C engine (issue #122)."""

import subprocess
import unittest
from pathlib import Path


ENGINE_DIR = Path(__file__).resolve().parents[1]
ENGINE_WRAPPER_DIR = ENGINE_DIR.parent


class MakefileGraphTest(unittest.TestCase):
    def test_glm_target_has_no_self_dependency_warning(self):
        result = subprocess.run(
            ["make", "-n", "glm"],
            cwd=ENGINE_DIR,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        output = result.stdout + result.stderr
        self.assertNotIn("Circular glm <- glm dependency dropped", output)

    def test_engine_wrapper_exposes_the_documented_test_target(self):
        result = subprocess.run(
            ["make", "-n", "test"],
            cwd=ENGINE_WRAPPER_DIR,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        output = result.stdout + result.stderr
        self.assertIn("-C", output)
        self.assertIn(str(ENGINE_DIR), output)
        self.assertIn(" test", output)


if __name__ == "__main__":
    unittest.main()
