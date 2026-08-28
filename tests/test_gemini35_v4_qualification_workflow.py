from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
CI_PATH = ROOT / ".github/workflows/ci.yml"


class Gemini35FlashV4QualificationWorkflowTests(unittest.TestCase):
    def test_consumed_one_shot_lane_is_no_longer_installed(self) -> None:
        workflow = CI_PATH.read_text(encoding="utf-8")
        self.assertNotIn("semantic-v4-provider-candidate-gemini35-flash", workflow)
        self.assertNotIn("refs/heads/phase12-eu-v4-gemini35", workflow)
        self.assertNotIn("[semantic-v4-candidate:gemini-3.5-flash]", workflow)
        self.assertNotIn("qualify_gemini35_flash_v4", workflow)
        self.assertNotIn("event-understanding-gemini35-flash-v4", workflow)
        self.assertNotIn("GEMINI_API_KEY", workflow)


if __name__ == "__main__":
    unittest.main()
