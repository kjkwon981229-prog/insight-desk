from __future__ import annotations

from datetime import datetime, timezone
import unittest

from insight_desk.core import CandidateEvent, EvidenceField, EvidenceSpan, EventFact
from insight_desk.generation import (
    GeneratedDraft,
    GenerationRequest,
    PreservationIssueCode,
    validate_preservation,
)
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


def dated_request(*, event_id: str, source: str, subject: str, action: str, event_date: str) -> GenerationRequest:
    evidence_id = f"ev:{event_id}"
    article_id = f"article:{event_id}"
    fact_id = f"fact:{event_id}"
    span = EvidenceSpan(
        evidence_id=evidence_id,
        article_id=article_id,
        field=EvidenceField.BODY,
        start=0,
        end=len(source),
        text=source,
    )
    fact = EventFact(
        fact_id=fact_id,
        subject=subject,
        action=action,
        event_date=event_date,
        evidence_ids=(evidence_id,),
    )
    event = CandidateEvent(
        event_id=event_id,
        topic_id="kpop",
        fact_ids=(fact_id,),
        article_ids=(article_id,),
    )
    return GenerationRequest(
        event=event,
        facts={fact_id: fact},
        evidence={evidence_id: span},
    )


class Live387MarketAttentionMorphologyRegressions(unittest.TestCase):
    def test_live_nominalized_market_attention_with_stative_jjollyeo_is_not_event(self) -> None:
        decision = visible(
            topic="경제·투자",
            headline="8월 기준금리 결정 이후 향후 경로에 집중",
            summary="시장의 관심은 8월 기준금리 결정 자체보다 향후 금리 경로에 쏠려 있다.",
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.NON_EVENT_DESCRIPTION, decision.reasons)

    def test_generalized_nominalized_market_attention_stative_surface_is_not_event(self) -> None:
        decision = visible(
            topic="경제·투자",
            headline="통화정책 회의 이후 금리 전망에 집중",
            summary="투자자들의 관심은 회의 결과 자체보다 향후 금리 전망에 모여 있다.",
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.NON_EVENT_DESCRIPTION, decision.reasons)

    def test_attributed_current_market_analysis_remains_publishable(self) -> None:
        decision = visible(
            topic="경제·투자",
            headline="한국은행, 26일 향후 금리 경로 설명",
            summary="한국은행은 26일 향후 금리 경로를 설명하며 물가와 금융안정 여건을 함께 보겠다고 밝혔다.",
        )
        self.assertTrue(decision.accepted, decision.reasons)


class Live387AtmosphereMorphologyRegressions(unittest.TestCase):
    def test_live_atmosphere_only_scene_with_heat_showed_surface_is_not_event(self) -> None:
        decision = visible(
            topic="KPOP",
            headline="K-POP 콘서트장 방불케 하는 대강당 열기",
            summary="대강당이 실제 K-POP 콘서트장 같은 뜨거운 열기를 보였다.",
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.NON_EVENT_DESCRIPTION, decision.reasons)

    def test_generalized_atmosphere_only_scene_surface_is_not_event(self) -> None:
        decision = visible(
            topic="KPOP",
            headline="공연장 같은 객석 분위기",
            summary="객석은 실제 K-POP 공연장 같은 뜨거운 분위기를 연출했다.",
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.NON_EVENT_DESCRIPTION, decision.reasons)

    def test_named_current_performance_remains_publishable(self) -> None:
        decision = visible(
            topic="KPOP",
            headline="레드벨벳, 26일 K-POP 무대 공연",
            summary="레드벨벳은 26일 K-POP 무대에서 신곡을 공연하며 관객들과 만났다.",
        )
        self.assertTrue(decision.accepted, decision.reasons)


class Live387InheritedEventDatePreservationRegressions(unittest.TestCase):
    def test_live_inherited_event_date_cannot_disappear_from_visible_draft(self) -> None:
        item = dated_request(
            event_id="event:live387-gamix",
            source="가믹스는 에이티즈 멤버의 댄스 챌린지를 따라 하는 영상을 올렸다.",
            subject="가믹스",
            action="에이티즈 멤버의 댄스 챌린지를 따라 하는 영상을 올렸다",
            event_date="2026-08-20",
        )
        draft = GeneratedDraft(
            event_id=item.event.event_id,
            headline="가믹스, 에이티즈 멤버 댄스 챌린지 영상 올려",
            summary="가믹스는 에이티즈 멤버의 댄스 챌린지를 따라 하는 영상을 올렸다.",
            evidence_ids=item.evidence_ids,
        )
        report = validate_preservation(item, draft)
        self.assertFalse(report.accepted)
        self.assertIn(PreservationIssueCode.MISSING_EVENT_DATE, {issue.code for issue in report.issues})

    def test_generalized_inherited_event_date_cannot_be_erased(self) -> None:
        item = dated_request(
            event_id="event:inherited-date-generalized",
            source="가수 A는 챌린지 영상을 자신의 계정에 올렸다.",
            subject="가수 A",
            action="챌린지 영상을 자신의 계정에 올렸다",
            event_date="2026-08-20",
        )
        draft = GeneratedDraft(
            event_id=item.event.event_id,
            headline="가수 A, 챌린지 영상 공개",
            summary="가수 A는 챌린지 영상을 자신의 계정에 올렸다.",
            evidence_ids=item.evidence_ids,
        )
        report = validate_preservation(item, draft)
        self.assertFalse(report.accepted)
        self.assertIn(PreservationIssueCode.MISSING_EVENT_DATE, {issue.code for issue in report.issues})

    def test_explicit_source_event_date_preserved_remains_accepted(self) -> None:
        item = dated_request(
            event_id="event:explicit-date-positive",
            source="가수 A는 20일 챌린지 영상을 자신의 계정에 올렸다.",
            subject="가수 A",
            action="20일 챌린지 영상을 자신의 계정에 올렸다",
            event_date="2026-08-20",
        )
        draft = GeneratedDraft(
            event_id=item.event.event_id,
            headline="가수 A, 20일 챌린지 영상 공개",
            summary="가수 A는 20일 챌린지 영상을 자신의 계정에 올렸다.",
            evidence_ids=item.evidence_ids,
        )
        report = validate_preservation(item, draft)
        self.assertTrue(report.accepted, report.issues)


if __name__ == "__main__":
    unittest.main()
