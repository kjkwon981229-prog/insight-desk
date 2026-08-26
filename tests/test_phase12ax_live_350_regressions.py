from __future__ import annotations

from datetime import datetime, timezone
import unittest

from insight_desk.story_admission import (
    StoryAdmissionReason,
    StoryAdmissionStage,
    evaluate_story_admission,
)


NOW = datetime(2026, 8, 26, 4, 55, tzinfo=timezone.utc)


def visible(*, topic: str, headline: str, summary: str):
    return evaluate_story_admission(
        topic=topic,
        headline=headline,
        summary=summary,
        source_text=summary,
        stage=StoryAdmissionStage.VISIBLE,
        now=NOW,
    )


class Live350BackgroundCapabilityRegressions(unittest.TestCase):
    def test_live_company_capability_profile_is_not_the_current_contract_event(self) -> None:
        decision = visible(
            topic="AI·테크",
            headline="다케야마, 100만점 이상 의료기기 취급",
            summary=(
                "다케야마가 의료소모품부터 수술지원 로봇까지 "
                "100만점 이상의 제품을 취급한다고 덧붙였다."
            ),
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.NON_EVENT_DESCRIPTION, decision.reasons)

    def test_current_named_distribution_contract_remains_an_event(self) -> None:
        decision = visible(
            topic="AI·테크",
            headline="제이엘케이, 일본 다케야마와 판매 대리점 계약",
            summary=(
                "의료 AI 기업 제이엘케이는 26일 일본 의료기기 전문기업 "
                "다케야마와 뇌졸중 AI 솔루션 판매 대리점 계약을 체결했다고 밝혔다."
            ),
        )
        self.assertTrue(decision.accepted, decision.reasons)


class Live350ExtractionChromeRegressions(unittest.TestCase):
    def test_live_timestamp_only_headline_is_metadata(self) -> None:
        decision = visible(
            topic="경제·투자",
            headline="- 입력 2026.08.26 13:41",
            summary="3%대로 오른 은행 예금금리가 7월에도 상승세를 보였다.",
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.METADATA, decision.reasons)

    def test_live_title_plus_square_bracket_byline_is_metadata(self) -> None:
        decision = visible(
            topic="경제·투자",
            headline="한은 기준금리 인상 시점, 8월 vs 10월 의견 분분",
            summary=(
                "한은 기준금리 인상 시점…'8월 vs 10월' 의견 분분 "
                "[뉴스웍스=허운연 기자] 3%대로 오른 은행 예금금리가 7월에도 상승세를 보였다."
            ),
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.METADATA, decision.reasons)

    def test_current_dated_rate_event_is_not_metadata(self) -> None:
        decision = visible(
            topic="경제·투자",
            headline="한국은행, 26일 기준금리 전망 설명",
            summary="한국은행은 26일 금융시장 상황과 향후 기준금리 경로를 설명했다.",
        )
        self.assertTrue(decision.accepted, decision.reasons)


class Live350AlbumNarrativeRegressions(unittest.TestCase):
    def test_live_context_free_album_story_synopsis_is_not_an_event(self) -> None:
        decision = visible(
            topic="엔터·음악·K-POP",
            headline="이야기가 앨범에 담겼다",
            summary=(
                "위기와 갈등을 마주한 연인들이 함께하는 순간을 "
                "‘축복(Bliss)’으로 받아들이는 이야기가 앨범에 담겼다."
            ),
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.NON_EVENT_DESCRIPTION, decision.reasons)

    def test_named_current_album_release_remains_an_event(self) -> None:
        decision = visible(
            topic="엔터·음악·K-POP",
            headline="엔하이픈, 미니 8집 THE SIN : BLISS 발매",
            summary=(
                "엔하이픈은 21일 미니 8집 'THE SIN : BLISS'를 발매하고 "
                "새 앨범 활동을 시작했다."
            ),
        )
        self.assertTrue(decision.accepted, decision.reasons)


if __name__ == "__main__":
    unittest.main()
