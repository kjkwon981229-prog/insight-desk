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
    SourceDocument,
)
from insight_desk.generation import GeneratedDraft, GenerationContractError, GenerationRequest
from insight_desk.generation_pipeline import generate_with_recovery
from insight_desk.production_orchestrator_v2 import ProductionV2Registry
from insight_desk.production_phase7_v2 import (
    CanonicalGenerationRequest,
    build_canonical_generation_request,
    scope_phase7_story_readmission,
)


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

    def test_production_phase7_wrapper_replaces_ingress_request_before_generation_routes(self) -> None:
        seen: list[GenerationRequest] = []
        sentinel = SimpleNamespace(
            final_generation=SimpleNamespace(render_mode=__import__("insight_desk.core", fromlist=["RenderMode"]).RenderMode.GENERATED)
        )

        def current(request, **_kwargs):
            seen.append(request)
            return sentinel

        core = SimpleNamespace(produce_phase7_entry_candidate=current)
        scope_phase7_story_readmission(core, _registry())
        legacy = _legacy_request()
        returned = core.produce_phase7_entry_candidate(
            legacy,
            primary_generator=object(),
            primary_verifier=object(),
            secondary_verifier=object(),
        )
        self.assertIs(returned, sentinel)
        self.assertEqual(len(seen), 1)
        self.assertIsInstance(seen[0], CanonicalGenerationRequest)
        self.assertIsNot(seen[0], legacy)
        self.assertIn("actor=한국은행", seen[0].fact_text)
        self.assertNotIn("subject=시장", seen[0].fact_text)


if __name__ == "__main__":
    unittest.main()
