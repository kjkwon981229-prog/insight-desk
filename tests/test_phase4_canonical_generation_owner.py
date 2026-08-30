from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from types import SimpleNamespace
import unittest

from insight_desk.core import (
    CandidateEvent,
    CanonicalEvidenceRef,
    CanonicalEvent,
    Certainty,
    EvidenceField,
    EvidenceSpan,
    EventFact,
    RenderMode,
    SourceDocument,
    VerificationCheck,
)
from insight_desk.generation import GeneratedDraft, GenerationContractError, GenerationRequest
from insight_desk.generation_pipeline import generate_with_recovery
from insight_desk.production_orchestrator_v2 import ProductionV2Registry
from insight_desk.production_phase7_v2 import (
    CanonicalEventRecoveryGenerator,
    CanonicalGenerationRequest,
    build_canonical_generation_request,
    scope_phase7_story_readmission,
)
from insight_desk.providers.cloudflare import CLOUDFLARE_VERIFIER_ID
from insight_desk.providers.local_nli import LOCAL_NLI_VERIFIER_ID
from insight_desk.verification_pipeline import DETERMINISTIC_SOURCE_PROOF_VERIFIER_ID


NOW = datetime(2026, 8, 30, 0, 0, tzinfo=timezone.utc)
PRIMARY = "한국은행은 기준금리를 동결했다."
BACKGROUND = "시장은 상승했다."
BODY = PRIMARY + " " + BACKGROUND
ARTICLE_ID = "article:generation"
EVENT_ID = "event:generation"
FACT_ID = "fact:generation"
EVIDENCE_ID = "evidence:generation"
SOURCE_ID = "source-document:article:generation"


def _source() -> SourceDocument:
    return SourceDocument(
        source_id=SOURCE_ID,
        candidate_ids=(ARTICLE_ID,),
        publisher="example.com",
        url="https://example.com/generation",
        title="한국은행 기준금리 결정",
        body=BODY,
        fetched_at=NOW,
        publication_time=NOW,
        retrieved_via="fixture",
        content_sha256=hashlib.sha256(BODY.encode("utf-8")).hexdigest(),
    )


def _canonical(*, ref_start: int = 0, ref_end: int | None = None) -> CanonicalEvent:
    end = len(PRIMARY) if ref_end is None else ref_end
    text = BODY[ref_start:end]
    return CanonicalEvent(
        event_id=EVENT_ID,
        topic="economy",
        actor="한국은행",
        action="기준금리를 동결했다",
        object="기준금리",
        event_type="news_event",
        source_ids=(SOURCE_ID,),
        publication_time=NOW,
        certainty=Certainty.ASSERTED,
        fact_ids=(FACT_ID,),
        evidence_ids=(EVIDENCE_ID,),
        evidence_refs=(
            CanonicalEvidenceRef(
                source_id=SOURCE_ID,
                field="body",
                start=ref_start,
                end=end,
                text_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
            ),
        ),
    )


def _legacy_request(*, evidence_start: int = 0, evidence_end: int | None = None) -> GenerationRequest:
    end = len(PRIMARY) if evidence_end is None else evidence_end
    span = EvidenceSpan(
        evidence_id=EVIDENCE_ID,
        article_id=ARTICLE_ID,
        field=EvidenceField.BODY,
        start=evidence_start,
        end=end,
        text=BODY[evidence_start:end],
    )
    fact = EventFact(
        fact_id=FACT_ID,
        subject="시장",
        action="상승했다",
        evidence_ids=(EVIDENCE_ID,),
        certainty=Certainty.ASSERTED,
    )
    event = CandidateEvent(
        event_id=EVENT_ID,
        topic_id="economy",
        fact_ids=(FACT_ID,),
        article_ids=(ARTICLE_ID,),
    )
    return GenerationRequest(event=event, facts={FACT_ID: fact}, evidence={EVIDENCE_ID: span})


def _registry(canonical: CanonicalEvent | None = None) -> ProductionV2Registry:
    return ProductionV2Registry(
        sources_by_article={ARTICLE_ID: _source()},
        events_by_id={EVENT_ID: canonical or _canonical()},
    )


