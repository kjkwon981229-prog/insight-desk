from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
CI_PATH = ROOT / ".github/workflows/ci.yml"


class Gemini36FlashV4QualificationWorkflowTests(unittest.TestCase):
    def test_one_shot_lane_is_exactly_scoped_to_candidate_branch_and_marker(self) -> None:
        workflow = CI_PATH.read_text(encoding="utf-8")
        self.assertIn("semantic-v4-provider-candidate-gemini36-flash:", workflow)
        self.assertIn("needs: [infrastructure, historical-production-replay]", workflow)
        self.assertIn("github.event_name == 'push'", workflow)
        self.assertIn("github.ref == 'refs/heads/phase12-eu-v4-gemini36'", workflow)
        self.assertIn(
            "contains(github.event.head_commit.message, '[semantic-v4-candidate:gemini-3.6-flash]')",
            workflow,
        )

    def test_lane_uses_existing_gemini_secret_and_v4_wrapper_only(self) -> None:
        workflow = CI_PATH.read_text(encoding="utf-8")
        self.assertIn("GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}", workflow)
        self.assertIn(
            "python -m scripts.qualify_gemini36_flash_v4 --report event-understanding-qualification.json",
            workflow,
        )
        self.assertIn("name: event-understanding-gemini36-flash-v4", workflow)
        self.assertIn("continue-on-error: true", workflow)
        self.assertIn("sha256sum event-understanding-qualification.json || true", workflow)
        self.assertIn("Preserve non-pass qualification as failed candidate job", workflow)
        self.assertNotIn("--provider gemini36_flash", workflow)
        self.assertNotIn(
            "qualify_event_understanding_provider_v4.py --provider gemini36_flash",
            workflow,
        )


if __name__ == "__main__":
    unittest.main()
