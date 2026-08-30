from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import unittest

from insight_desk.core import (
    CandidateEvent,
    EvidenceField,
    EvidenceSpan,
    EventFact,
    FailureKind,
)
from insight_desk.generation import GeneratedDraft, GenerationRequest, Groq20BBriefingGenerator
from insight_desk.generation_pipeline import generate_with_recovery
from insight_desk.providers.groq import GROQ_20B, GroqFreeClient
from insight_desk.providers.transport import ProviderTransportError


TEXT = "네오팩토리가 AI 공장 구축 사업을 15억달러에 수주했다."
HEADLINE = "네오팩토리 AI 공장 구축 사업 15억달러 수주"


def request() -> GenerationRequest:
    span = EvidenceSpan(
        evidence_id="ev:phase12b-generation",
        article_id="article:phase12b-generation",
        field=EvidenceField.BODY,
        start=0,
        end=len(TEXT),
        text=TEXT,
    )
    fact = EventFact(
        fact_id="fact:phase12b-generation",
        subject="네오팩토리",
        action="AI 공장 구축 사업을 15억달러에 수주했다",
        object="AI 공장 구축 사업",
        evidence_ids=(span.evidence_id,),
    )
    event = CandidateEvent(
        event_id="event:phase12b-generation",
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
class RateLimitedTransport:
    calls: int = 0

    def post_json(self, url, payload, headers):
        self.calls += 1
        raise ProviderTransportError(
            failure_kind=FailureKind.RATE_LIMITED,
            status_code=429,
            retry_after_seconds=60.0,
        )


@dataclass
class HealthyAlternate:
    calls: int = 0

    def generate(self, item: GenerationRequest) -> GeneratedDraft:
        self.calls += 1
        return GeneratedDraft(
            event_id=item.event.event_id,
            headline=HEADLINE,
            summary=TEXT,
            evidence_ids=item.evidence_ids,
        )


class Phase12BGenerationCircuitTests(unittest.TestCase):
    def test_groq_rate_limit_is_observed_once_before_alternate_generation(self) -> None:
        transport = RateLimitedTransport()
        groq = Groq20BBriefingGenerator(
            GroqFreeClient(
                api_key="test",
                model_id=GROQ_20B,
                transport=transport,
                delay_seconds=0,
            )
        )
        alternate = HealthyAlternate()

        result = generate_with_recovery(
            request(),
            primary=groq,
            alternate=alternate,
        )

        self.assertEqual(transport.calls, 1)
        self.assertEqual(alternate.calls, 1)
        self.assertEqual(result.draft.headline, HEADLINE)
        self.assertEqual(result.attempts[0].error_code, "rate_limited:429")

    def test_recovery_layer_wires_optional_gemini_without_removing_exact_fallback(self) -> None:
        source = Path("insight_desk/generation_pipeline.py").read_text(encoding="utf-8")
        self.assertIn("GeminiStructuredClient.configured()", source)
        self.assertIn("GeminiBriefingGenerator", source)
        self.assertIn("_configured_zero_cost_alternate", source)
        self.assertIn("ExtractiveFallbackGenerator().generate(request)", source)


if __name__ == "__main__":
    unittest.main()
