from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
CI_PATH = ROOT / ".github/workflows/ci.yml"


class Gemini37FlashV4QualificationWorkflowTests(unittest.TestCase):
    def test_one_shot_lane_is_exactly_scoped_to_gemini37_v4_candidate(self) -> None:
        workflow = CI_PATH.read_text(encoding="utf-8")
        self.assertIn("semantic-v4-provider-candidate-gemini37-flash", workflow)
        self.assertIn("refs/heads/phase12-eu-v4-gemini37", workflow)
        self.assertIn("[semantic-v4-candidate:gemini-3.7-flash] qualify frozen contract once", workflow)
        self.assertIn("GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}", workflow)
        self.assertIn("needs: [infrastructure, historical-production-replay]", workflow)
        self.assertIn("python -m scripts.qualify_gemini37_flash_v4", workflow)
        self.assertIn("event-understanding-gemini37-flash-v4-${{ github.run_id }}", workflow)


if __name__ == "__main__":
    unittest.main()
