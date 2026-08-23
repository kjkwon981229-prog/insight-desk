from __future__ import annotations

from dataclasses import dataclass
from email.message import Message
import io
from pathlib import Path
import unittest
import urllib.error

from insight_desk.core import (
    CandidateEvent,
    EvidenceField,
    EvidenceSpan,
    EventFact,
    FailureKind,
    VerificationCheck,
)
from insight_desk.generation import GeneratedDraft, GenerationRequest
from insight_desk.phase7 import produce_phase7_entry_candidate
from insight_desk.providers.cloudflare import CLOUDFLARE_VERIFIER_ID, CloudflareClaimVerifier
from insight_desk.providers.local_nli import LOCAL_NLI_VERIFIER_ID
from insight_desk.providers.transport import JsonHttpTransport, ProviderTransportError


TEXT = "네오팩토리가 AI 공장 구축 사업을 15억달러에 수주했다."


def request() -> GenerationRequest:
    span = EvidenceSpan(
        evidence_id="ev:phase12b",
        article_id="article:phase12b",
        field=EvidenceField.BODY,
        start=0,
        end=len(TEXT),
        text=TEXT,
    )
    fact = EventFact(
        fact_id="fact:phase12b",
        subject="네오팩토리",
        action="AI 공장 구축 사업을 15억달러에 수주했다",
        object="AI 공장 구축 사업",
        evidence_ids=(span.evidence_id,),
    )
    event = CandidateEvent(
        event_id="event:phase12b",
        topic_id="ai_tech",
        fact_ids=(fact.fact_id,),
        article_ids=(span.article_id,),
    )
    return GenerationRequest(
        event=event,
        facts={fact.fact_id: fact},
        evidence={span.evidence_id: span},
    )


@dataclass
class AlwaysFailGenerator:
    calls: int = 0

    def generate(self, item: GenerationRequest) -> GeneratedDraft:
        self.calls += 1
        raise RuntimeError("synthetic provider unavailable")


@dataclass
class ExplodingVerifier:
    verifier_id: str
    model_id: str
    calls: int = 0

    def verify(self, **kwargs) -> VerificationCheck:
        self.calls += 1
        raise AssertionError("exact-source fallback must not call external semantic verifiers")


@dataclass
class SequenceVerifier:
    verifier_id: str
    model_id: str
    answers: list[VerificationCheck]
    calls: int = 0

    def verify(self, *, check_id: str, claim_text: str, evidence_text: str, evidence_ids: tuple[str, ...]) -> VerificationCheck:
        self.calls += 1
        answer = self.answers.pop(0)
        return VerificationCheck(
            check_id=check_id,
            verifier_id=self.verifier_id,
            model_id=answer.model_id,
            evidence_ids=evidence_ids,
            entailed=answer.entailed,
            error_code=answer.error_code,
            zero_cost=True,
        )


class Phase12BFailureTaxonomyTests(unittest.TestCase):
    def test_generic_http_429_is_rate_limited_not_daily_quota_exhaustion(self) -> None:
        self.assertTrue(hasattr(FailureKind, "RATE_LIMITED"))
        headers = Message()
        headers["Retry-After"] = "7"
        error = urllib.error.HTTPError(
            "https://example.invalid",
            429,
            "Too Many Requests",
            headers,
            io.BytesIO(b"rate limit exceeded"),
        )

        def opener(request, timeout):
            raise error

        transport = JsonHttpTransport(attempts=1, opener=opener, sleeper=lambda _: None)
        with self.assertRaises(ProviderTransportError) as raised:
            transport.post_json("https://example.invalid", {}, {})
        self.assertIs(raised.exception.failure_kind, FailureKind.RATE_LIMITED)
        self.assertEqual(raised.exception.retry_after_seconds, 7.0)

    def test_cloudflare_known_daily_free_allocation_429_is_specialized(self) -> None:
        class FailingTransport:
            def post_json(self, url, payload, headers):
                raise ProviderTransportError(
                    failure_kind=FailureKind.RATE_LIMITED,
                    status_code=429,
                    detail='{"errors":[{"code":3036,"message":"daily free allocation"}]}',
                )

        check = CloudflareClaimVerifier("account", "token", FailingTransport()).verify(
            check_id="cf:quota",
            claim_text="claim",
            evidence_text="evidence",
            evidence_ids=("ev:1",),
        )
        self.assertIsNone(check.entailed)
        self.assertEqual(check.error_code, "free_quota_exhausted:429")


