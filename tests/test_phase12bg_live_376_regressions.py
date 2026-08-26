from __future__ import annotations

from datetime import datetime, timezone
import unittest

from insight_desk.story_admission import (
    StoryAdmissionReason,
    StoryAdmissionStage,
    evaluate_story_admission,
)


NOW = datetime(2026, 8, 26, 11, 5, tzinfo=timezone.utc)


def visible(*, topic: str, headline: str, summary: str):
    return evaluate_story_admission(
        topic=topic,
        headline=headline,
        summary=summary,
        source_text=summary,
        stage=StoryAdmissionStage.VISIBLE,
        now=NOW,
    )


class Live376RollingMarketStateRegressions(unittest.TestCase):
    def test_rolling_market_state_without_current_event_is_not_publishable(self) -> None:
        cases = (
            (
                "코스피 2주 연속 6500~7000선 등락",
                "코스피가 2주째 6500~7000선에서 등락을 반복하며 뚜렷한 방향을 잡지 못하고 있다.",
            ),
            (
                "원달러 환율 박스권 흐름 지속",
                "원달러 환율이 최근 3주째 1380~1420원 사이에서 오르내리며 방향성을 찾지 못하고 있다.",
            ),
        )
        for headline, summary in cases:
            with self.subTest(summary=summary):
                decision = visible(topic="경제·투자", headline=headline, summary=summary)
                self.assertFalse(decision.accepted)
                self.assertIn(StoryAdmissionReason.NON_EVENT_DESCRIPTION, decision.reasons)

    def test_current_quantified_market_event_remains_publishable(self) -> None:
        decision = visible(
            topic="경제·투자",
            headline="코스피, 26일 1.2% 상승 마감",
            summary="코스피는 26일 외국인 순매수에 힘입어 전 거래일보다 1.2% 상승 마감했다.",
        )
        self.assertTrue(decision.accepted, decision.reasons)


class Live376OrphanedReportingClauseRegressions(unittest.TestCase):
    def test_reporting_adnominal_clause_cannot_start_headline_without_actor(self) -> None:
        cases = (
            (
                "발표한 '2026년 7월 중 금융기관 가중평균 금리' 통계에 따르면, 7월 가계대출 금리는 연 4.64%로 올랐다",
                "26일 한국은행이 발표한 '2026년 7월 중 금융기관 가중평균 금리' 통계에 따르면, 7월 가계대출 금리는 연 4.64%로 전월보다 올랐다.",
            ),
            (
                "공개한 8월 수출입 동향 자료에 따르면 수출은 전년 동월 대비 8.2% 증가했다",
                "관세청이 26일 공개한 8월 수출입 동향 자료에 따르면 수출은 전년 동월 대비 8.2% 증가했다.",
            ),
        )
        for headline, summary in cases:
            with self.subTest(headline=headline):
                decision = visible(topic="경제·투자", headline=headline, summary=summary)
                self.assertFalse(decision.accepted)
                self.assertIn(StoryAdmissionReason.STANDALONE_COMPLETENESS, decision.reasons)

    def test_actor_preserving_reporting_headline_remains_publishable(self) -> None:
        decision = visible(
            topic="경제·투자",
            headline="한국은행, 7월 가계대출 금리 4.64%로 상승 발표",
            summary="한국은행은 26일 7월 예금은행 가계대출 금리가 연 4.64%로 올랐다고 발표했다.",
        )
        self.assertTrue(decision.accepted, decision.reasons)


class Live376GenericMarketAttentionRegressions(unittest.TestCase):
    def test_generic_market_attention_state_is_not_a_current_event(self) -> None:
        cases = (
            (
                "금리 경로에 관심 집중",
                "시장은 8월 기준금리 결정 자체보다 향후 금리 경로에 관심을 쏟고 있다.",
            ),
            (
                "투자자 관심, 향후 실적 전망으로 이동",
                "투자자들은 당장의 주가보다 다음 분기 실적 전망에 관심을 집중하고 있다.",
            ),
        )
        for headline, summary in cases:
            with self.subTest(summary=summary):
                decision = visible(topic="경제·투자", headline=headline, summary=summary)
                self.assertFalse(decision.accepted)
                self.assertIn(StoryAdmissionReason.NON_EVENT_DESCRIPTION, decision.reasons)

    def test_named_current_market_analysis_remains_publishable(self) -> None:
        decision = visible(
            topic="경제·투자",
            headline="한국은행, 향후 금리 경로 설명",
            summary="한국은행은 26일 통화정책방향 자료를 발표하며 향후 금리 경로의 주요 변수를 설명했다.",
        )
        self.assertTrue(decision.accepted, decision.reasons)


