from __future__ import annotations

from datetime import datetime, timezone
import unittest

from insight_desk.story_admission import (
    StoryAdmissionReason,
    StoryAdmissionStage,
    evaluate_story_admission,
)


NOW = datetime(2026, 8, 25, 8, 0, tzinfo=timezone.utc)


class Phase12AFLive258Regressions(unittest.TestCase):
    def decide(
        self,
        *,
        topic: str,
        headline: str,
        summary: str,
        source_text: str = "",
    ):
        return evaluate_story_admission(
            topic=topic,
            headline=headline,
            summary=summary,
            source_text=source_text or summary,
            stage=StoryAdmissionStage.VISIBLE,
            now=NOW,
        )

    def test_program_components_cannot_replace_the_current_program_event(self) -> None:
        decision = self.decide(
            topic="AI·테크",
            headline="10회·30시간 취업 교육 과정 개설",
            summary=(
                "교육은 총 10회, 30시간 과정으로 진행되며 ICRU 진단도구를 활용한 "
                "퍼스널브랜딩·진로목표 설정, 기업 및 직무분석, 생성형 AI를 활용한 "
                "자기소개서 작성과 면접 준비, AI 역량검사 실전 대비 등을 포함한다."
            ),
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.NON_EVENT_DESCRIPTION, decision.reasons)

    def test_method_description_cannot_replace_the_current_agreement_event(self) -> None:
        decision = self.decide(
            topic="AI·테크",
            headline="LS ITC·모티프테크놀로지스, 제조 현장 AI 결합 방식",
            summary=(
                "LS ITC가 보유한 제조 현장 IT·OT 구축·운영 경험과 "
                "모티프테크놀로지스의 AI 파운데이션 모델 기술력을 결합해 실제 제조 "
                "공정에 적용 가능한 AI 활용 과제를 발굴·검증하는 방식이다."
            ),
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.NON_EVENT_DESCRIPTION, decision.reasons)

    def test_long_forecast_requires_visible_attribution(self) -> None:
        decision = self.decide(
            topic="경제·투자",
            headline="중국 반도체 자본지출, 2030년 820억달러 전망",
            summary=(
                "중국의 반도체 자본적 지출은 연평균 10%대 증가가 예상되며 "
                "2030년에는 820억달러에 육박할 것으로 전망됐다. 고성능 메모리 및 "
                "첨단공정 생산능력 확충이 투자 확대의 주요 배경이다."
            ),
        )
        self.assertFalse(decision.accepted)
        self.assertIn(
            StoryAdmissionReason.FORECAST_ATTRIBUTION_STANDALONE_UNRESOLVED,
            decision.reasons,
        )

    def test_unattributed_market_explanation_is_not_a_daily_event(self) -> None:
        decision = self.decide(
            topic="경제·투자",
            headline="주담대 금리 동결·저하 불투명",
            summary=(
                "한국은행 기준금리 동결 전망이 79%로 높아졌음에도 주담대 금리는 "
                "바로 내려오지 않는다. 은행들이 기준금리 방향을 관망하는 상황이라 "
                "단기간 내 대출 금리가 크게 떨어질 가능성은 낮다."
            ),
        )
        self.assertFalse(decision.accepted)
        self.assertTrue(
            StoryAdmissionReason.NON_EVENT_DESCRIPTION in decision.reasons
            or StoryAdmissionReason.FORECAST_ATTRIBUTION_STANDALONE_UNRESOLVED
            in decision.reasons
        )

    def test_unquantified_market_consensus_is_not_a_daily_event(self) -> None:
        decision = self.decide(
            topic="경제·투자",
            headline="한국은행 8월 기준금리, ‘동결’ 전망 우세",
            summary=(
                "한국은행의 8월 기준금리 결정을 이틀 앞두고 시장 무게중심이 "
                "'동결'로 기울고 있다. 물가 흐름이 안정되고 주택시장 과열과 "
                "가계부채 문제도 단기간 내 금리 인상이 필요하지 않다는 판단이 우세하다."
            ),
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.NON_EVENT_DESCRIPTION, decision.reasons)

    def test_stale_primary_evidence_cannot_be_hidden_by_date_free_rewrite(self) -> None:
        decision = self.decide(
            topic="엔터·음악·K-POP",
            headline="SM Universe 강사진의 K-pop 안무 교육 실시",
            summary=(
                "K-pop 댄스 프로그램에서 SM Universe 강사진이 안무 교육을 진행했으며, "
                "청소년들은 팀별 공연 준비를 통해 협동심과 자신감을 함양했다."
            ),
            source_text=(
                "지난 10일 SM Universe에서 청소년 대상 K-pop 진로체험 프로그램을 "
                "운영했다. SM Universe 강사진이 안무 교육을 진행했다."
            ),
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.FRESHNESS, decision.reasons)

    def test_current_event_may_keep_descriptive_details_as_background(self) -> None:
        cases = (
            (
                "AI·테크",
                "한국교통대, AI 기반 실전 취업 프로그램 운영",
                "한국교통대는 25일 AI 기반 실전 취업 프로그램을 운영한다고 밝혔다. "
                "교육은 10회, 30시간 과정으로 자기소개서 작성과 AI 역량검사 대비 등을 포함한다.",
            ),
            (
                "AI·테크",
                "LS ITC·모티프테크놀로지스, 제조 AI 업무협약 체결",
                "LS ITC와 모티프테크놀로지스는 24일 제조 AI 업무협약을 체결했다. "
                "양사는 IT·OT 경험과 AI 모델 기술을 결합해 현장 적용 과제를 검증할 계획이다.",
            ),
            (
                "경제·투자",
                "골드만삭스, 중국 반도체 자본지출 2030년 820억달러 전망",
                "골드만삭스는 최근 보고서에서 중국 반도체 자본지출이 2030년 "
                "820억달러에 육박할 것으로 전망했다. 첨단공정 증설은 전망의 배경이다.",
            ),
            (
                "경제·투자",
                "금투협 조사, 8월 기준금리 동결 전망 79%",
                "금융투자협회가 25일 발표한 조사에서 응답자의 79%가 기준금리 "
                "동결을 전망했다. 시장에서는 주택과 가계부채 흐름도 함께 주시하고 있다.",
            ),
        )
        for topic, headline, summary in cases:
            with self.subTest(headline=headline):
                self.assertTrue(
                    self.decide(topic=topic, headline=headline, summary=summary).accepted
                )

    def test_current_event_is_not_rejected_for_old_background(self) -> None:
        decision = self.decide(
            topic="엔터·음악·K-POP",
            headline="A기획사, 25일 K-pop 교육 프로그램 개편안 발표",
            summary=(
                "A기획사는 25일 K-pop 교육 프로그램 개편안을 발표했다. "
                "기존 프로그램은 지난 10일에도 안무 교육을 진행했다."
            ),
            source_text=(
                "A기획사는 25일 K-pop 교육 프로그램 개편안을 발표했다. "
                "기존 프로그램은 지난 10일에도 안무 교육을 진행했다."
            ),
        )
        self.assertTrue(decision.accepted)

    def test_live_258_current_events_remain_accepted(self) -> None:
        cases = (
            (
                "경제·투자",
                "국내 증시, 개인·기관 순매수로 상승 마감",
                "25일 국내 증시는 개인과 기관의 순매수가 유입되며 상승 마감했다. "
                "주요 지수 모두 상승세를 보였고 일부 대형주는 하락했다.",
            ),
            (
                "엔터·음악·K-POP",
                "소연, 9월 초 솔로 앨범 발매 예정",
                "그룹 아이들 멤버 소연이 오는 9월 초 솔로 앨범을 발매할 예정이다. "
                "2021년 미니 1집 이후 약 5년 만의 솔로 컴백이다.",
            ),
            (
                "KBO·한화 이글스",
                "한화, SSG전 선발 라인업 확정",
                "한화는 25일 SSG전을 앞두고 선발 라인업을 확정했다. "
                "인천 SSG랜더스필드에서 시즌 13번째 맞대결을 펼친다.",
            ),
        )
        for topic, headline, summary in cases:
            with self.subTest(headline=headline):
                self.assertTrue(
                    self.decide(topic=topic, headline=headline, summary=summary).accepted
                )


if __name__ == "__main__":
    unittest.main()
