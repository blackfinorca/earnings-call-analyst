import importlib.util
import time
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "backend" / "research_app" / "scans" / "macro_scan.py"


def load_module():
    spec = importlib.util.spec_from_file_location("macro_scan", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ParallelRowTests(unittest.TestCase):
    def test_run_parallel_tasks_preserves_input_order(self):
        module = load_module()

        def slow():
            time.sleep(0.05)
            return "slow"

        def fast():
            return "fast"

        results = module.run_parallel_tasks(
            [("first", slow), ("second", fast)],
            max_workers=2,
        )

        self.assertEqual(results, {"first": "slow", "second": "fast"})
        self.assertEqual(list(results), ["first", "second"])


if __name__ == "__main__":
    unittest.main()
