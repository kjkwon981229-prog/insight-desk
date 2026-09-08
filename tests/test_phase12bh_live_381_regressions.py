from __future__ import annotations

from datetime import datetime, timezone
import unittest

from insight_desk.story_admission import (
    StoryAdmissionReason,
    StoryAdmissionStage,
    evaluate_story_admission,
)


NOW = datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc)


def visible(*, topic: str, headline: str, summary: str):
    return evaluate_story_admission(
        topic=topic,
        headline=headline,
        summary=summary,
        source_text=summary,
        stage=StoryAdmissionStage.VISIBLE,
        now=NOW,
    )


class Live381StaticCompanyIdentityRegressions(unittest.TestCase):
    def test_static_company_identity_cannot_replace_current_event(self) -> None:
        cases = (
            (
                "세스텍의 반도체·디스플레이용 로봇 및 물류시스템",
                "세스텍은 반도체와 디스플레이 공정에 사용되는 로봇과 자율주행로봇(AMR) 기반 물류시스템을 제조하는 기업이다.",
            ),
            (
                "로보테크의 AI 물류 로봇 시스템",
                "로보테크는 AI 기반 자율주행로봇과 물류시스템을 제조하는 기업이다.",
            ),
        )
        for headline, summary in cases:
            with self.subTest(summary=summary):
                decision = visible(topic="AI·테크", headline=headline, summary=summary)
                self.assertFalse(decision.accepted)
                self.assertIn(StoryAdmissionReason.NON_EVENT_DESCRIPTION, decision.reasons)

    def test_current_company_event_with_identity_background_remains_publishable(self) -> None:
        decision = visible(
            topic="AI·테크",
            headline="세스텍, 26일 이달의 우수벤처 선정",
            summary=(
                "벤처기업협회는 26일 세스텍을 이달의 우수벤처로 선정했다. "
                "세스텍은 반도체와 디스플레이 공정용 로봇을 제조하는 기업이다."
            ),
        )
        self.assertTrue(decision.accepted, decision.reasons)


class Live381ReferentialComparativeFragmentRegressions(unittest.TestCase):
    def test_unscoped_comparative_fragment_is_not_standalone(self) -> None:
        cases = (
            (
                "하락폭이 축소됐다",
                "다만 오후 들어서는 금통위의 기준금리 결정을 앞둔 경계감이 커지면서 국고채 금리의 하락폭이 축소됐다.",
            ),
            (
                "상승폭이 확대됐다",
                "그러나 장 후반에는 외국인 매수세가 유입되면서 주가지수의 상승폭이 확대됐다.",
            ),
        )
        for headline, summary in cases:
            with self.subTest(headline=headline):
                decision = visible(topic="경제·투자", headline=headline, summary=summary)
                self.assertFalse(decision.accepted)
                self.assertIn(StoryAdmissionReason.STANDALONE_COMPLETENESS, decision.reasons)

    def test_scoped_current_market_move_remains_publishable(self) -> None:
        decision = visible(
            topic="경제·투자",
            headline="국고채 3년물 금리 하락폭 26일 오후 축소",
            summary="26일 오후 국고채 3년물 금리는 오전보다 낙폭을 줄여 전일 대비 2.1bp 하락한 3.71%를 기록했다.",
        )
        self.assertTrue(decision.accepted, decision.reasons)


class Live381NominalizedMarketAttentionRegressions(unittest.TestCase):
    def test_nominalized_generic_market_attention_state_is_not_current_event(self) -> None:
        cases = (
            (
                "8월 기준금리 결정 이후 향후 경로에 집중된 시장 관심",
                "시장의 관심은 8월 기준금리 결정 자체보다 향후 금리 경로로 향하고 있다.",
            ),
            (
                "실적 발표 이후 전망에 집중된 투자자 관심",
                "투자자들의 관심은 이번 실적 자체보다 향후 실적 전망으로 향하고 있다.",
            ),
        )
        for headline, summary in cases:
            with self.subTest(summary=summary):
                decision = visible(topic="경제·투자", headline=headline, summary=summary)
                self.assertFalse(decision.accepted)
                self.assertIn(StoryAdmissionReason.NON_EVENT_DESCRIPTION, decision.reasons)

    def test_attributed_current_market_analysis_remains_publishable(self) -> None:
        decision = visible(
            topic="경제·투자",
            headline="한국은행, 26일 향후 금리 경로 설명",
            summary="한국은행은 26일 통화정책 설명자료를 발표하며 향후 금리 경로의 주요 변수를 설명했다.",
        )
        self.assertTrue(decision.accepted, decision.reasons)


class Live381AtmosphereOnlyKpopRegressions(unittest.TestCase):
    def test_atmosphere_only_scene_cannot_replace_kpop_event(self) -> None:
        cases = (
            (
                "K-POP 콘서트장 방불케 한 강당 열기",
                "강렬한 비트와 화려한 조명이 더해진 강당이 실제 K-POP 콘서트장을 방불케 할 정도로 뜨거운 열기로 가득 찼다.",
            ),
            (
                "K-POP 공연장 방불케 한 현장 분위기",
                "화려한 조명과 음악이 더해진 현장은 K-POP 공연장을 방불케 할 정도로 뜨거운 열기로 가득 찼다.",
            ),
        )
        for headline, summary in cases:
            with self.subTest(summary=summary):
                decision = visible(topic="엔터·음악·K-POP", headline=headline, summary=summary)
                self.assertFalse(decision.accepted)
                self.assertIn(StoryAdmissionReason.NON_EVENT_DESCRIPTION, decision.reasons)

    def test_named_current_kpop_performance_event_remains_publishable(self) -> None:
        decision = visible(
            topic="엔터·음악·K-POP",
            headline="레드벨벳, 26일 K-POP 페스티벌 무대 공연",
            summary="레드벨벳은 26일 서울에서 열린 K-POP 페스티벌 무대에 올라 신곡 두 곡을 공연했다.",
        )
        self.assertTrue(decision.accepted, decision.reasons)


class Live381PastContentRepromotionRegressions(unittest.TestCase):
    def test_past_content_cannot_be_repromoted_as_fresh_release(self) -> None:
        cases = (
            (
                "슬기, 레드벨벳 컴백 준비 브이로그 공개",
                "슬기는 개인 유튜브 채널을 통해 레드벨벳 여름 미니앨범 'Velvet Summer'의 컴백 준비 과정을 담은 브이로그를 선보이며 팬들과 소통했다.",
            ),
            (
                "가수 A, 컴백 준비 영상 공개",
                "가수 A는 개인 유튜브 채널을 통해 컴백 준비 과정을 담은 영상을 선보이며 팬들과 소통했다.",
            ),
        )
        for headline, summary in cases:
            with self.subTest(headline=headline):
                decision = visible(topic="엔터·음악·K-POP", headline=headline, summary=summary)
                self.assertFalse(decision.accepted)
                self.assertIn(StoryAdmissionReason.STANDALONE_COMPLETENESS, decision.reasons)

    def test_explicit_current_content_release_remains_publishable(self) -> None:
        decision = visible(
            topic="엔터·음악·K-POP",
            headline="가수 A, 26일 컴백 준비 영상 공개",
            summary="가수 A는 26일 개인 유튜브 채널에 컴백 준비 과정을 담은 새 영상을 공개했다.",
        )
        self.assertTrue(decision.accepted, decision.reasons)


if __name__ == "__main__":
    unittest.main()
