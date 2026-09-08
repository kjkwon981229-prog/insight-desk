from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import unittest

from insight_desk.core import (
    CandidateEvent,
    CanonicalEvidenceRef,
    CanonicalEvent,
    Certainty,
    EvidenceField,
    EvidenceSpan,
    EventFact,
    SourceDocument,
)
from insight_desk.generation import GeneratedDraft, GenerationContractError, GenerationRequest
from insight_desk.production_phase7_v2 import (
    CanonicalEventRecoveryGenerator,
    build_canonical_generation_request,
)
from insight_desk.verification_pipeline import (
    DETERMINISTIC_SOURCE_PROOF_VERIFIER_ID,
    verify_exact_canonical_proposition_draft,
    verify_exact_source_draft,
)


class _Registry:
    def __init__(self, event: CanonicalEvent, source: SourceDocument) -> None:
        self._event = event
        self._source = source

    def canonical_event(self, event_id: str) -> CanonicalEvent:
        if event_id != self._event.event_id:
            raise KeyError(event_id)
        return self._event

    def source_for_event(self, event_id: str) -> SourceDocument:
        if event_id != self._event.event_id:
            raise KeyError(event_id)
        return self._source


def _fixture(
    proposition: str,
    *,
    actor: str,
    action: str,
    topic: str,
    object_text: str | None = None,
    second_proposition: str | None = None,
):
    article_id = "article-1"
    source_id = "source-1"
    event_id = "event-1"
    fact_id = "fact-1"
    evidence_id = "evidence-1"
    body = proposition if second_proposition is None else proposition + "\n" + second_proposition
    now = datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)
    source = SourceDocument(
        source_id=source_id,
        candidate_ids=(article_id,),
        publisher="fixture",
        url="https://example.com/source",
        title="fixture title",
        body=body,
        fetched_at=now,
        publication_time=now,
        retrieved_via="fixture",
        content_sha256=hashlib.sha256(body.encode("utf-8")).hexdigest(),
    )
    spans = [
        EvidenceSpan(
            evidence_id=evidence_id,
            article_id=article_id,
            field=EvidenceField.BODY,
            start=0,
            end=len(proposition),
            text=proposition,
        )
    ]
    refs = [
        CanonicalEvidenceRef(
            source_id=source_id,
            field="body",
            start=0,
            end=len(proposition),
            text_sha256=hashlib.sha256(proposition.encode("utf-8")).hexdigest(),
        )
    ]
    if second_proposition is not None:
        second_id = "evidence-2"
        second_start = len(proposition) + 1
        spans.append(
            EvidenceSpan(
                evidence_id=second_id,
                article_id=article_id,
                field=EvidenceField.BODY,
                start=second_start,
                end=second_start + len(second_proposition),
                text=second_proposition,
            )
        )
        refs.append(
            CanonicalEvidenceRef(
                source_id=source_id,
                field="body",
                start=second_start,
                end=second_start + len(second_proposition),
                text_sha256=hashlib.sha256(second_proposition.encode("utf-8")).hexdigest(),
            )
        )

    evidence_ids = tuple(span.evidence_id for span in spans)
    fact = EventFact(
        fact_id=fact_id,
        subject=actor,
        action=action,
        object=object_text,
        evidence_ids=evidence_ids,
        certainty=Certainty.ASSERTED,
    )
    candidate = CandidateEvent(
        event_id=event_id,
        topic_id=topic,
        fact_ids=(fact_id,),
        article_ids=(article_id,),
    )
    event = CanonicalEvent(
        event_id=event_id,
        topic=topic,
        actor=actor,
        action=action,
        object=object_text,
        event_type="fixture-event",
        source_ids=(source_id,),
        fact_ids=(fact_id,),
        evidence_ids=evidence_ids,
        evidence_refs=tuple(refs),
        certainty=Certainty.ASSERTED,
    )
    request = GenerationRequest(
        event=candidate,
        facts={fact_id: fact},
        evidence={span.evidence_id: span for span in spans},
    )
    registry = _Registry(event, source)
    canonical_request = build_canonical_generation_request(registry, request)
    return registry, canonical_request


