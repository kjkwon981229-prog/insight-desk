from __future__ import annotations

from pathlib import Path
import unittest


class Phase9FullRegressionGateTests(unittest.TestCase):
    def test_full_regression_workflow_preserves_zero_cost_and_complete_local_runtime_gates(self) -> None:
        workflow = Path(".github/workflows/phase9-full-regression.yml").read_text(encoding="utf-8")
        runner_lines = [line.strip() for line in workflow.splitlines() if "runs-on:" in line]
        self.assertEqual(runner_lines, ["runs-on: ubuntu-24.04"])
        self.assertNotIn("secrets.", workflow)
        self.assertIn(".[semantic-local,qa]", workflow)
        self.assertIn("python -m unittest discover -s tests -p 'test_*.py' -v", workflow)
        self.assertIn("python benchmarks/validate.py", workflow)
        self.assertIn("tests.test_semantic_properties", workflow)
        self.assertIn("npm ci && npm test", workflow)
        self.assertIn("push-sw.js", workflow)
        self.assertIn("docs/NEWS_REWRITE_POLICY_V1.md", workflow)
        self.assertIn("larger_runner=0", workflow)


if __name__ == "__main__":
    unittest.main()
