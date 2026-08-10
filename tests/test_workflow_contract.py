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

    def test_schedule_and_selection_audit_contract(self) -> None:
        workflow = Path(".github/workflows/insight-desk-pages.yml").read_text(encoding="utf-8")
        self.assertIn('cron: "30 22 * * *"', workflow)
        self.assertIn("selection-audit-${{ github.run_id }}", workflow)
        self.assertIn("hashFiles('build/selection-audit.json')", workflow)

    def test_authoritative_credentials_are_injected_only_as_workflow_env(self) -> None:
        workflow = Path(".github/workflows/insight-desk-pages.yml").read_text(encoding="utf-8")
        self.assertIn("OPENDART_API_KEY: ${{ secrets.OPENDART_API_KEY }}", workflow)
        self.assertIn("KOSIS_API_KEY: ${{ secrets.KOSIS_API_KEY }}", workflow)
        self.assertIn('echo "::add-mask::$OPENDART_API_KEY"', workflow)
        self.assertIn('echo "::add-mask::$KOSIS_API_KEY"', workflow)
        self.assertNotIn("echo $OPENDART_API_KEY", workflow)
        self.assertNotIn("echo $KOSIS_API_KEY", workflow)


if __name__ == "__main__":
    unittest.main()
