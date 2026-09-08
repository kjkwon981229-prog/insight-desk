from __future__ import annotations

from datetime import datetime, timezone
import unittest

from insight_desk.core import CandidateEvent, EvidenceField, EvidenceSpan, EventFact
from insight_desk.generation import GeneratedDraft, GenerationRequest, validate_preservation
from insight_desk.generation_pipeline import ExtractiveFallbackUnavailable, generate_with_recovery
from insight_desk.semantic.visible_identity import visible_event_redundant
from insight_desk.story_admission import StoryAdmissionReason, StoryAdmissionStage, evaluate_story_admission


NOW = datetime(2026, 8, 26, 17, 25, tzinfo=timezone.utc)


def visible(*, topic: str, headline: str, summary: str):
    return evaluate_story_admission(
        topic=topic,
        headline=headline,
        summary=summary,
        source_text=summary,
        stage=StoryAdmissionStage.VISIBLE,
        now=NOW,
    )


def material(*, topic: str, source_text: str, subject: str = ""):
    return evaluate_story_admission(
        topic=topic,
        source_text=source_text,
        subject=subject,
        stage=StoryAdmissionStage.MATERIAL,
        now=NOW,
    )


def request_for(*, event_id: str, topic_id: str, source: str, subject: str, action: str):
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


class Live409ParentEventCentralityRegressions(unittest.TestCase):
    _APPLE_FORECAST = (
        "국내 시장의 스마트폰 부품사, 앱 생태계, 인공지능 서비스 기업이 "
        "애플의 제품 사양과 운영체제 정책을 함께 살필 전망이다."
    )
    _RATE_FORECAST = "기준금리에 대한 전망은 엇갈린다."

    def test_live_industry_watch_forecast_is_not_a_current_event(self) -> None:
        decision = visible(
            topic="AI·테크",
            headline="국내 스마트폰 생태계, 애플 정책 주시",
            summary=self._APPLE_FORECAST,
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.NON_EVENT_DESCRIPTION, decision.reasons)

    def test_live_rate_outlook_state_is_not_a_current_event(self) -> None:
        decision = visible(
            topic="경제·투자",
            headline="전망은 엇갈린다",
            summary=self._RATE_FORECAST,
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.NON_EVENT_DESCRIPTION, decision.reasons)

    def test_live_forecast_background_is_rejected_at_material_boundary(self) -> None:
        for topic, text in (
            ("AI·테크", self._APPLE_FORECAST),
            ("경제·투자", self._RATE_FORECAST),
        ):
            with self.subTest(text=text):
                decision = material(topic=topic, source_text=text)
                self.assertFalse(decision.accepted)
                self.assertIn(StoryAdmissionReason.NON_EVENT_DESCRIPTION, decision.reasons)

    def test_generalized_unattributed_industry_watch_is_not_a_current_event(self) -> None:
        text = "국내 반도체 부품사들이 주요 고객사의 차세대 제품 정책을 함께 살필 전망이다."
        decision = visible(
            topic="AI·테크",
            headline="국내 반도체 부품사, 고객사 정책 주시",
            summary=text,
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.NON_EVENT_DESCRIPTION, decision.reasons)

    def test_named_current_report_forecast_remains_publishable(self) -> None:
        decision = visible(
            topic="경제·투자",
            headline="골드만삭스, 26일 반도체 설비투자 증가 전망",
            summary="골드만삭스는 26일 보고서에서 반도체 설비투자가 늘어날 것으로 전망했다.",
        )
        self.assertTrue(decision.accepted, decision.reasons)

    def test_concrete_current_product_event_remains_publishable(self) -> None:
        decision = visible(
            topic="AI·테크",
            headline="애플, 26일 신형 스마트폰 사양 공개",
            summary="애플은 26일 신형 스마트폰의 주요 사양과 운영체제 기능을 공개했다.",
        )
        self.assertTrue(decision.accepted, decision.reasons)


