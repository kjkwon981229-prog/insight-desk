from __future__ import annotations

from datetime import datetime, timezone
import unittest

from insight_desk.semantic.statistical_identity import same_statistical_release_fingerprint
from insight_desk.semantic.visible_identity import visible_event_redundant
from insight_desk.story_admission import (
    StoryAdmissionReason,
    StoryAdmissionStage,
    evaluate_story_admission,
)


NOW = datetime(2026, 8, 26, 4, 40, tzinfo=timezone.utc)


def visible(*, topic: str, headline: str, summary: str):
    return evaluate_story_admission(
        topic=topic,
        headline=headline,
        summary=summary,
        source_text=summary,
        stage=StoryAdmissionStage.VISIBLE,
        now=NOW,
    )


class Live346OfficialReleaseTitleRegressions(unittest.TestCase):
    PRIOR_HEADLINE = "금리 선택 관련 김성준 한국은행 팀장 설명"
    PRIOR_SUMMARY = (
        "김성준 한국은행 금융통계팀장은 변동금리보다 고정금리가 높아 "
        "소비자들이 당장 낮은 금리를 선택하는 경향이 있다고 밝혔다."
    )
    CANDIDATE_HEADLINE = "7월 주택담보대출 고정금리 비중 31.9%로 하락"
    CANDIDATE_SUMMARY = (
        "한국은행이 26일 발표한 2026년 7월 금융기관 가중평균금리에 따르면, "
        "7월 신규취급 주택담보대출 중 고정금리 비중은 31.9%로 "
        "전월 대비 5.8%포인트 감소했다."
    )
    PRIOR_SOURCE = (
        "한국은행이 26일 발표한 ‘2026년 7월 금융기관 가중평균금리’에 따르면 "
        "7월 주택담보대출 중 고정금리 비중은 31.9%로 낮아졌다. "
        "김성준 한국은행 금융통계팀장은 변동금리보다 고정금리가 높아 "
        "소비자들이 낮은 금리를 선택하는 유인이 크다고 설명했다."
    )
    CANDIDATE_SOURCE = (
        "한국은행이 26일 발표한 ‘2026년 7월 금융기관 가중평균금리’에 따르면 "
        "7월 주택담보대출 중 고정금리 비중은 31.9%로 전월보다 5.8%포인트 낮아졌다."
    )

    def test_live_same_official_release_title_dedupes_without_literal_statistics_word(self) -> None:
        self.assertTrue(
            visible_event_redundant(
                topic_id="economy",
                prior_headline=self.PRIOR_HEADLINE,
                prior_summary=self.PRIOR_SUMMARY,
                candidate_headline=self.CANDIDATE_HEADLINE,
                candidate_summary=self.CANDIDATE_SUMMARY,
                prior_source_text=self.PRIOR_SOURCE,
                candidate_source_text=self.CANDIDATE_SOURCE,
            )
        )

    def test_official_release_title_still_requires_same_reference_month(self) -> None:
        self.assertFalse(
            same_statistical_release_fingerprint(
                self.PRIOR_SOURCE.replace("7월", "6월"),
                self.CANDIDATE_SOURCE,
            )
        )

    def test_official_release_title_still_requires_same_exact_release_name(self) -> None:
        self.assertFalse(
            same_statistical_release_fingerprint(
                self.PRIOR_SOURCE,
                self.CANDIDATE_SOURCE.replace(
                    "금융기관 가중평균금리", "소비자동향조사 결과"
                ),
            )
        )


class Live346PublisherBoilerplateRegressions(unittest.TestCase):
    def test_live_ai_preview_disclosure_prompt_and_byline_are_metadata_not_story(self) -> None:
        decision = visible(
            topic="KBO·한화 이글스",
            headline="AI 경기 분석 안내",
            summary=(
                "*위 내용은 생성형 AI로 예측한 경기 분석 "
                "[명령어 : 8월 26일 인천 SSG-한화 경기를 분석해줘=CHAT GPT] "
                "football1229@newspim.com"
            ),
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.METADATA, decision.reasons)

    def test_current_ai_prediction_service_launch_is_not_publisher_boilerplate(self) -> None:
        decision = visible(
            topic="AI·테크",
            headline="뉴스핌, 생성형 AI 경기예측 서비스 출시",
            summary="뉴스핌은 26일 생성형 AI로 경기 결과를 예측하는 서비스를 출시했다.",
        )
        self.assertTrue(decision.accepted, decision.reasons)


class Live346ComponentDescriptionRegressions(unittest.TestCase):
    def test_live_subexhibit_feature_description_is_not_the_parent_event(self) -> None:
        decision = visible(
            topic="엔터·음악·K-POP",
            headline="K-POP 팝업 전시 내 다국어 지원 AI 체험 제공",
            summary=(
                "K-POP 팝업 전시가 관람객에게 가상 아이돌 데뷔 과정을 경험하는 "
                "AI 몰입형 스토리텔링을 제공하며, 영어·중국어·일본어 안내를 지원한다."
            ),
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.NON_EVENT_DESCRIPTION, decision.reasons)

    def test_current_kpop_expo_opening_is_a_material_event(self) -> None:
        decision = visible(
            topic="엔터·음악·K-POP",
            headline="K-POP 포함 천안 K-컬처박람회, 9월 2일 개막",
            summary=(
                "천안시는 K-POP 전시를 포함한 K-컬처박람회를 "
                "9월 2일부터 독립기념관에서 개최한다고 26일 밝혔다."
            ),
        )
        self.assertTrue(decision.accepted, decision.reasons)


if __name__ == "__main__":
    unittest.main()
