from __future__ import annotations

import unittest
from pathlib import Path


class WorkflowContractTests(unittest.TestCase):
    def test_total_failure_fails_build_before_pages_deploy(self) -> None:
        workflow = Path(".github/workflows/insight-desk-pages.yml").read_text(encoding="utf-8")
        self.assertIn("name: Fail closed on total failure", workflow)
        self.assertIn("if: steps.state.outputs.status == 'TOTAL_FAILURE'", workflow)
        self.assertIn("exit 1", workflow)
        self.assertIn("if: needs.build.result == 'success' && needs.build.outputs.publish == 'true'", workflow)


if __name__ == "__main__":
    unittest.main()
