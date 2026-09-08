from __future__ import annotations

from dataclasses import dataclass, field
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
from insight_desk.generation import GenerationRequest
from insight_desk.production_orchestrator_v2 import ProductionV2Registry
from insight_desk.production_phase7_v2 import scope_phase7_story_readmission
from insight_desk.production_verification_v2 import (
    CANONICAL_FIDELITY_INDETERMINATE,
    CANONICAL_FIDELITY_REJECTED,
    CanonicalFidelityVerifier,
)
from insight_desk.providers.cloudflare import CLOUDFLARE_VERIFIER_ID
from insight_desk.providers.local_nli import LOCAL_NLI_VERIFIER_ID
from insight_desk.verification_pipeline import DETERMINISTIC_SOURCE_PROOF_VERIFIER_ID


NOW = datetime(2026, 8, 30, 0, 0, tzinfo=timezone.utc)
BODY = "인사혁신처는 2027년부터 PSAT를 별도 검정시험으로 전환해 기존 1차 시험을 대체한다고 밝혔다."
ARTICLE_ID = "article:canonical-verification"
EVENT_ID = "event:canonical-verification"
FACT_ID = "fact:canonical-verification"
EVIDENCE_ID = "evidence:canonical-verification"
SOURCE_ID = "source-document:canonical-verification"


@dataclass
class RecordingVerifier:
    verifier_id: str
    model_id: str
    answers: list[bool | None] = field(default_factory=list)
    calls: list[tuple[str, str, tuple[str, ...], str]] = field(default_factory=list)

    def verify(self, *, check_id, claim_text, evidence_text, evidence_ids):
        self.calls.append((claim_text, evidence_text, evidence_ids, check_id))
        entailed = self.answers.pop(0) if self.answers else True
        return VerificationCheck(
            check_id=check_id,
            verifier_id=self.verifier_id,
            model_id=self.model_id,
            evidence_ids=evidence_ids,
            entailed=entailed,
            error_code=None if entailed is not None else "synthetic_inconclusive",
            zero_cost=True,
        )


def _source() -> SourceDocument:
    return SourceDocument(
        source_id=SOURCE_ID,
        candidate_ids=(ARTICLE_ID,),
        publisher="example.com",
        url="https://example.com/psat",
        title="2027년 PSAT 제도 개편",
        body=BODY,
        fetched_at=NOW,
        publication_time=NOW,
        retrieved_via="fixture",
        content_sha256=hashlib.sha256(BODY.encode("utf-8")).hexdigest(),
    )


def _canonical() -> CanonicalEvent:
    return CanonicalEvent(
        event_id=EVENT_ID,
        topic="society",
        actor="인사혁신처",
        action="확정됐다",
        object="PSAT",
        event_type="policy_change",
        source_ids=(SOURCE_ID,),
        publication_time=NOW,
        certainty=Certainty.ASSERTED,
        fact_ids=(FACT_ID,),
        evidence_ids=(EVIDENCE_ID,),
        evidence_refs=(
            CanonicalEvidenceRef(
                source_id=SOURCE_ID,
                field="body",
                start=0,
                end=len(BODY),
                text_sha256=hashlib.sha256(BODY.encode("utf-8")).hexdigest(),
            ),
        ),
    )


def _request() -> GenerationRequest:
    span = EvidenceSpan(
        evidence_id=EVIDENCE_ID,
        article_id=ARTICLE_ID,
        field=EvidenceField.BODY,
        start=0,
        end=len(BODY),
        text=BODY,
    )
    fact = EventFact(
        fact_id=FACT_ID,
        subject="인사혁신처",
        action="PSAT 제도를 개편한다고 밝혔다",
        object="PSAT",
        evidence_ids=(EVIDENCE_ID,),
        certainty=Certainty.ASSERTED,
    )
    event = CandidateEvent(
        event_id=EVENT_ID,
        topic_id="society",
        fact_ids=(FACT_ID,),
        article_ids=(ARTICLE_ID,),
    )
    return GenerationRequest(event=event, facts={FACT_ID: fact}, evidence={EVIDENCE_ID: span})


def _registry() -> ProductionV2Registry:
    return ProductionV2Registry(
        sources_by_article={ARTICLE_ID: _source()},
        events_by_id={EVENT_ID: _canonical()},
    )


