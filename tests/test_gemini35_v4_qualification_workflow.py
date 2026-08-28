from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
CI_PATH = ROOT / ".github/workflows/ci.yml"


class Gemini35FlashV4QualificationWorkflowTests(unittest.TestCase):
    def test_one_shot_lane_is_exactly_scoped_to_candidate_branch_and_marker(self) -> None:
        workflow = CI_PATH.read_text(encoding="utf-8")
        self.assertIn("semantic-v4-provider-candidate-gemini35-flash:", workflow)
        self.assertIn("needs: [infrastructure, historical-production-replay]", workflow)
        self.assertIn("github.event_name == 'push'", workflow)
        self.assertIn("github.ref == 'refs/heads/phase12-eu-v4-gemini35'", workflow)
        self.assertIn(
            "contains(github.event.head_commit.message, '[semantic-v4-candidate:gemini-3.5-flash]')",
            workflow,
        )

    def test_lane_uses_existing_gemini_secret_and_v4_wrapper_only(self) -> None:
        workflow = CI_PATH.read_text(encoding="utf-8")
        self.assertIn("GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}", workflow)
        self.assertIn(
            "python -m scripts.qualify_gemini35_flash_v4 --report event-understanding-qualification.json",
            workflow,
        )
        self.assertIn("name: event-understanding-gemini35-flash-v4", workflow)
        self.assertNotIn("--provider gemini35_flash", workflow)
        self.assertNotIn("qualify_event_understanding_provider.py --provider gemini35_flash", workflow)


if __name__ == "__main__":
    unittest.main()