class Live376RetrospectivePromotionRegressions(unittest.TestCase):
    def test_retrospective_continuity_cannot_be_promoted_to_new_release_headline(self) -> None:
        cases = (
            (
                "슬기, 레드벨벳 'Velvet Summer' 컴백 브이로그 공개",
                "슬기는 개인 유튜브 채널을 통해 레드벨벳 'Velvet Summer' 컴백 준비 과정을 소개하는 브이로그를 선보이며 팬들과 소통해 왔다.",
            ),
            (
                "아티스트 A, 투어 비하인드 영상 공개",
                "아티스트 A는 개인 채널에서 투어 준비 과정을 담은 영상을 선보이며 팬들과 소통을 이어왔다.",
            ),
        )
        for headline, summary in cases:
            with self.subTest(headline=headline):
                decision = visible(topic="엔터·음악·K-POP", headline=headline, summary=summary)
                self.assertFalse(decision.accepted)
                self.assertIn(StoryAdmissionReason.STANDALONE_COMPLETENESS, decision.reasons)

    def test_explicit_current_release_remains_publishable(self) -> None:
        decision = visible(
            topic="엔터·음악·K-POP",
            headline="슬기, 레드벨벳 컴백 비하인드 영상 공개",
            summary="슬기는 26일 개인 유튜브 채널에 레드벨벳 컴백 비하인드 영상을 공개했다.",
        )
        self.assertTrue(decision.accepted, decision.reasons)


class Live376LeadingSectionChromeRegressions(unittest.TestCase):
    def test_leading_section_glyph_is_visible_publisher_chrome(self) -> None:
        cases = (
            (
                "◆신세계스퀘어엔 신인 그룹 데뷔 뮤비 공개",
                "신세계백화점 본점 신세계스퀘어가 신인 그룹의 데뷔 무대로도 활용된다.",
            ),
            (
                "◇신제품 소식…아이돌 협업 굿즈 공개",
                "브랜드는 아이돌 그룹과 협업한 굿즈를 공개했다.",
            ),
        )
        for headline, summary in cases:
            with self.subTest(headline=headline):
                decision = visible(topic="엔터·음악·K-POP", headline=headline, summary=summary)
                self.assertFalse(decision.accepted)
                self.assertIn(StoryAdmissionReason.METADATA, decision.reasons)

    def test_plain_event_headline_without_section_chrome_remains_publishable(self) -> None:
        decision = visible(
            topic="엔터·음악·K-POP",
            headline="신세계스퀘어, 신인 그룹 데뷔 뮤직비디오 공개",
            summary="신세계스퀘어는 26일 신인 그룹의 데뷔 뮤직비디오를 공개했다.",
        )
        self.assertTrue(decision.accepted, decision.reasons)


class Live376ParentlessFeatureRegressions(unittest.TestCase):
    def test_exhibition_feature_cannot_replace_named_parent_event(self) -> None:
        cases = (
            (
                "K-POP 팝업 전시, AI 가상 아이돌 데뷔 체험 지원",
                "K-POP 팝업 전시에서 관람객은 가상 아이돌 데뷔 과정을 체험하는 AI 몰입형 콘텐츠를 이용할 수 있으며, 영어·중국어·일본어 다국어 안내가 제공된다.",
            ),
            (
                "AI 체험관, 가상 아바타 제작 기능 제공",
                "AI 체험관에서 방문객은 가상 아바타를 제작하는 콘텐츠를 이용할 수 있으며 다국어 안내가 제공된다.",
            ),
        )
        for headline, summary in cases:
            with self.subTest(summary=summary):
                decision = visible(topic="엔터·음악·K-POP", headline=headline, summary=summary)
                self.assertFalse(decision.accepted)
                self.assertIn(StoryAdmissionReason.NON_EVENT_DESCRIPTION, decision.reasons)

    def test_named_current_parent_event_can_include_feature_detail(self) -> None:
        decision = visible(
            topic="엔터·음악·K-POP",
            headline="천안시, 2026 K-컬처박람회 9월 2일 개막",
            summary=(
                "천안시는 26일 2026 K-컬처박람회를 9월 2일부터 6일까지 개최한다고 밝혔다. "
                "K-POP 팝업 전시에서는 AI 가상 아이돌 데뷔 체험을 제공한다."
            ),
        )
        self.assertTrue(decision.accepted, decision.reasons)


if __name__ == "__main__":
    unittest.main()
