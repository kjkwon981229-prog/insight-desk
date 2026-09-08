from __future__ import annotations

from dataclasses import dataclass
import unittest

from insight_desk.core import CandidateEvent, EvidenceField, EvidenceSpan, EventFact
from insight_desk.feed_quality import VisibleStoryIssue, visible_story_issues
from insight_desk.semantic.material import MaterialEventVerdict, assess_material_event


@dataclass(frozen=True)
class _Token:
    tag: str = "VV"


class _PredicateMorphology:
    def analyze(self, text: str):
        del text
        return (_Token(),)


def _material(text: str, *, subject: str, action: str):
    span = EvidenceSpan(
        evidence_id="evidence:237",
        article_id="article:237",
        field=EvidenceField.BODY,
        start=0,
        end=len(text),
        text=text,
    )
    fact = EventFact(
        fact_id="fact:237",
        subject=subject,
        action=action,
        evidence_ids=(span.evidence_id,),
    )
    event = CandidateEvent(
        event_id="event:237",
        topic_id="fixture",
        fact_ids=(fact.fact_id,),
        article_ids=(span.article_id,),
    )
    return assess_material_event(
        event,
        facts={fact.fact_id: fact},
        evidence={span.evidence_id: span},
        morphology=_PredicateMorphology(),
    )


class Daily237SameByteNegativeRegressions(unittest.TestCase):
    def test_subjectless_resident_consultation_remainder_is_context_dependent(self) -> None:
        headline = "데이터센터 건설 신청이 잇따르자 어떤 기준을 적용할지를 주민들에게 묻겠다는 것이다"
        summary = (
            "인공지능(AI) 붐을 타고 데이터센터 건설 신청이 잇따르자 "
            "어떤 기준을 적용할지를 주민들에게 묻겠다는 것이다."
        )
        issues = visible_story_issues(topic="AI·테크", headline=headline, summary=summary)
        self.assertIn(VisibleStoryIssue.CONTEXT_DEPENDENT_HEADLINE, issues)

    def test_stale_headline_current_forecast_summary_is_mixed_event_binding(self) -> None:
        headline = "한국은행 기준금리 인상"
        summary = (
            "한국은행이 지난달 기준금리를 2.50%에서 2.75%로 올린 뒤 "
            "27일 금융통화위원회에서 추가 인상 가능성이 제기되어 "
            "강원지역 자영업자들의 금융비용 부담이 커질 전망이다."
        )
        issues = visible_story_issues(topic="경제·투자", headline=headline, summary=summary)
        self.assertIn(VisibleStoryIssue.MIXED_EVENT_SUMMARY, issues)
        assessment = _material(
            summary,
            subject="한국은행",
            action=(
                "지난달 기준금리를 2.50%에서 2.75%로 올린 뒤 27일 금융통화위원회에서 "
                "추가 인상 가능성이 제기되어 강원지역 자영업자들의 금융비용 부담이 커질 전망이다"
            ),
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.DEFER)

    def test_1950s_historical_background_is_stale_non_current_event(self) -> None:
        headline = "1950년대 미국 재무부의 금융억압 정책"
        summary = (
            "1950년대 미국은 재무부가 연준을 통제하며 금리를 인위적으로 낮게 묶어두는 한편, "
            "은행들에 국채 보유를 사실상 강제하는 강력한 금융억압 정책을 펼쳤다."
        )
        issues = visible_story_issues(topic="경제·투자", headline=headline, summary=summary)
        self.assertIn(VisibleStoryIssue.STALE_DATED_CONTEXT, issues)
        assessment = _material(
            summary,
            subject="1950년대 미국",
            action=(
                "재무부가 연준을 통제하며 금리를 인위적으로 낮게 묶어두는 한편, "
                "은행들에 국채 보유를 사실상 강제하는 강력한 금융억압 정책을 펼쳤다"
            ),
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.DEFER)

    def test_seventeen_day_old_bare_day_performance_is_stale(self) -> None:
        headline = "aespa, 고척스카이돔 대규모 콘서트 선보여"
        summary = (
            "aespa가 7일과 8일 서울 고척스카이돔에서 2026-27 월드투어 "
            "'SYNK : COMPLÆXITY' 포문을 열며 대규모 콘서트를 선보였다."
        )
        issues = visible_story_issues(topic="엔터·음악·K-POP", headline=headline, summary=summary)
        self.assertIn(VisibleStoryIssue.STALE_DATED_CONTEXT, issues)
        assessment = _material(
            summary,
            subject="aespa",
            action=(
                "7일과 8일 서울 고척스카이돔에서 2026-27 월드투어 'SYNK : COMPLÆXITY' "
                "포문을 열며 대규모 콘서트를 선보였다"
            ),
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.DEFER)

    def test_group_composition_and_popularity_profile_is_biographical_non_event(self) -> None:
        headline = "블랙핑크, 세계 투어와 음악 활동으로 글로벌 인기 확정"
        summary = (
            "블랙핑크는 지수·제니·로제·리사로 구성된 4인조 걸그룹으로, "
            "세계 투어와 다양한 음악 활동을 통해 글로벌 인기를 얻으며 "
            "K-POP을 대표하는 팀으로 자리매김했다."
        )
        issues = visible_story_issues(topic="엔터·음악·K-POP", headline=headline, summary=summary)
        self.assertIn(VisibleStoryIssue.NON_EVENT_ANALYTICAL_SUMMARY, issues)
        assessment = _material(
            summary,
            subject="블랙핑크",
            action=(
                "지수·제니·로제·리사로 구성된 4인조 걸그룹으로, 세계 투어와 다양한 음악 활동을 통해 "
                "글로벌 인기를 얻으며 K-POP을 대표하는 팀으로 자리매김했다"
            ),
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.DEFER)


