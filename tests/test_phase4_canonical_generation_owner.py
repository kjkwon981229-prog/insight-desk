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


NOW = datetime(2026, 8, 30, 0, 0, tzinfo=timezone.utc)
BODY = "한국은행은 기준금리를 동결했다. 시장은 상승했다."
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
    source = _source()
    end = len(BODY) if ref_end is None else ref_end
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
    end = len(BODY) if evidence_end is None else evidence_end
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
    return GenerationRequest(
        event=event,
        facts={FACT_ID: fact},
        evidence={EVIDENCE_ID: span},
    )


def _registry(canonical: CanonicalEvent | None = None) -> ProductionV2Registry:
    source = _source()
    return ProductionV2Registry(
        sources_by_article={ARTICLE_ID: source},
        events_by_id={EVENT_ID: canonical or _canonical()},
    )


def _projection_draft(
    *,
    topic: str,
    actor: str,
    action: str,
    body: str,
    object_text: str | None = None,
) -> GeneratedDraft:
    token = hashlib.sha256(f"{topic}\x1f{actor}\x1f{action}\x1f{body}".encode("utf-8")).hexdigest()[:12]
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
        title=body,
        body=body,
        fetched_at=NOW,
        publication_time=NOW,
        retrieved_via="fixture",
        content_sha256=hashlib.sha256(body.encode("utf-8")).hexdigest(),
    )
    span = EvidenceSpan(
        evidence_id=evidence_id,
        article_id=article_id,
        field=EvidenceField.BODY,
        start=0,
        end=len(body),
        text=body,
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
        evidence_refs=(
            CanonicalEvidenceRef(
                source_id=source_id,
                field="body",
                start=0,
                end=len(body),
                text_sha256=hashlib.sha256(body.encode("utf-8")).hexdigest(),
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
            event_id=EVENT_ID,
            headline="한국은행 기준금리 동결",
            summary="한국은행은 기준금리를 동결했다.",
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
    def test_primary_generation_reads_canonical_semantics_not_legacy_event_fact(self) -> None:
        request = build_canonical_generation_request(_registry(), _legacy_request())
        self.assertIsInstance(request, CanonicalGenerationRequest)
        self.assertIn("actor=한국은행", request.fact_text)
        self.assertIn("action=기준금리를 동결했다", request.fact_text)
        self.assertNotIn("subject=시장", request.fact_text)
        self.assertNotIn("action=상승했다", request.fact_text)

        primary = _RecordingGenerator()
        result = generate_with_recovery(request, primary=primary)
        self.assertEqual(len(primary.requests), 1)
        self.assertIs(primary.requests[0], request)
        self.assertEqual(result.draft.headline, "한국은행 기준금리 동결")

    def test_alternate_generation_receives_the_same_canonical_request(self) -> None:
        request = build_canonical_generation_request(_registry(), _legacy_request())
        alternate = _RecordingGenerator()
        result = generate_with_recovery(request, primary=None, alternate=alternate)
        self.assertEqual(len(alternate.requests), 1)
        self.assertIs(alternate.requests[0], request)
        self.assertIn("actor=한국은행", alternate.requests[0].fact_text)
        self.assertEqual(result.draft.headline, "한국은행 기준금리 동결")

    def test_canonical_evidence_mismatch_fails_closed_without_legacy_fact_fallback(self) -> None:
        first_sentence_end = BODY.index(".") + 1
        canonical = _canonical(ref_start=0, ref_end=first_sentence_end)
        legacy = _legacy_request(
            evidence_start=first_sentence_end + 1,
            evidence_end=len(BODY),
        )
        with self.assertRaisesRegex(GenerationContractError, "canonical evidence"):
            build_canonical_generation_request(_registry(canonical), legacy)

    def test_production_visible_text_is_deterministic_canonical_projection(self) -> None:
        legacy_phase7_calls: list[GenerationRequest] = []

        def legacy_phase7(request, **_kwargs):
            legacy_phase7_calls.append(request)
            raise AssertionError("legacy provider generation must not own production-visible text")

        core = SimpleNamespace(produce_phase7_entry_candidate=legacy_phase7)
        scope_phase7_story_readmission(core, _registry())
        legacy = _legacy_request()
        primary_generator = _RecordingGenerator()
        primary_verifier = _AlwaysSupportVerifier(CLOUDFLARE_VERIFIER_ID)
        secondary_verifier = _AlwaysSupportVerifier(LOCAL_NLI_VERIFIER_ID)

        returned = core.produce_phase7_entry_candidate(
            legacy,
            primary_generator=primary_generator,
            primary_verifier=primary_verifier,
            secondary_verifier=secondary_verifier,
        )

        self.assertIsNotNone(returned)
        assert returned is not None
        self.assertEqual(legacy_phase7_calls, [])
        self.assertEqual(primary_generator.requests, [])
        self.assertIs(returned.final_generation.render_mode, RenderMode.CANONICAL_RECOVERY)
        self.assertEqual(returned.final_generation.draft.headline, "한국은행, 기준금리를 동결했다")
        self.assertEqual(returned.final_generation.draft.summary, "한국은행 · 기준금리를 동결했다")
        self.assertNotIn("주체:", returned.final_generation.draft.summary)
        self.assertNotIn("사건:", returned.final_generation.draft.summary)
        self.assertTrue(returned.publishable)
        self.assertTrue(primary_verifier.calls)
        self.assertTrue(secondary_verifier.calls)

    def test_representative_visible_projection_preserves_canonical_slots_exactly(self) -> None:
        fixtures = (
            {
                "name": "economy",
                "topic": "economy",
                "actor": "한국은행",
                "action": "기준금리를 동결했다",
                "body": "한국은행은 기준금리를 동결했다.",
                "object_text": "기준금리",
                "summary": "한국은행 · 기준금리를 동결했다",
            },
            {
                "name": "kbo",
                "topic": "kbo_hanwha",
                "actor": "한화 이글스",
                "action": "롯데 자이언츠를 5대 3으로 이겼다",
                "body": "한화 이글스는 롯데 자이언츠를 5대 3으로 이겼다.",
                "object_text": "롯데 자이언츠",
                "summary": "한화 이글스 · 롯데 자이언츠를 5대 3으로 이겼다",
            },
            {
                "name": "ai",
                "topic": "ai_tech",
                "actor": "오픈AI",
                "action": "새 API 기능을 공개했다",
                "body": "오픈AI는 새 API 기능을 공개했다.",
                "object_text": "새 API 기능",
                "summary": "오픈AI · 새 API 기능을 공개했다",
            },
            {
                "name": "psat",
                "topic": "economy",
                "actor": "인사혁신처",
                "action": "2027년부터 PSAT을 별도 검정시험으로 시행한다",
                "body": "인사혁신처는 2027년부터 PSAT을 별도 검정시험으로 시행한다.",
                "object_text": "PSAT",
                "summary": "인사혁신처 · 2027년부터 PSAT을 별도 검정시험으로 시행한다",
            },
        )
        for fixture in fixtures:
            with self.subTest(fixture["name"]):
                draft = _projection_draft(
                    topic=fixture["topic"],
                    actor=fixture["actor"],
                    action=fixture["action"],
                    body=fixture["body"],
                    object_text=fixture["object_text"],
                )
                self.assertEqual(draft.summary, fixture["summary"])
                self.assertIn(fixture["actor"], draft.combined_text)
                self.assertIn(fixture["action"], draft.combined_text)
                self.assertNotIn("주체:", draft.summary)
                self.assertNotIn("사건:", draft.summary)

    def test_projection_does_not_repeat_actor_already_present_in_action(self) -> None:
        action = "한국은행이 기준금리를 동결했다"
        draft = _projection_draft(
            topic="economy",
            actor="한국은행",
            action=action,
            body=action + ".",
            object_text="기준금리",
        )
        self.assertEqual(draft.headline, action)
        self.assertEqual(draft.summary, action)

    def test_projection_keeps_explicit_object_role_when_action_does_not_contain_it(self) -> None:
        draft = _projection_draft(
            topic="economy",
            actor="정부",
            action="개편안을 발표했다",
            body="정부는 공무원 채용시험 개편안을 발표했다.",
            object_text="공무원 채용시험",
        )
        self.assertEqual(draft.summary, "정부 · 개편안을 발표했다 · 대상: 공무원 채용시험")

    def test_psat_projection_cannot_mutate_separate_test_into_adoption(self) -> None:
        action = "2027년부터 PSAT을 별도 검정시험으로 시행한다"
        draft = _projection_draft(
            topic="economy",
            actor="인사혁신처",
            action=action,
            body="인사혁신처는 2027년부터 PSAT을 별도 검정시험으로 시행한다.",
            object_text="PSAT",
        )
        self.assertIn(action, draft.headline)
        self.assertIn(action, draft.summary)
        self.assertNotIn("도입", draft.combined_text)


if __name__ == "__main__":
    unittest.main()
