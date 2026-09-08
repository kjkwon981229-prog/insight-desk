from __future__ import annotations

from dataclasses import dataclass
import unittest

from insight_desk.core import CandidateEvent, EvidenceField, EvidenceSpan, EventFact
from insight_desk.feed_quality import VisibleStoryIssue, visible_story_issues
from insight_desk.semantic.material import (
    MaterialEventReason,
    MaterialEventVerdict,
    assess_material_event,
)


@dataclass(frozen=True)
class _Token:
    tag: str = "VV"


class _PredicateMorphology:
    def analyze(self, text: str):
        del text
        return (_Token(),)


def _material(text: str, *, subject: str, action: str):
    span = EvidenceSpan(
        evidence_id="evidence:234",
        article_id="article:234",
        field=EvidenceField.BODY,
        start=0,
        end=len(text),
        text=text,
    )
    fact = EventFact(
        fact_id="fact:234",
        subject=subject,
        action=action,
        evidence_ids=(span.evidence_id,),
    )
    event = CandidateEvent(
        event_id="event:234",
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


class Daily234SameByteNegativeRegressions(unittest.TestCase):
    def test_last_month_rate_hike_repromotion_is_stale(self) -> None:
        headline = "한국은행, 기준금리 연 2.75%로 인상"
        summary = "한국은행은 지난달 기준금리를 연 2.50%에서 2.75%로 올렸다고 밝혔다."
        issues = visible_story_issues(
            topic="경제·투자",
            headline=headline,
            summary=summary,
        )
        self.assertIn(VisibleStoryIssue.STALE_DATED_CONTEXT, issues)
        assessment = _material(
            summary,
            subject="한국은행",
            action="지난달 기준금리를 연 2.50%에서 2.75%로 올렸다고 밝혔다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.DEFER)
        self.assertIn(
            assessment.reasons[0],
            (MaterialEventReason.STALE_DATED_CONTEXT, MaterialEventReason.STALE_EXPLICIT_PAST_EVENT),
        )

    def test_album_vocal_rap_description_is_descriptive_non_event(self) -> None:
        headline = "지젤, 일본 오리지널 앨범 속 보컬과 랩으로 존재감 입증"
        summary = (
            "지젤은 앨범에 수록된 'ATTITUDE'와 'In Halo' 등 일본 오리지널 곡들에서 "
            "한국어와 일본어를 자유롭게 오가는 랩과 보컬을 선보였다."
        )
        issues = visible_story_issues(
            topic="엔터·음악·K-POP",
            headline=headline,
            summary=summary,
        )
        self.assertIn(VisibleStoryIssue.NON_EVENT_ANALYTICAL_SUMMARY, issues)
        assessment = _material(
            summary,
            subject="지젤",
            action=(
                "앨범에 수록된 'ATTITUDE'와 'In Halo' 등 일본 오리지널 곡들에서 "
                "한국어와 일본어를 자유롭게 오가는 랩과 보컬을 선보였다"
            ),
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.DEFER)
        self.assertEqual(
            assessment.reasons,
            (MaterialEventReason.NON_EVENT_ANALYTICAL_JUDGMENT,),
        )

    def test_birthplace_and_group_role_profile_is_biographical_non_event(self) -> None:
        headline = "블랙핑크 리사의 주요 활동 및 역할"
        summary = (
            "태국 출신 가수이자 배우인 리사는 블랙핑크에서 메인댄서와 리드래퍼, "
            "서브보컬을 담당하고 있다."
        )
        issues = visible_story_issues(
            topic="엔터·음악·K-POP",
            headline=headline,
            summary=summary,
        )
        self.assertIn(VisibleStoryIssue.NON_EVENT_ANALYTICAL_SUMMARY, issues)
        assessment = _material(
            summary,
            subject="리사",
            action="블랙핑크에서 메인댄서와 리드래퍼, 서브보컬을 담당하고 있다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.DEFER)
        self.assertEqual(
            assessment.reasons,
            (MaterialEventReason.NON_EVENT_ANALYTICAL_JUDGMENT,),
        )

    def test_comma_terminated_track_list_headline_is_malformed_and_context_dependent(self) -> None:
        headline = (
            "가수 전유나의 동명 명곡을 샘플링한 힙합 R&B '다이아몬드 아워(Diamond Hour)', "
            "미니멀한 베이스 기반의 '원 모어 타임(One More Time)',"
        )
        summary = (
            "가수 전유나의 동명 명곡을 샘플링한 힙합 R&B '다이아몬드 아워(Diamond Hour)', "
            "미니멀한 베이스 기반의 '원 모어 타임(One More Time)', "
            "몽환적인 여름의 감상을 담은 '토크 투 미(Talk to me)' 등이 담겼다."
        )
        issues = visible_story_issues(
            topic="엔터·음악·K-POP",
            headline=headline,
            summary=summary,
        )
        self.assertIn(VisibleStoryIssue.MALFORMED_VISIBLE_TEXT, issues)
        self.assertIn(VisibleStoryIssue.CONTEXT_DEPENDENT_HEADLINE, issues)


class Daily234PositiveBoundaries(unittest.TestCase):
    def test_current_rate_decision_and_attributed_forecast_remain_material(self) -> None:
        cases = (
            (
                "한국은행은 오늘 기준금리를 2.75%에서 3.00%로 인상했다.",
                "한국은행",
                "오늘 기준금리를 2.75%에서 3.00%로 인상했다",
            ),
            (
                "BNP파리바는 오늘 한국은행이 기준금리를 동결할 것으로 내다봤다.",
                "BNP파리바",
                "오늘 한국은행이 기준금리를 동결할 것으로 내다봤다",
            ),
        )
        for text, subject, action in cases:
            with self.subTest(text=text):
                assessment = _material(text, subject=subject, action=action)
                self.assertIs(assessment.verdict, MaterialEventVerdict.MATERIAL)

    def test_actual_album_release_performance_and_record_remain_events(self) -> None:
        cases = (
            ("지젤은 24일 일본 오리지널 앨범을 발매했다.", "24일 일본 오리지널 앨범을 발매했다"),
            ("지젤은 24일 도쿄 콘서트에서 신곡을 공연했다.", "24일 도쿄 콘서트에서 신곡을 공연했다"),
            ("지젤은 신곡으로 오리콘 차트 1위를 기록했다.", "신곡으로 오리콘 차트 1위를 기록했다"),
        )
        for text, action in cases:
            with self.subTest(text=text):
                assessment = _material(text, subject="지젤", action=action)
                self.assertIs(assessment.verdict, MaterialEventVerdict.MATERIAL)

    def test_current_person_activity_event_remains_material(self) -> None:
        text = "리사는 24일 새 솔로 싱글을 공개했다."
        assessment = _material(
            text,
            subject="리사",
            action="24일 새 솔로 싱글을 공개했다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.MATERIAL)

    def test_complete_track_and_album_headlines_remain_visible(self) -> None:
        cases = (
            (
                "알파드라이브원, 미니 2집 발매",
                "알파드라이브원은 24일 미니 2집을 발매했다.",
            ),
            (
                "알파드라이브원 미니 2집에 '다이아몬드 아워' 수록",
                "알파드라이브원은 새 미니 2집에 '다이아몬드 아워'를 수록했다.",
            ),
        )
        for headline, summary in cases:
            with self.subTest(headline=headline):
                issues = visible_story_issues(
                    topic="엔터·음악·K-POP",
                    headline=headline,
                    summary=summary,
                )
                self.assertNotIn(VisibleStoryIssue.MALFORMED_VISIBLE_TEXT, issues)
                self.assertNotIn(VisibleStoryIssue.CONTEXT_DEPENDENT_HEADLINE, issues)


if __name__ == "__main__":
    unittest.main()