class CanonicalClaimVerificationTests(unittest.TestCase):
    def test_legacy_canonical_fidelity_rejection_stops_before_source_check(self) -> None:
        base = RecordingVerifier(
            verifier_id=CLOUDFLARE_VERIFIER_ID,
            model_id="primary-model",
            answers=[False],
        )
        canonical_text = "actor=인사혁신처 | action=PSAT 별도 검정시험 전환 및 기존 1차 시험 대체"
        verifier = CanonicalFidelityVerifier(base=base, canonical_text=canonical_text)
        result = verifier.verify(
            check_id="check:headline",
            claim_text="국가공무원 5·7급 공채 PSAT 1차 시험 도입",
            evidence_text=BODY,
            evidence_ids=(EVIDENCE_ID,),
        )
        self.assertFalse(result.entailed)
        self.assertEqual(result.error_code, CANONICAL_FIDELITY_REJECTED)
        self.assertEqual(len(base.calls), 1)
        self.assertEqual(base.calls[0][1], canonical_text)

    def test_legacy_canonical_fidelity_support_then_checks_source(self) -> None:
        base = RecordingVerifier(
            verifier_id=CLOUDFLARE_VERIFIER_ID,
            model_id="primary-model",
            answers=[True, True],
        )
        canonical_text = "actor=인사혁신처 | action=PSAT 별도 검정시험 전환 및 기존 1차 시험 대체"
        verifier = CanonicalFidelityVerifier(base=base, canonical_text=canonical_text)
        result = verifier.verify(
            check_id="check:summary",
            claim_text="2027년부터 PSAT를 별도 검정시험으로 전환한다.",
            evidence_text=BODY,
            evidence_ids=(EVIDENCE_ID,),
        )
        self.assertTrue(result.entailed)
        self.assertEqual(len(base.calls), 2)
        self.assertEqual(base.calls[0][1], canonical_text)
        self.assertEqual(base.calls[1][1], BODY)

    def test_legacy_canonical_fidelity_indeterminate_fails_closed(self) -> None:
        base = RecordingVerifier(
            verifier_id=CLOUDFLARE_VERIFIER_ID,
            model_id="primary-model",
            answers=[None],
        )
        verifier = CanonicalFidelityVerifier(
            base=base,
            canonical_text="actor=인사혁신처 | action=PSAT 제도 개편",
        )
        result = verifier.verify(
            check_id="check:headline",
            claim_text="PSAT 제도 개편",
            evidence_text=BODY,
            evidence_ids=(EVIDENCE_ID,),
        )
        self.assertIsNone(result.entailed)
        self.assertTrue((result.error_code or "").startswith(CANONICAL_FIDELITY_INDETERMINATE))
        self.assertEqual(len(base.calls), 1)

    def test_production_phase7_uses_exact_source_proof_without_semantic_verifiers(self) -> None:
        legacy_calls: list[GenerationRequest] = []

        def current(request: GenerationRequest, **_kwargs):
            legacy_calls.append(request)
            raise AssertionError("legacy provider generation must not own production-visible text")

        core = SimpleNamespace(produce_phase7_entry_candidate=current)
        scope_phase7_story_readmission(core, _registry())
        primary = RecordingVerifier(
            verifier_id=CLOUDFLARE_VERIFIER_ID,
            model_id="primary-model",
        )
        secondary = RecordingVerifier(
            verifier_id=LOCAL_NLI_VERIFIER_ID,
            model_id="secondary-model",
        )
        returned = core.produce_phase7_entry_candidate(
            _request(),
            primary_generator=object(),
            primary_verifier=primary,
            secondary_verifier=secondary,
        )

        self.assertIsNotNone(returned)
        assert returned is not None
        self.assertEqual(legacy_calls, [])
        self.assertIs(returned.final_generation.render_mode, RenderMode.CANONICAL_RECOVERY)
        self.assertEqual(returned.final_generation.draft.headline, BODY)
        self.assertEqual(returned.final_generation.draft.summary, BODY)
        self.assertNotIn("PSAT 도입", returned.final_generation.draft.combined_text)
        self.assertTrue(returned.publishable)
        self.assertEqual(primary.calls, [])
        self.assertEqual(secondary.calls, [])
        self.assertTrue(
            all(
                check.verifier_id == DETERMINISTIC_SOURCE_PROOF_VERIFIER_ID
                for item in returned.verification.claims
                for check in item.claim.checks
            )
        )


if __name__ == "__main__":
    unittest.main()