class Live409ExactFallbackActorInvariantRegressions(unittest.TestCase):
    _SOURCE = (
        "알파드라이브원은 오는 27일 방송되는 Mnet ‘엠카운트다운’에서 "
        "‘BORN DIRE’와 ‘Diamond Hour’의 음악방송 무대를 최초 공개한다."
    )
    _ACTION = (
        "오는 27일 방송되는 Mnet ‘엠카운트다운’에서 ‘BORN DIRE’와 "
        "‘Diamond Hour’의 음악방송 무대를 최초 공개한다"
    )

    def _request(self, event_id: str = "event:live409-alpha") -> GenerationRequest:
        return request_for(
            event_id=event_id,
            topic_id="kpop",
            source=self._SOURCE,
            subject="알파드라이브원",
            action=self._ACTION,
        )

    def test_live_literal_action_headline_cannot_drop_primary_actor(self) -> None:
        request = self._request()
        draft = GeneratedDraft(
            event_id=request.event.event_id,
            headline=self._ACTION,
            summary=self._SOURCE,
            evidence_ids=request.evidence_ids,
        )
        report = validate_preservation(request, draft)
        self.assertFalse(report.accepted)
        self.assertIn("missing_headline_subject", issue_codes(report))

    def test_generalized_literal_action_headline_cannot_drop_primary_actor(self) -> None:
        source = "정부는 28일 국가 AI 기본계획을 발표한다."
        action = "28일 국가 AI 기본계획을 발표한다"
        request = request_for(
            event_id="event:live409-government",
            topic_id="ai_tech",
            source=source,
            subject="정부",
            action=action,
        )
        draft = GeneratedDraft(
            event_id=request.event.event_id,
            headline=action,
            summary=source,
            evidence_ids=request.evidence_ids,
        )
        report = validate_preservation(request, draft)
        self.assertFalse(report.accepted)
        self.assertIn("missing_headline_subject", issue_codes(report))

    def test_exact_fallback_fails_closed_when_only_distinct_headline_drops_actor(self) -> None:
        with self.assertRaises(ExtractiveFallbackUnavailable):
            generate_with_recovery(self._request("event:live409-fallback"), primary=None, alternate=None)

    def test_actor_preserving_headline_remains_valid(self) -> None:
        request = self._request("event:live409-actor-positive")
        draft = GeneratedDraft(
            event_id=request.event.event_id,
            headline="알파드라이브원, 27일 ‘엠카운트다운’서 신곡 무대 최초 공개",
            summary=self._SOURCE,
            evidence_ids=request.evidence_ids,
        )
        report = validate_preservation(request, draft)
        self.assertTrue(report.accepted, report.issues)


class Live409ScheduledPolicyEventDuplicateRegressions(unittest.TestCase):
    def test_live_bok_rate_decision_and_outlook_cards_are_one_scheduled_event(self) -> None:
        self.assertTrue(
            visible_event_redundant(
                topic_id="economy",
                prior_headline="한국은행 금융통화위원회 기준금리 결정",
                prior_summary="한국은행 금융통화위원회가 오늘(27일) 회의를 열어 기준금리를 결정할 예정입니다.",
                candidate_headline="한은, 기준금리 결정 및 경제전망 발표",
                candidate_summary="한은이 이날 기준금리 인상 여부를 결정하며, 수정 경제전망과 향후 6개월 기준금리 전망을 포함한 점도표를 공개한다.",
                prior_source_text="한국은행 금융통화위원회는 27일 회의를 열어 기준금리를 결정한다.",
                candidate_source_text="한국은행은 27일 금융통화위원회에서 기준금리를 결정하고 수정 경제전망과 향후 6개월 점도표를 공개한다.",
            )
        )

    def test_generalized_same_day_policy_decision_children_are_deduplicated(self) -> None:
        self.assertTrue(
            visible_event_redundant(
                topic_id="economy",
                prior_headline="한국은행, 15일 기준금리 결정",
                prior_summary="한국은행 금융통화위원회가 15일 기준금리를 결정한다.",
                candidate_headline="한은, 15일 금리결정과 경제전망 공개",
                candidate_summary="한국은행이 15일 기준금리를 결정하고 수정 경제전망을 발표한다.",
                prior_source_text="한국은행 금융통화위원회는 15일 통화정책방향 회의에서 기준금리를 결정한다.",
                candidate_source_text="한국은행은 15일 금융통화위원회에서 기준금리를 결정하고 경제전망을 공개한다.",
            )
        )

    def test_different_policy_meeting_days_remain_distinct(self) -> None:
        self.assertFalse(
            visible_event_redundant(
                topic_id="economy",
                prior_headline="한국은행, 15일 기준금리 결정",
                prior_summary="한국은행 금융통화위원회가 15일 기준금리를 결정한다.",
                candidate_headline="한국은행, 28일 기준금리 결정",
                candidate_summary="한국은행 금융통화위원회가 28일 기준금리를 결정한다.",
                prior_source_text="한국은행 금융통화위원회는 15일 기준금리를 결정한다.",
                candidate_source_text="한국은행 금융통화위원회는 28일 기준금리를 결정한다.",
            )
        )

    def test_same_day_unrelated_bok_release_remains_distinct(self) -> None:
        self.assertFalse(
            visible_event_redundant(
                topic_id="economy",
                prior_headline="한국은행, 27일 기준금리 결정",
                prior_summary="한국은행 금융통화위원회가 27일 기준금리를 결정한다.",
                candidate_headline="한국은행, 27일 외환시장 동향 발표",
                candidate_summary="한국은행은 27일 외환시장 동향 자료를 발표했다.",
                prior_source_text="한국은행 금융통화위원회는 27일 기준금리를 결정한다.",
                candidate_source_text="한국은행은 27일 외환시장 동향 자료를 발표했다.",
            )
        )


if __name__ == "__main__":
    unittest.main()
