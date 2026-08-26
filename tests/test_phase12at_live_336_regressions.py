from __future__ import annotations

from datetime import datetime, timezone
import unittest

from insight_desk.semantic.visible_identity import visible_event_redundant
from insight_desk.story_admission import (
    StoryAdmissionReason,
    StoryAdmissionStage,
    evaluate_story_admission,
)


NOW = datetime(2026, 8, 26, 3, 30, tzinfo=timezone.utc)


def visible(*, topic: str, headline: str, summary: str):
    return evaluate_story_admission(
        topic=topic,
        headline=headline,
        summary=summary,
        source_text=summary,
        stage=StoryAdmissionStage.VISIBLE,
        now=NOW,
    )


class Live336ReferentialCompletenessRegressions(unittest.TestCase):
    def test_live_event_object_reference_without_antecedent_is_not_standalone(self) -> None:
        decision = visible(
            topic="AI·테크",
            headline="LG화학, 반도체 업체 접점 확대 계획",
            summary=(
                "LG화학은 이번 행사를 계기로 주요 반도체 제조사와 OSAT, "
                "기판·패키징 기업과의 접점을 확대한다는 계획이다."
            ),
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.STANDALONE_COMPLETENESS, decision.reasons)

    def test_named_event_antecedent_can_resolve_later_event_reference(self) -> None:
        decision = visible(
            topic="AI·테크",
            headline="LG화학, 반도체 행사 개최",
            summary=(
                "LG화학은 26일 반도체 행사를 개최했다. "
                "이번 행사를 계기로 주요 반도체 업체와 접점을 확대한다."
            ),
        )
        self.assertTrue(decision.accepted, decision.reasons)


class Live336ExplanatoryStateRegressions(unittest.TestCase):
    def test_live_unattributed_explanatory_factor_is_not_an_event(self) -> None:
        decision = visible(
            topic="경제·투자",
            headline="수요 측 인플레이션 압력 꼽힌다",
            summary=(
                "반도체 경기 호황에 따른 가파른 성장세와 이에 따른 "
                "수요 측 인플레이션 압력이 꼽힌다"
            ),
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.NON_EVENT_DESCRIPTION, decision.reasons)

    def test_current_attributed_statement_can_name_an_explanatory_factor(self) -> None:
        decision = visible(
            topic="경제·투자",
            headline="한국은행, 수요 측 인플레이션 압력 주요 요인으로 지목",
            summary=(
                "한국은행은 26일 보고서에서 반도체 경기 호황에 따른 "
                "수요 측 인플레이션 압력을 주요 요인으로 꼽았다."
            ),
        )
        self.assertTrue(decision.accepted, decision.reasons)


class Live336StatisticalReleaseIdentityRegressions(unittest.TestCase):
    def test_live_same_statistical_release_sibling_metrics_are_redundant(self) -> None:
        self.assertTrue(
            visible_event_redundant(
                topic_id="economy",
                prior_headline="7월 주택담보대출 금리 연 4.48% 기록",
                prior_summary=(
                    "한국은행의 7월 금융기관 가중평균 금리 통계에 따르면 "
                    "신규 취급액 기준 주택담보대출 금리는 전달 대비 0.12%p 상승한 "
                    "연 4.48%로 나타났습니다."
                ),
                candidate_headline="7월 예금은행 가계 대출 금리 연 4.64%로 상승",
                candidate_summary=(
                    "한국은행이 오늘(26일) 발표한 금융기관 가중평균 금리 통계에 따르면, "
                    "지난 7월 신규 취급액 기준 예금은행 가계 대출 가중평균금리는 "
                    "전월 대비 0.14%포인트 상승한 연 4.64%를 기록했습니다."
                ),
            )
        )

    def test_same_release_label_for_different_reference_months_is_not_redundant(self) -> None:
        self.assertFalse(
            visible_event_redundant(
                topic_id="economy",
                prior_headline="6월 주택담보대출 금리 연 4.36% 기록",
                prior_summary="한국은행의 6월 금융기관 가중평균 금리 통계에 따르면 주택담보대출 금리는 연 4.36%였다.",
                candidate_headline="7월 주택담보대출 금리 연 4.48% 기록",
                candidate_summary="한국은행의 7월 금융기관 가중평균 금리 통계에 따르면 주택담보대출 금리는 연 4.48%였다.",
            )
        )

    def test_different_statistical_releases_in_same_month_are_not_redundant(self) -> None:
        self.assertFalse(
            visible_event_redundant(
                topic_id="economy",
                prior_headline="7월 가계대출 금리 상승",
                prior_summary="한국은행의 7월 금융기관 가중평균 금리 통계에 따르면 가계대출 금리가 상승했다.",
                candidate_headline="7월 소비자심리지수 상승",
                candidate_summary="한국은행의 7월 소비자동향조사 통계에 따르면 소비자심리지수가 상승했다.",
            )
        )


if __name__ == "__main__":
    unittest.main()
