from __future__ import annotations

import unittest

from insight_desk.core import (
    CandidateEvent,
    EvidenceField,
    EvidenceSpan,
    EventFact,
    TemporalState,
)
from insight_desk.generation import GeneratedDraft, GenerationRequest, validate_preservation


def request_for(
    *,
    event_id: str,
    topic_id: str,
    source: str,
    subject: str,
    action: str,
    event_date: str | None = None,
    participants: tuple[str, ...] = (),
    temporal_state: TemporalState | None = None,
) -> GenerationRequest:
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
        participants=participants,
        temporal_state=temporal_state,
        evidence_ids=(evidence_id,),
    )
    event = CandidateEvent(
        event_id=event_id,
        topic_id=topic_id,
        fact_ids=(fact_id,),
        article_ids=(article_id,),
    )
    return GenerationRequest(
        event=event,
        facts={fact_id: fact},
        evidence={evidence_id: span},
    )


def issue_codes(report) -> set[str]:
    return {getattr(issue.code, "value", str(issue.code)) for issue in report.issues}


class SourceEventIdentityInvariantTests(unittest.TestCase):
    def test_surname_only_corporate_role_is_not_publishable_event_identity(self) -> None:
        source = "박 회장은 26일 AI 반도체 투자 확대 계획을 발표했다."
        request = request_for(
            event_id="event:invariant-chairman",
            topic_id="ai_tech",
            source=source,
            subject="박 회장",
            action="26일 AI 반도체 투자 확대 계획을 발표했다",
        )
        draft = GeneratedDraft(
            event_id=request.event.event_id,
            headline="박 회장, AI 반도체 투자 확대 계획 발표",
            summary=source,
            evidence_ids=request.evidence_ids,
        )
        report = validate_preservation(request, draft)
        self.assertFalse(report.accepted)
        self.assertIn("invalid_event_subject", issue_codes(report))

    def test_surname_only_legislator_is_not_publishable_event_identity(self) -> None:
        source = "김 의원은 26일 AI 허위광고 규제 법안을 대표발의했다."
        request = request_for(
            event_id="event:invariant-legislator",
            topic_id="ai_tech",
            source=source,
            subject="김 의원",
            action="26일 AI 허위광고 규제 법안을 대표발의했다",
        )
        draft = GeneratedDraft(
            event_id=request.event.event_id,
            headline="김 의원, AI 허위광고 규제 법안 발의",
            summary=source,
            evidence_ids=request.evidence_ids,
        )
        report = validate_preservation(request, draft)
        self.assertFalse(report.accepted)
        self.assertIn("invalid_event_subject", issue_codes(report))

    def test_full_named_role_remains_valid_event_identity(self) -> None:
        source = "김성원 의원은 26일 AI 허위광고 규제 법안을 대표발의했다."
        request = request_for(
            event_id="event:invariant-full-name",
            topic_id="ai_tech",
            source=source,
            subject="김성원 의원",
            action="26일 AI 허위광고 규제 법안을 대표발의했다",
        )
        draft = GeneratedDraft(
            event_id=request.event.event_id,
            headline="김성원 의원, AI 허위광고 규제 법안 발의",
            summary=source,
            evidence_ids=request.evidence_ids,
        )
        report = validate_preservation(request, draft)
        self.assertTrue(report.accepted, report.issues)


