from __future__ import annotations

import unittest
from pathlib import Path

from insight_desk.pipeline.synthesis import is_usable_synthesis, summary_style_issues


class KoreanNewsSummaryPrincipleTests(unittest.TestCase):
    def test_fact_first_natural_korean_passes(self) -> None:
        summary = (
            "금융당국이 8월 21일부터 레버리지 ETF 투자한도를 100만원으로 제한한다. "
            "기존 한도는 300만원이었다."
        )
        self.assertEqual(summary_style_issues(summary), ())

    def test_translationese_is_rejected(self) -> None:
        self.assertIn("TRANSLATIONESE", summary_style_issues("정부가 규제 강화 결정을 내렸다."))
        self.assertFalse(
            is_usable_synthesis(
                "정부, 규제 강화",
                "정부가 규제 강화 결정을 내렸다.",
                source_count=2,
            )
        )

    def test_repeated_subject_is_rejected_when_subject_did_not_change(self) -> None:
        issues = summary_style_issues(
            "삼성전자는 2분기 영업이익이 20% 늘었다. 삼성전자는 설비투자도 확대했다."
        )
        self.assertIn("REPEATED_SUBJECT", issues)

    def test_repeated_subject_check_is_adjacent_only(self) -> None:
        issues = summary_style_issues(
            "삼성전자는 2분기 영업이익이 20% 늘었다. 설비투자도 확대했다. 삼성전자는 하반기 투자를 유지한다."
        )
        self.assertNotIn("REPEATED_SUBJECT", issues)

    def test_unattributed_abstract_evaluation_and_forced_conclusion_are_rejected(self) -> None:
        self.assertIn("ABSTRACT_EVALUATION", summary_style_issues("우려가 제기됐다."))
        self.assertIn(
            "REDUNDANT_CONCLUSION",
            summary_style_issues("회사는 투자를 2조원으로 늘렸다. 종합하면 중요한 변화다."),
        )

    def test_live_validator_uses_the_same_style_contract(self) -> None:
        validator = Path("scripts/validate_live_acceptance.py").read_text(encoding="utf-8")
        self.assertIn("summary_style_issues(summary)", validator)

    def test_policy_document_contains_all_seven_locked_rules(self) -> None:
        policy = Path("docs/news-summary-korean-principles.md").read_text(encoding="utf-8")
        for number in range(1, 8):
            self.assertIn(f"## {number}.", policy)


if __name__ == "__main__":
    unittest.main()