class Phase12BProviderCircuitTests(unittest.TestCase):
    def test_daily_quota_opens_circuit_and_later_calls_skip_dead_route(self) -> None:
        from insight_desk.providers.resilience import FailoverClaimVerifier

        exhausted = SequenceVerifier(
            "cloudflare-route",
            "cf-model",
            [
                VerificationCheck(
                    check_id="template",
                    verifier_id="cloudflare-route",
                    model_id="cf-model",
                    evidence_ids=("ev:1",),
                    entailed=None,
                    error_code="free_quota_exhausted:429",
                )
            ],
        )
        healthy = SequenceVerifier(
            "gemini-route",
            "gemini-model",
            [
                VerificationCheck(
                    check_id="template",
                    verifier_id="gemini-route",
                    model_id="gemini-model",
                    evidence_ids=("ev:1",),
                    entailed=True,
                ),
                VerificationCheck(
                    check_id="template",
                    verifier_id="gemini-route",
                    model_id="gemini-model",
                    evidence_ids=("ev:1",),
                    entailed=True,
                ),
            ],
        )
        verifier = FailoverClaimVerifier(
            verifier_id=CLOUDFLARE_VERIFIER_ID,
            routes=(exhausted, healthy),
        )

        first = verifier.verify(
            check_id="check:first",
            claim_text="claim",
            evidence_text="evidence",
            evidence_ids=("ev:1",),
        )
        second = verifier.verify(
            check_id="check:second",
            claim_text="claim",
            evidence_text="evidence",
            evidence_ids=("ev:1",),
        )

        self.assertTrue(first.entailed)
        self.assertTrue(second.entailed)
        self.assertEqual(exhausted.calls, 1)
        self.assertEqual(healthy.calls, 2)
        self.assertEqual(first.model_id, "gemini-model")

    def test_explicit_content_rejection_does_not_failover(self) -> None:
        from insight_desk.providers.resilience import FailoverClaimVerifier

        rejecting = SequenceVerifier(
            "route:a",
            "model:a",
            [
                VerificationCheck(
                    check_id="template",
                    verifier_id="route:a",
                    model_id="model:a",
                    evidence_ids=("ev:1",),
                    entailed=False,
                )
            ],
        )
        unused = SequenceVerifier(
            "route:b",
            "model:b",
            [
                VerificationCheck(
                    check_id="template",
                    verifier_id="route:b",
                    model_id="model:b",
                    evidence_ids=("ev:1",),
                    entailed=True,
                )
            ],
        )
        verifier = FailoverClaimVerifier(verifier_id="primary-slot", routes=(rejecting, unused))
        result = verifier.verify(
            check_id="check:reject",
            claim_text="claim",
            evidence_text="evidence",
            evidence_ids=("ev:1",),
        )
        self.assertFalse(result.entailed)
        self.assertEqual(rejecting.calls, 1)
        self.assertEqual(unused.calls, 0)


class Phase12BExactSourceFallbackTests(unittest.TestCase):
    def test_generation_failure_exact_source_fallback_needs_no_external_verifier(self) -> None:
        primary = ExplodingVerifier(CLOUDFLARE_VERIFIER_ID, "cloudflare")
        secondary = ExplodingVerifier(LOCAL_NLI_VERIFIER_ID, "local-nli")
        result = produce_phase7_entry_candidate(
            request(),
            primary_generator=AlwaysFailGenerator(),
            primary_verifier=primary,
            secondary_verifier=secondary,
        )
        self.assertTrue(result.publishable)
        self.assertEqual(result.final_generation.draft.headline, TEXT)
        self.assertEqual(result.final_generation.draft.summary, TEXT)
        self.assertEqual(primary.calls, 0)
        self.assertEqual(secondary.calls, 0)
        self.assertTrue(
            all(
                check.verifier_id == "deterministic-source-proof"
                for item in result.verification.claims
                for check in item.claim.checks
            )
        )


class Phase12BWorkflowGateTests(unittest.TestCase):
    def test_pr_live_production_requires_explicit_exact_head_marker(self) -> None:
        workflow = Path(".github/workflows/insight-desk-production.yml").read_text(encoding="utf-8")
        self.assertIn("name: Require explicit production-preflight marker", workflow)
        self.assertIn("[production-preflight]", workflow)
        self.assertIn("github.event.pull_request.head.sha", workflow)
        self.assertIn("needs.pr_live_gate.outputs.run_live == 'true'", workflow)

    def test_main_production_schedule_remains_enabled(self) -> None:
        workflow = Path(".github/workflows/insight-desk-production.yml").read_text(encoding="utf-8")
        self.assertIn('cron: "30 22 * * *"', workflow)
        self.assertIn("github.event_name != 'pull_request'", workflow)


if __name__ == "__main__":
    unittest.main()