def _source_grounded_draft(
    *,
    topic: str,
    actor: str,
    action: str,
    proposition: str,
    object_text: str | None = None,
) -> GeneratedDraft:
    token = hashlib.sha256(
        f"{topic}\x1f{actor}\x1f{action}\x1f{proposition}".encode("utf-8")
    ).hexdigest()[:12]
    article_id = f"article:projection:{token}"
    event_id = f"event:projection:{token}"
    fact_id = f"fact:projection:{token}"
    evidence_id = f"evidence:projection:{token}"
    source_id = f"source-document:{article_id}"
    source = SourceDocument(
        source_id=source_id,
        candidate_ids=(article_id,),
        publisher="fixture.example",
        url=f"https://fixture.example/{token}",
        title="fixture",
        body=proposition,
        fetched_at=NOW,
        publication_time=NOW,
        retrieved_via="fixture",
        content_sha256=hashlib.sha256(proposition.encode("utf-8")).hexdigest(),
    )
    span = EvidenceSpan(
        evidence_id=evidence_id,
        article_id=article_id,
        field=EvidenceField.BODY,
        start=0,
        end=len(proposition),
        text=proposition,
    )
    legacy_fact = EventFact(
        fact_id=fact_id,
        subject="legacy-subject",
        action="legacy-action",
        evidence_ids=(evidence_id,),
        certainty=Certainty.ASSERTED,
    )
    candidate = CandidateEvent(
        event_id=event_id,
        topic_id=topic,
        fact_ids=(fact_id,),
        article_ids=(article_id,),
    )
    canonical = CanonicalEvent(
        event_id=event_id,
        topic=topic,
        actor=actor,
        action=action,
        object=object_text,
        event_type="news_event",
        source_ids=(source_id,),
        publication_time=NOW,
        certainty=Certainty.ASSERTED,
        fact_ids=(fact_id,),
        evidence_ids=(evidence_id,),
        evidence_refs=(
            CanonicalEvidenceRef(
                source_id=source_id,
                field="body",
                start=0,
                end=len(proposition),
                text_sha256=hashlib.sha256(proposition.encode("utf-8")).hexdigest(),
            ),
        ),
    )
    request = GenerationRequest(
        event=candidate,
        facts={fact_id: legacy_fact},
        evidence={evidence_id: span},
    )
    registry = ProductionV2Registry(
        sources_by_article={article_id: source},
        events_by_id={event_id: canonical},
    )
    canonical_request = build_canonical_generation_request(registry, request)
    return CanonicalEventRecoveryGenerator(registry).generate(canonical_request)


class _RecordingGenerator:
    def __init__(self) -> None:
        self.requests: list[GenerationRequest] = []

    def generate(self, request: GenerationRequest) -> GeneratedDraft:
        self.requests.append(request)
        return GeneratedDraft(
            event_id=request.event.event_id,
            headline="한국은행 기준금리 동결",
            summary=PRIMARY,
            evidence_ids=request.evidence_ids,
        )


class _AlwaysSupportVerifier:
    def __init__(self, verifier_id: str) -> None:
        self.verifier_id = verifier_id
        self.model_id = verifier_id + "-fixture"
        self.calls: list[tuple[str, str]] = []

    def verify(self, *, check_id, claim_text, evidence_text, evidence_ids):
        self.calls.append((claim_text, evidence_text))
        return VerificationCheck(
            check_id=check_id,
            verifier_id=self.verifier_id,
            model_id=self.model_id,
            evidence_ids=evidence_ids,
            entailed=True,
            zero_cost=True,
        )


