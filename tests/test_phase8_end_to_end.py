from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import unittest

from insight_desk.core import CandidateEvent, EvidenceField, EvidenceSpan, EventFact, VerificationCheck
from insight_desk.generation import GeneratedDraft, GenerationRequest
from insight_desk.phase7 import produce_phase7_entry_candidate
from insight_desk.providers.cloudflare import CLOUDFLARE_VERIFIER_ID
from insight_desk.providers.local_nli import LOCAL_NLI_VERIFIER_ID
from insight_desk.rendering import build_rendered_briefing
from insight_desk.ui import PwaRuntimeConfig, build_briefing_view_model, render_briefing_html


@dataclass
class Generator:
    headline: str
    summary: str

    def generate(self, request: GenerationRequest) -> GeneratedDraft:
        return GeneratedDraft(
            event_id=request.event.event_id,
            headline=self.headline,
            summary=self.summary,
            evidence_ids=request.evidence_ids,
        )


@dataclass
class Verifier:
    verifier_id: str
    model_id: str
    answers: list[bool | None] = field(default_factory=list)

    def verify(
        self,
        *,
        check_id: str,
        claim_text: str,
        evidence_text: str,
        evidence_ids: tuple[str, ...],
    ) -> VerificationCheck:
        answer = self.answers.pop(0) if self.answers else True
        return VerificationCheck(
            check_id=check_id,
            verifier_id=self.verifier_id,
            model_id=self.model_id,
            evidence_ids=evidence_ids,
            entailed=answer,
            error_code=None if answer is not None else "synthetic_indeterminate",
            zero_cost=True,
        )


def request(event_id: str, text: str) -> GenerationRequest:
    span = EvidenceSpan(
        evidence_id=f"ev:{event_id}",
        article_id=f"article:{event_id}",
        field=EvidenceField.BODY,
        start=0,
        end=len(text),
        text=text,
    )
    fact = EventFact(
        fact_id=f"fact:{event_id}",
        subject=text.split("가", 1)[0],
        action=text,
        evidence_ids=(span.evidence_id,),
    )
    event = CandidateEvent(
        event_id=event_id,
        topic_id="ai_tech",
        fact_ids=(fact.fact_id,),
        article_ids=(span.article_id,),
    )
    return GenerationRequest(
        event=event,
        facts={fact.fact_id: fact},
        evidence={span.evidence_id: span},
    )


def candidate(event_id: str, text: str, *, supported: bool):
    primary_answers = [True, True] if supported else [None, None]
    return produce_phase7_entry_candidate(
        request(event_id, text),
        primary_generator=Generator(headline=text, summary=text),
        primary_verifier=Verifier(
            CLOUDFLARE_VERIFIER_ID,
            "@cf/meta/llama-3.3-70b-instruct-fp8-fast",
            primary_answers,
        ),
        secondary_verifier=Verifier(
            LOCAL_NLI_VERIFIER_ID,
            "MoritzLaurer/mDeBERTa-v3-base-mnli-xnli",
            [True, True],
        ),
    )


class Phase8EndToEndTests(unittest.TestCase):
    def test_verified_candidate_flows_to_locked_pwa_html_and_unpublishable_item_is_omitted(self) -> None:
        accepted_text = "네오팩토리가 AI 공장 구축 사업을 수주했다."
        rejected_text = "검증이 끝나지 않은 별도 사건이다."
        accepted = candidate("event:accepted", accepted_text, supported=True)
        rejected = candidate("event:rejected", rejected_text, supported=False)

        rendered = build_rendered_briefing(
            briefing_id="briefing:phase8-e2e",
            generated_at=datetime(2026, 8, 23, 13, 19, tzinfo=timezone.utc),
            candidates=(accepted, rejected),
        )
        view = build_briefing_view_model(
            rendered,
            topic_by_event={"event:accepted": "AI·테크"},
        )
        html = render_briefing_html(
            view,
            runtime=PwaRuntimeConfig(push_worker_url="https://push.example.workers.dev"),
        )

        self.assertEqual([entry.event_id for entry in rendered.entries], ["event:accepted"])
        self.assertIn(accepted_text, html)
        self.assertIn("AI·테크", html)
        self.assertNotIn(rejected_text, html)
        self.assertIn('rel="manifest" href="manifest.webmanifest"', html)
        self.assertIn('data-push-service-worker-url="push-sw.js"', html)
        self.assertIn('<script src="assets/js/push.js" defer></script>', html)
        self.assertNotIn("key-fact-panel", html)
        self.assertNotIn("next-signal", html)
        self.assertNotIn("검색 관심 흐름", html)


if __name__ == "__main__":
    unittest.main()