class HeadlinePrimarySubjectInvariantTests(unittest.TestCase):
    def test_statistical_metric_subject_cannot_disappear_from_headline(self) -> None:
        source = "전월 대비 PCE 물가는 0.2% 올라 6월 0.1% 하락에서 상승으로 전환했다."
        request = request_for(
            event_id="event:invariant-pce",
            topic_id="economy",
            source=source,
            subject="PCE 물가",
            action="0.2% 올라 6월 0.1% 하락에서 상승으로 전환했다",
        )
        draft = GeneratedDraft(
            event_id=request.event.event_id,
            headline="0.2% 올라 6월 0.1% 하락에서 상승으로 전환",
            summary=source,
            evidence_ids=request.evidence_ids,
        )
        report = validate_preservation(request, draft)
        self.assertFalse(report.accepted)
        self.assertIn("missing_headline_subject", issue_codes(report))

    def test_pitcher_subject_cannot_disappear_from_headline(self) -> None:
        source = "최민준은 26일 한화전에 선발 등판해 5⅓이닝 무실점을 기록했다."
        request = request_for(
            event_id="event:invariant-pitcher",
            topic_id="kbo_hanwha",
            source=source,
            subject="최민준",
            action="26일 한화전에 선발 등판해 5⅓이닝 무실점을 기록했다",
        )
        draft = GeneratedDraft(
            event_id=request.event.event_id,
            headline="26일 한화전에 선발 등판해 5⅓이닝 무실점",
            summary=source,
            evidence_ids=request.evidence_ids,
        )
        report = validate_preservation(request, draft)
        self.assertFalse(report.accepted)
        self.assertIn("missing_headline_subject", issue_codes(report))

    def test_primary_subject_in_headline_remains_valid(self) -> None:
        source = "최민준은 26일 한화전에 선발 등판해 5⅓이닝 무실점을 기록했다."
        request = request_for(
            event_id="event:invariant-pitcher-positive",
            topic_id="kbo_hanwha",
            source=source,
            subject="최민준",
            action="26일 한화전에 선발 등판해 5⅓이닝 무실점을 기록했다",
        )
        draft = GeneratedDraft(
            event_id=request.event.event_id,
            headline="최민준, 26일 한화전 5⅓이닝 무실점",
            summary=source,
            evidence_ids=request.evidence_ids,
        )
        report = validate_preservation(request, draft)
        self.assertTrue(report.accepted, report.issues)


class ProspectiveEventDiscriminatorInvariantTests(unittest.TestCase):
    def _starter_request(self, event_id: str) -> GenerationRequest:
        source = "한화는 27일 인천 SSG랜더스필드에서 열리는 SSG전에 브루스 짐머맨을 선발 투수로 예고했다."
        return request_for(
            event_id=event_id,
            topic_id="kbo_hanwha",
            source=source,
            subject="브루스 짐머맨",
            action="27일 SSG전에 선발 등판한다",
            event_date="2026-08-27",
            participants=("SSG",),
            temporal_state=TemporalState.PLANNED,
        )

    def test_planned_event_with_known_date_cannot_drop_date(self) -> None:
        request = self._starter_request("event:invariant-starter-date")
        draft = GeneratedDraft(
            event_id=request.event.event_id,
            headline="브루스 짐머맨, SSG전 선발 등판",
            summary="한화는 SSG전에 브루스 짐머맨을 선발 투수로 예고했다.",
            evidence_ids=request.evidence_ids,
        )
        report = validate_preservation(request, draft)
        self.assertFalse(report.accepted)
        self.assertIn("missing_event_date", issue_codes(report))

    def test_planned_event_with_known_counterparty_cannot_drop_counterparty(self) -> None:
        request = self._starter_request("event:invariant-starter-opponent")
        draft = GeneratedDraft(
            event_id=request.event.event_id,
            headline="브루스 짐머맨, 27일 선발 등판",
            summary="한화는 27일 브루스 짐머맨을 선발 투수로 예고했다.",
            evidence_ids=request.evidence_ids,
        )
        report = validate_preservation(request, draft)
        self.assertFalse(report.accepted)
        self.assertIn("missing_event_participant", issue_codes(report))

    def test_planned_event_preserving_date_and_counterparty_remains_valid(self) -> None:
        request = self._starter_request("event:invariant-starter-positive")
        draft = GeneratedDraft(
            event_id=request.event.event_id,
            headline="브루스 짐머맨, 27일 SSG전 선발 등판",
            summary="한화는 27일 SSG전에 브루스 짐머맨을 선발 투수로 예고했다.",
            evidence_ids=request.evidence_ids,
        )
        report = validate_preservation(request, draft)
        self.assertTrue(report.accepted, report.issues)


if __name__ == "__main__":
    unittest.main()