class CanonicalGenerationOwnerTests(unittest.TestCase):
    def test_canonical_request_uses_canonical_metadata_not_legacy_fact(self) -> None:
        request = build_canonical_generation_request(_registry(), _legacy_request())
        self.assertIsInstance(request, CanonicalGenerationRequest)
        self.assertIn("actor=한국은행", request.fact_text)
        self.assertIn("action=기준금리를 동결했다", request.fact_text)
        self.assertNotIn("subject=시장", request.fact_text)
        self.assertNotIn("action=상승했다", request.fact_text)
        self.assertEqual(request.evidence_text, PRIMARY)

    def test_legacy_generation_helpers_receive_same_canonical_request(self) -> None:
        request = build_canonical_generation_request(_registry(), _legacy_request())
        primary = _RecordingGenerator()
        result = generate_with_recovery(request, primary=primary)
        self.assertEqual(primary.requests, [request])
        self.assertEqual(result.draft.headline, "한국은행 기준금리 동결")

    def test_canonical_evidence_mismatch_fails_closed_without_legacy_fallback(self) -> None:
        second_start = len(PRIMARY) + 1
        legacy = _legacy_request(evidence_start=second_start, evidence_end=len(BODY))
        with self.assertRaisesRegex(GenerationContractError, "canonical evidence"):
            build_canonical_generation_request(_registry(), legacy)

    def test_production_visible_text_is_exact_source_and_skips_semantic_verifiers(self) -> None:
        legacy_phase7_calls: list[GenerationRequest] = []

        def legacy_phase7(request, **_kwargs):
            legacy_phase7_calls.append(request)
            raise AssertionError("legacy provider generation must not own production-visible text")

        core = SimpleNamespace(produce_phase7_entry_candidate=legacy_phase7)
        scope_phase7_story_readmission(core, _registry())
        primary_verifier = _AlwaysSupportVerifier(CLOUDFLARE_VERIFIER_ID)
        secondary_verifier = _AlwaysSupportVerifier(LOCAL_NLI_VERIFIER_ID)
        returned = core.produce_phase7_entry_candidate(
            _legacy_request(),
            primary_generator=_RecordingGenerator(),
            primary_verifier=primary_verifier,
            secondary_verifier=secondary_verifier,
        )

        self.assertIsNotNone(returned)
        assert returned is not None
        self.assertEqual(legacy_phase7_calls, [])
        self.assertIs(returned.final_generation.render_mode, RenderMode.CANONICAL_RECOVERY)
        self.assertEqual(returned.final_generation.draft.headline, PRIMARY)
        self.assertEqual(returned.final_generation.draft.summary, PRIMARY)
        self.assertTrue(returned.publishable)
        self.assertEqual(primary_verifier.calls, [])
        self.assertEqual(secondary_verifier.calls, [])
        self.assertTrue(
            all(
                check.verifier_id == DETERMINISTIC_SOURCE_PROOF_VERIFIER_ID
                for item in returned.verification.claims
                for check in item.claim.checks
            )
        )

    def test_representative_visible_authority_is_exact_source_proposition(self) -> None:
        fixtures = (
            ("economy", "한국은행", "기준금리를 동결했다", "한국은행은 기준금리를 동결했다.", "기준금리"),
            ("kbo_hanwha", "한화 이글스", "롯데를 이겼다", "한화 이글스는 롯데 자이언츠를 5대 3으로 이겼다.", "롯데 자이언츠"),
            ("ai_tech", "오픈AI", "공개했다", "오픈AI는 새 API 기능을 공개했다.", "새 API 기능"),
            ("economy", "인사혁신처", "확정됐다", "인사혁신처는 2027년부터 PSAT을 별도 검정시험으로 시행해 기존 1차 시험을 대체한다고 밝혔다.", "PSAT"),
        )
        for topic, actor, action, proposition, object_text in fixtures:
            with self.subTest(topic=topic, proposition=proposition):
                draft = _source_grounded_draft(
                    topic=topic,
                    actor=actor,
                    action=action,
                    proposition=proposition,
                    object_text=object_text,
                )
                self.assertEqual(draft.headline, proposition)
                self.assertEqual(draft.summary, proposition)

    def test_coordinated_actor_survives_lossy_actor_projection(self) -> None:
        proposition = "한화와 NC는 29일 대전에서 맞붙는다."
        draft = _source_grounded_draft(
            topic="kbo_hanwha",
            actor="NC",
            action="맞붙는다",
            proposition=proposition,
        )
        self.assertEqual(draft.headline, proposition)
        self.assertIn("한화", draft.headline)
        self.assertIn("NC", draft.headline)

    def test_object_role_is_preserved_by_source_bytes_not_reconstructed_labels(self) -> None:
        proposition = "정부는 공무원 채용시험 개편안을 발표했다."
        draft = _source_grounded_draft(
            topic="economy",
            actor="정부",
            action="개편안을 발표했다",
            proposition=proposition,
            object_text="공무원 채용시험",
        )
        self.assertEqual(draft.summary, proposition)
        self.assertNotIn("대상:", draft.summary)

    def test_psat_source_proposition_cannot_mutate_into_adoption(self) -> None:
        proposition = "인사혁신처는 2027년부터 PSAT을 별도 검정시험으로 시행해 기존 1차 시험을 대체한다고 밝혔다."
        draft = _source_grounded_draft(
            topic="economy",
            actor="인사혁신처",
            action="확정됐다",
            proposition=proposition,
            object_text="PSAT",
        )
        self.assertEqual(draft.combined_text, proposition + "\n" + proposition)
        self.assertIn("별도 검정시험", draft.combined_text)
        self.assertIn("기존 1차 시험을 대체", draft.combined_text)
        self.assertNotIn("PSAT 도입", draft.combined_text)


if __name__ == "__main__":
    unittest.main()
