from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import unittest

from insight_desk.acquisition import DiscoveryConfigError, default_news_discovery
from insight_desk.core import (
    CandidateEvent,
    EvidenceField,
    EvidenceSpan,
    EventFact,
    RenderMode,
    VerificationCheck,
)
from insight_desk.generation import GeneratedDraft, GenerationRequest
from insight_desk.generation_pipeline import GenerationAttemptKind, generate_with_recovery
from insight_desk.phase7 import VerificationRecoveryReason, produce_phase7_entry_candidate
from insight_desk.providers.cloudflare import CLOUDFLARE_VERIFIER_ID, CloudflareClaimVerifier
from insight_desk.providers.groq import GROQ_20B, GroqFreeClient
from insight_desk.providers.resilience import FailoverClaimVerifier, UnavailableClaimVerifier
from insight_desk.providers.transport import ProviderConfigError


TEXT = "정부는 9월 3일부터 새 제도를 시행한다고 밝혔다."
FALLBACK_HEADLINE = "9월 3일부터 새 제도를 시행한다고 밝혔다"


def request() -> GenerationRequest:
    span = EvidenceSpan(
        evidence_id="ev:control-plane",
        article_id="article:control-plane",
        field=EvidenceField.BODY,
        start=0,
        end=len(TEXT),
        text=TEXT,
    )
    fact = EventFact(
        fact_id="fact:control-plane",
        subject="정부",
        action=FALLBACK_HEADLINE,
        evidence_ids=(span.evidence_id,),
    )
    event = CandidateEvent(
        event_id="event:control-plane",
        topic_id="economy",
        fact_ids=(fact.fact_id,),
        article_ids=(span.article_id,),
    )
    return GenerationRequest(
        event=event,
        facts={fact.fact_id: fact},
        evidence={span.evidence_id: span},
    )


@dataclass
class HealthyGenerator:
    calls: int = 0

    def generate(self, item: GenerationRequest) -> GeneratedDraft:
        self.calls += 1
        return GeneratedDraft(
            event_id=item.event.event_id,
            headline=FALLBACK_HEADLINE,
            summary=TEXT,
            evidence_ids=item.evidence_ids,
        )


@dataclass
class ConstantVerifier:
    verifier_id: str
    model_id: str
    entailed: bool | None
    error_code: str | None = None
    calls: int = 0

    def verify(self, *, check_id: str, claim_text: str, evidence_text: str, evidence_ids: tuple[str, ...]) -> VerificationCheck:
        del claim_text, evidence_text
        self.calls += 1
        return VerificationCheck(
            check_id=check_id,
            verifier_id=self.verifier_id,
            model_id=self.model_id,
            evidence_ids=evidence_ids,
            entailed=self.entailed,
            error_code=self.error_code,
            zero_cost=True,
        )


class RecordingTransport:
    def post_json(self, url, payload, headers):
        raise AssertionError("factory contract test must not call Gemini")


class Phase12BControlPlaneResilienceTests(unittest.TestCase):
    def test_generation_can_start_without_groq_and_use_alternate(self) -> None:
        alternate = HealthyGenerator()
        result = generate_with_recovery(request(), primary=None, alternate=alternate)
        self.assertEqual(alternate.calls, 1)
        self.assertEqual(result.attempts[0].kind, GenerationAttemptKind.ALTERNATE)
        self.assertEqual(result.render_mode, RenderMode.GENERATED)

    def test_generation_without_any_provider_uses_exact_source(self) -> None:
        result = generate_with_recovery(request(), primary=None, alternate=None)
        self.assertEqual(result.render_mode, RenderMode.EXTRACTIVE_FALLBACK)
        self.assertEqual(result.draft.headline, FALLBACK_HEADLINE)
        self.assertEqual(result.draft.summary, TEXT)
        self.assertIn(result.draft.headline, TEXT)

    def test_groq_configuration_is_optional_and_detectable(self) -> None:
        self.assertFalse(GroqFreeClient.configured({}, model_id=GROQ_20B))
        self.assertTrue(GroqFreeClient.configured({"GROQ_API_KEY": "key"}, model_id=GROQ_20B))

    def test_discovery_without_naver_credentials_keeps_independent_free_routes(self) -> None:
        discovery = default_news_discovery(env={})
        self.assertEqual(
            [route.route_id for route in discovery.routes],
            ["bing_news_rss", "gdelt_doc"],
        )

    def test_partial_naver_credentials_fail_fast(self) -> None:
        with self.assertRaises(DiscoveryConfigError):
            default_news_discovery(env={"NCP_CLIENT_ID": "client"})

    def test_primary_verifier_can_start_with_gemini_only(self) -> None:
        verifier = CloudflareClaimVerifier.from_env(
            env={"GEMINI_API_KEY": "gemini"},
            gemini_transport=RecordingTransport(),
        )
        self.assertIsInstance(verifier, FailoverClaimVerifier)
        self.assertEqual(verifier.verifier_id, CLOUDFLARE_VERIFIER_ID)
        self.assertEqual(len(verifier.routes), 1)
        self.assertEqual(verifier.routes[0].verifier_id, "gemini")

    def test_primary_verifier_without_external_credentials_is_explicitly_unavailable(self) -> None:
        verifier = CloudflareClaimVerifier.from_env(env={})
        self.assertIsInstance(verifier, UnavailableClaimVerifier)
        check = verifier.verify(
            check_id="missing:1",
            claim_text="claim",
            evidence_text="evidence",
            evidence_ids=("ev:1",),
        )
        self.assertIsNone(check.entailed)
        self.assertEqual(check.error_code, "config_missing")

    def test_partial_cloudflare_credentials_fail_fast(self) -> None:
        with self.assertRaises(ProviderConfigError):
            CloudflareClaimVerifier.from_env(env={"CLOUDFLARE_ACCOUNT_ID": "account"})

    def test_verifier_infrastructure_indeterminate_recovers_to_exact_source(self) -> None:
        primary_generator = HealthyGenerator()
        primary_verifier = ConstantVerifier(
            CLOUDFLARE_VERIFIER_ID,
            "unavailable-primary",
            None,
            "insufficient_verification_capacity:config_missing",
        )
        secondary_verifier = ConstantVerifier("local-nli", "mdeberta", True)

        result = produce_phase7_entry_candidate(
            request(),
            primary_generator=primary_generator,
            primary_verifier=primary_verifier,
            secondary_verifier=secondary_verifier,
        )

        self.assertTrue(result.publishable)
        self.assertEqual(result.final_generation.render_mode, RenderMode.EXTRACTIVE_FALLBACK)
        self.assertEqual(result.final_generation.draft.headline, FALLBACK_HEADLINE)
        self.assertEqual(result.final_generation.draft.summary, TEXT)
        self.assertEqual(
            result.verification_recovery_reason,
            VerificationRecoveryReason.GENERATED_VERIFICATION_UNAVAILABLE,
        )

    def test_workflow_does_not_block_zero_cost_fallback_on_optional_provider_keys(self) -> None:
        workflow = Path(".github/workflows/insight-desk-production.yml").read_text(encoding="utf-8")
        self.assertNotIn("PHASE11_CREDENTIALS_MISSING", workflow)
        self.assertNotIn("PHASE11_CREDENTIALS_PRESENT", workflow)
        self.assertIn("PHASE12B_PROVIDER_ROUTES", workflow)
        self.assertIn("PHASE12B_PARTIAL_PROVIDER_CONFIG", workflow)


if __name__ == "__main__":
    unittest.main()
