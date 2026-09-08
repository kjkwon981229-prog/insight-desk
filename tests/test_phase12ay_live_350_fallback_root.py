from __future__ import annotations

from dataclasses import dataclass, field
import unittest

from insight_desk.core import CandidateEvent, EvidenceField, EvidenceSpan, EventFact, RenderMode
from insight_desk.generation import GeneratedDraft, GenerationRequest
from insight_desk.generation_pipeline import GenerationAttemptKind, generate_with_recovery


EVENT_SENTENCE = "네오팩토리가 AI 공장 구축 사업을 15억달러에 수주했다."


def request(text: str) -> GenerationRequest:
    span = EvidenceSpan(
        evidence_id="ev:live350-fallback",
        article_id="article:live350-fallback",
        field=EvidenceField.BODY,
        start=0,
        end=len(text),
        text=text,
    )
    fact = EventFact(
        fact_id="fact:live350-fallback",
        subject="네오팩토리",
        action="AI 공장 구축 사업을 15억달러에 수주했다",
        object="AI 공장 구축 사업",
        evidence_ids=(span.evidence_id,),
    )
    event = CandidateEvent(
        event_id="event:live350-fallback",
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
class FailingGenerator:
    calls: int = 0
    outcomes: list[Exception] = field(
        default_factory=lambda: [RuntimeError("primary-a"), RuntimeError("primary-b")]
    )

    def generate(self, item: GenerationRequest) -> GeneratedDraft:
        self.calls += 1
        raise self.outcomes.pop(0)


class Live350FallbackRootRegressions(unittest.TestCase):
    def test_exact_fallback_skips_leading_timestamp_chrome_and_keeps_event(self) -> None:
        text = "- 입력 2026.08.26 13:41\n" + EVENT_SENTENCE
        result = generate_with_recovery(request(text), primary=FailingGenerator())

        self.assertIs(result.render_mode, RenderMode.EXTRACTIVE_FALLBACK)
        self.assertNotIn("입력 2026.08.26", result.draft.headline)
        self.assertNotIn("입력 2026.08.26", result.draft.summary)
        self.assertEqual(result.draft.summary, EVENT_SENTENCE)
        self.assertIn("AI 공장 구축 사업을 15억달러에 수주했다", result.draft.headline)
        self.assertIs(result.attempts[-1].kind, GenerationAttemptKind.EXTRACTIVE_FALLBACK)

    def test_clean_first_line_remains_the_exact_fallback_headline(self) -> None:
        title = "AI 공장 15억달러 수주"
        text = title + "\n" + EVENT_SENTENCE
        result = generate_with_recovery(request(text), primary=FailingGenerator())

        self.assertIs(result.render_mode, RenderMode.EXTRACTIVE_FALLBACK)
        self.assertEqual(result.draft.headline, title)
        self.assertEqual(result.draft.summary, EVENT_SENTENCE)


if __name__ == "__main__":
    unittest.main()