class SourceGroundedVisibleAuthorityTests(unittest.TestCase):
    def test_kbo_coordinated_actor_is_preserved_from_exact_source(self) -> None:
        proposition = "한화와 NC는 29일 대전에서 맞붙는다."
        registry, request = _fixture(
            proposition,
            actor="NC",
            action="맞붙는다",
            topic="kbo_hanwha",
        )

        draft = CanonicalEventRecoveryGenerator(registry).generate(request)

        self.assertEqual(draft.headline, proposition)
        self.assertEqual(draft.summary, proposition)
        self.assertIn("한화", draft.headline)
        self.assertIn("NC", draft.headline)
        verification = verify_exact_canonical_proposition_draft(request, draft)
        self.assertTrue(verification.publishable)
        self.assertTrue(
            all(
                check.verifier_id == DETERMINISTIC_SOURCE_PROOF_VERIFIER_ID
                for result in verification.claims
                for check in result.claim.checks
            )
        )

    def test_psat_exact_proposition_survives_lossy_flat_action(self) -> None:
        proposition = (
            "내년부터 검정시험 형태로 처음 시행돼 국가공무원 5·7급 공채를 비롯한 복수 시험의 "
            "1차 시험으로 대체되는 공직적격성평가(PSAT)의 시험 일정 등 운영 방향이 확정됐다."
        )
        registry, request = _fixture(
            proposition,
            actor="공직적격성평가(PSAT)",
            action="확정됐다",
            object_text="시험 일정 등 운영 방향",
            topic="economy",
        )

        draft = CanonicalEventRecoveryGenerator(registry).generate(request)

        self.assertEqual(draft.headline, proposition)
        self.assertEqual(draft.summary, proposition)
        self.assertIn("검정시험 형태로 처음 시행", draft.combined_text)
        self.assertIn("1차 시험으로 대체", draft.combined_text)
        self.assertNotIn("PSAT 도입", draft.combined_text)
        self.assertNotEqual(draft.headline, "확정됐다")
        self.assertTrue(verify_exact_canonical_proposition_draft(request, draft).publishable)

    def test_multiple_canonical_proposition_spans_fail_closed(self) -> None:
        with self.assertRaisesRegex(
            GenerationContractError,
            "requires one exact proposition",
        ):
            _fixture(
                "한화와 NC는 29일 대전에서 맞붙는다.",
                actor="NC",
                action="맞붙는다",
                topic="kbo_hanwha",
                second_proposition="양 팀은 선발 라인업을 공개했다.",
            )

    def test_one_evidence_ref_crossing_source_blocks_fails_closed(self) -> None:
        first = "시장 전망은 개선될 수 있다"
        second = "5대 은행의 정기예금 잔액이 증가했다."
        with self.assertRaisesRegex(
            GenerationContractError,
            "requires one exact proposition",
        ):
            _fixture(
                first + "\n" + second,
                actor="5대 은행",
                action="정기예금 잔액이 증가했다",
                topic="economy",
            )

    def test_exact_source_verification_does_not_need_semantic_verifier(self) -> None:
        proposition = "한국은행은 기준금리를 동결했다."
        registry, request = _fixture(
            proposition,
            actor="한국은행",
            action="기준금리를 동결했다",
            topic="economy",
        )
        draft = CanonicalEventRecoveryGenerator(registry).generate(request)

        verification = verify_exact_canonical_proposition_draft(request, draft)

        self.assertTrue(verification.publishable)
        self.assertEqual(len(verification.claims), 2)
        for result in verification.claims:
            self.assertEqual(len(result.claim.checks), 1)
            self.assertEqual(
                result.claim.checks[0].verifier_id,
                DETERMINISTIC_SOURCE_PROOF_VERIFIER_ID,
            )
            self.assertTrue(result.claim.checks[0].entailed)

    def test_canonical_proof_rejects_a_punctuation_truncated_excerpt(self) -> None:
        proposition = "한국은행은 기준금리를 동결했다."
        _registry, request = _fixture(
            proposition,
            actor="한국은행",
            action="기준금리를 동결했다",
            topic="economy",
        )
        excerpt = proposition[:-1]
        draft = GeneratedDraft(
            event_id=request.event.event_id,
            headline=excerpt,
            summary=excerpt,
            evidence_ids=request.evidence_ids,
        )

        self.assertTrue(verify_exact_source_draft(request, draft).publishable)
        self.assertFalse(
            verify_exact_canonical_proposition_draft(request, draft).publishable
        )

    def test_identical_bytes_from_an_unbound_article_cannot_satisfy_provenance(self) -> None:
        proposition = "한국은행은 기준금리를 동결했다."
        registry, canonical_request = _fixture(
            proposition,
            actor="한국은행",
            action="기준금리를 동결했다",
            topic="economy",
        )
        evidence_id = canonical_request.evidence_ids[0]
        foreign_span = replace(
            canonical_request.evidence[evidence_id],
            article_id="article-with-identical-bytes-but-no-source-binding",
        )
        foreign_request = GenerationRequest(
            event=replace(
                canonical_request.event,
                article_ids=(
                    canonical_request.event.article_ids[0],
                    foreign_span.article_id,
                ),
            ),
            facts=canonical_request.facts,
            evidence={evidence_id: foreign_span},
        )

        with self.assertRaisesRegex(
            GenerationContractError,
            "absent from generation provenance",
        ):
            build_canonical_generation_request(registry, foreign_request)


if __name__ == "__main__":
    unittest.main()
