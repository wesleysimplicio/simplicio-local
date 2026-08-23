import json
import sys
import tempfile
import unittest
from pathlib import Path

from runtime.benchmarks.speculative_benchmark import SCHEMA_ID, BenchmarkCase, run_suite, validate_suite


class SpeculativeBenchmarkTests(unittest.TestCase):
    def test_dry_run_is_planned_and_has_no_claim(self):
        case = BenchmarkCase("baseline-coding", "coding", "baseline", (sys.executable, "-c", "print('{}')"))
        receipt = run_suite((case,), dry_run=True)
        self.assertEqual(receipt["status"], "planned")
        self.assertEqual(receipt["claims"], [])
        self.assertIsNone(receipt["cases"][0]["metrics"])

    def test_measured_equivalence_is_workload_scoped(self):
        code = "import json; print(json.dumps({'output':'same','prompt_tokens':2,'generation_tokens':3,'accepted_tokens':2}))"
        cases = (
            BenchmarkCase("baseline-chat", "chat", "baseline", (sys.executable, "-c", code)),
            BenchmarkCase("mtp-chat", "chat", "mtp", (sys.executable, "-c", code)),
        )
        receipt = run_suite(cases)
        self.assertEqual(receipt["status"], "measured")
        self.assertTrue(receipt["cases"][1]["output_equivalent"])
        self.assertEqual(receipt["cases"][1]["metrics"]["accepted_tokens"], 2)

    def test_invalid_matrix_is_rejected(self):
        errors = validate_suite({"schema": SCHEMA_ID, "cases": [{"id": "x", "strategy": "unknown"}]})
        self.assertTrue(errors)

    def test_cli_fixture_can_be_serialized(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "suite.json"
            path.write_text(json.dumps({"schema": SCHEMA_ID, "cases": [{
                "id": "baseline", "workload": "coding", "strategy": "baseline",
                "command": [sys.executable, "-c", "print('{}')"],
            }]}))
            self.assertEqual(len(validate_suite(json.loads(path.read_text()))), 0)


if __name__ == "__main__":
    unittest.main()
