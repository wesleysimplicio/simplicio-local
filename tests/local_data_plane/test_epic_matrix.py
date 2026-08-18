import unittest
from pathlib import Path


class EpicMatrixTests(unittest.TestCase):
    def test_all_child_slots_are_recorded(self):
        text = Path("docs/protocols/inference-data-plane-v2.md").read_text(encoding="utf-8")
        for issue in range(191, 204):
            self.assertIn(f"| #{issue} |", text)


if __name__ == "__main__":
    unittest.main()
