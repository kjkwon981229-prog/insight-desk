from __future__ import annotations

import unittest

from insight_desk.curation.grounding import CardLine, check_grounding

SENTENCES = [
    "딥브레인AI는 총 15억 원 규모의 연구개발을 추진한다고 19일 밝혔다.",
    "총 연구개발비 15억 원 가운데 정부지원금은 10억 원이다.",
    "2026년 9월부터 2028년 8월까지 약 2년간 기술 개발을 진행한다.",
]
NO_NOUNS = lambda text: frozenset()  # noqa: E731


class ClaimWordGroundingTests(unittest.TestCase):
    def _check(self, text: str):
        return check_grounding(
            [CardLine(text=text, evidence=(0,))] * 3,
            SENTENCES,
            noun_extractor=NO_NOUNS,
            proper_extractor=NO_NOUNS,
        )

    def test_invested_when_source_says_research_budget_is_rejected(self):
        result = self._check("딥브레인AI, 영상 에이전트 개발에 15억 원 투자함")
        self.assertFalse(result.ok)
        self.assertEqual(result.code, "grounding:claim")

    def test_source_wording_is_accepted(self):
        self.assertTrue(self._check("딥브레인AI, 15억 원 규모 연구개발 추진").ok)


if __name__ == "__main__":
    unittest.main()
