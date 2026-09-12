from pathlib import Path
import unittest


class Phase12FailureDiagnosticArtifactTests(unittest.TestCase):
    def test_publishable_pr_artifact_survives_quality_gate_failure_for_review(self) -> None:
        workflow = Path(".github/workflows/insight-desk-production.yml").read_text(encoding="utf-8")
        section_start = workflow.index("name: Upload canonical PR production artifact")
        section_end = workflow.index("name: Upload PR failure diagnostics")
        section = workflow[section_start:section_end]
        self.assertIn("always()", section)
        self.assertIn("steps.state.outputs.publish == 'true'", section)

    def test_pr_failure_preserves_state_and_audit_without_starting_second_production(self) -> None:
        workflow = Path(".github/workflows/insight-desk-production.yml").read_text(encoding="utf-8")
        self.assertEqual(workflow.count("Run current-engine daily production"), 1)
        self.assertIn("name: Upload PR failure diagnostics", workflow)
        section_start = workflow.index("name: Upload PR failure diagnostics")
        section_end = workflow.index("name: Fail closed when no publishable briefing exists")
        section = workflow[section_start:section_end]
        self.assertIn("always()", section)
        self.assertIn("github.event_name == 'pull_request'", section)
        self.assertIn("steps.state.outputs.publish != 'true'", section)
        self.assertNotIn("failure()", section)
        self.assertIn("build/run-state.json", section)
        self.assertIn("build/production-audit.json", section)
        self.assertIn("name: production-diagnostic-${{ github.run_id }}", section)


if __name__ == "__main__":
    unittest.main()