class Daily237PositiveBoundaries(unittest.TestCase):
    def test_current_resident_consultation_with_explicit_actor_remains_material(self) -> None:
        headline = "새너제이시, 데이터센터 개발 기준 주민 의견수렴"
        summary = "새너제이시는 오늘 데이터센터 개발 기준을 마련하기 위해 주민 의견 청취회를 열었다."
        issues = visible_story_issues(topic="AI·테크", headline=headline, summary=summary)
        self.assertNotIn(VisibleStoryIssue.CONTEXT_DEPENDENT_HEADLINE, issues)
        assessment = _material(
            summary,
            subject="새너제이시",
            action="오늘 데이터센터 개발 기준을 마련하기 위해 주민 의견 청취회를 열었다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.MATERIAL)

    def test_current_rate_decision_and_attributed_forecast_remain_material(self) -> None:
        cases = (
            (
                "한국은행은 오늘 기준금리를 2.75%에서 3.00%로 인상했다.",
                "한국은행",
                "오늘 기준금리를 2.75%에서 3.00%로 인상했다",
            ),
            (
                "BNP파리바는 오늘 한국은행이 27일 기준금리를 동결할 것으로 전망했다.",
                "BNP파리바",
                "오늘 한국은행이 27일 기준금리를 동결할 것으로 전망했다",
            ),
        )
        for text, subject, action in cases:
            with self.subTest(text=text):
                assessment = _material(text, subject=subject, action=action)
                self.assertIs(assessment.verdict, MaterialEventVerdict.MATERIAL)

    def test_current_research_or_announcement_centered_on_history_remains_material(self) -> None:
        text = "서울대 연구팀은 오늘 1950년대 미국 금융억압 정책을 분석한 연구 결과를 발표했다."
        issues = visible_story_issues(
            topic="경제·투자",
            headline="서울대 연구팀, 1950년대 미국 금융억압 연구 결과 발표",
            summary=text,
        )
        self.assertNotIn(VisibleStoryIssue.STALE_DATED_CONTEXT, issues)
        assessment = _material(
            text,
            subject="서울대 연구팀",
            action="오늘 1950년대 미국 금융억압 정책을 분석한 연구 결과를 발표했다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.MATERIAL)

    def test_recent_and_upcoming_performances_remain_material(self) -> None:
        cases = (
            (
                "aespa는 오늘 서울 고척스카이돔에서 콘서트를 열었다.",
                "오늘 서울 고척스카이돔에서 콘서트를 열었다",
            ),
            (
                "aespa는 28일 서울 고척스카이돔에서 콘서트를 열 예정이다.",
                "28일 서울 고척스카이돔에서 콘서트를 열 예정이다",
            ),
        )
        for text, action in cases:
            with self.subTest(text=text):
                assessment = _material(text, subject="aespa", action=action)
                self.assertIs(assessment.verdict, MaterialEventVerdict.MATERIAL)

    def test_actual_release_performance_award_and_record_remain_events(self) -> None:
        cases = (
            ("블랙핑크는 오늘 새 싱글을 발매했다.", "오늘 새 싱글을 발매했다"),
            ("블랙핑크는 오늘 서울에서 신곡을 공연했다.", "오늘 서울에서 신곡을 공연했다"),
            ("블랙핑크는 오늘 음악 시상식에서 대상을 수상했다.", "오늘 음악 시상식에서 대상을 수상했다"),
            ("블랙핑크는 오늘 빌보드 차트 1위를 기록했다.", "오늘 빌보드 차트 1위를 기록했다"),
        )
        for text, action in cases:
            with self.subTest(text=text):
                assessment = _material(text, subject="블랙핑크", action=action)
                self.assertIs(assessment.verdict, MaterialEventVerdict.MATERIAL)


if __name__ == "__main__":
    unittest.main()
