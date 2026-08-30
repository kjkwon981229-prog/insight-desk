from pathlib import Path
import unittest


class Phase12FailureDiagnosticArtifactTests(unittest.TestCase):
    def test_pr_failure_preserves_state_and_audit_without_starting_second_production(self) -> None:
        workflow = Path(".github/workflows/insight-desk-production.yml").read_text(encoding="utf-8")
        self.assertEqual(workflow.count("Run current-engine daily production"), 1)
        self.assertIn("name: Upload PR failure diagnostics", workflow)
        section = workflow[workflow.index("name: Upload PR failure diagnostics") :]
        self.assertIn("always()", section)
        self.assertIn("github.event_name == 'pull_request'", section)
        self.assertIn("steps.state.outputs.publish != 'true'", section)
        self.assertIn("build/run-state.json", section)
        self.assertIn("build/production-audit.json", section)
        self.assertIn("name: production-diagnostic-${{ github.run_id }}", section)


if __name__ == "__main__":
    unittest.main()
