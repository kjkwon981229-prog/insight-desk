from __future__ import annotations

import unittest

from insight_desk.curation.grounding import CardLine, check_grounding


def _check(source: str, line: str):
    return check_grounding([CardLine(text=line, evidence=(0,))], [source], context="")


class GeminiReviewCaseTests(unittest.TestCase):
    def test_dropped_plain_negation_is_rejected(self) -> None:
        result = _check("해당 기업은 올해 신규 공장 증설 계획이 전혀 없다고 공식 발표했다.", "해당 기업 올해 신규 공장 증설 계획 발표")
        self.assertEqual(result.code, "grounding:negation_dropped")

    def test_reversed_direction_is_rejected(self) -> None:
        result = _check("A사의 3분기 매출은 500억원이었으며 연구개발 비용은 전년 대비 15% 감소했다.", "A사 3분기 매출 15% 증가")
        self.assertEqual(result.code, "grounding:direction")

    def test_same_direction_passes(self) -> None:
        result = _check("A사의 3분기 영업이익은 전년 대비 15% 감소했다.", "A사 3분기 영업이익 15% 감소")
        self.assertTrue(result.ok, result.code)

    def test_spaced_won_amount_matches(self) -> None:
        result = _check("해당 스타트업은 시리즈A 투자로 500억 원을 유치했다.", "스타트업 시리즈A 500억원 투자 유치")
        self.assertTrue(result.ok, result.code)

    def test_dollar_sign_matches_dollar_word(self) -> None:
        result = _check("The basic plan starts at $100 per month.", "기본 요금 월 100달러 책정")
        self.assertTrue(result.ok, result.code)


if __name__ == "__main__":
    unittest.main()
