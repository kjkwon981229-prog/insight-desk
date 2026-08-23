from __future__ import annotations

from dataclasses import dataclass
import unittest

from insight_desk.core import CandidateEvent, EvidenceField, EvidenceSpan, EventFact
from insight_desk.generation import (
    GeneratedDraft,
    GenerationContractError,
    GenerationRequest,
    Groq20BBriefingGenerator,
    NEWS_REWRITE_POLICY_V1,
    PreservationIssueCode,
    build_generation_prompt,
    validate_preservation,
)
from insight_desk.providers.groq import GROQ_20B, GROQ_120B


SOURCE = (
    '한국은행 부총재는 "물가 흐름을 더 지켜봐야 한다"고 밝혔다. '
    '원·달러 환율은 1386.5원으로 마감했다. 2026-08-23 기준이다.'
)


def request() -> GenerationRequest:
    span = EvidenceSpan(
        evidence_id="ev:phase7",
        article_id="article:phase7",
        field=EvidenceField.BODY,
        start=0,
        end=len(SOURCE),
        text=SOURCE,
    )
    fact = EventFact(
        fact_id="fact:phase7",
        subject="한국은행 부총재",
        action='"물가 흐름을 더 지켜봐야 한다"고 밝혔다',
        object=None,
        event_date="2026-08-23",
        evidence_ids=(span.evidence_id,),
    )
    event = CandidateEvent(
        event_id="event:phase7",
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
class FakeStructuredClient:
    model_id: str = GROQ_20B
    output: dict[str, object] | None = None
    last_prompt: str | None = None
    last_schema_name: str | None = None

    def structured_json(
        self,
        *,
        prompt: str,
        schema: dict[str, object],
        schema_name: str,
        system_prompt: str = "",
    ) -> dict[str, object]:
        self.last_prompt = prompt
        self.last_schema_name = schema_name
        return self.output or {
            "headline": "한국은행, 물가 흐름 추가 관찰",
            "summary": '한국은행 부총재는 "물가 흐름을 더 지켜봐야 한다"고 밝혔다.',
        }


class Phase7GenerationContractTests(unittest.TestCase):
    def test_generation_request_preserves_event_fact_evidence_order(self) -> None:
        item = request()
        self.assertEqual(item.evidence_ids, ("ev:phase7",))
        self.assertEqual(item.evidence_text, SOURCE)
        self.assertIn("subject=한국은행 부총재", item.fact_text)
        self.assertIn("event_date=2026-08-23", item.fact_text)

    def test_generation_request_rejects_foreign_evidence_provenance(self) -> None:
        item = request()
        span = item.evidence["ev:phase7"]
        foreign = EvidenceSpan(
            evidence_id=span.evidence_id,
            article_id="article:foreign",
            field=span.field,
            start=span.start,
            end=span.end,
            text=span.text,
        )
        with self.assertRaises(GenerationContractError):
            GenerationRequest(
                event=item.event,
                facts=item.facts,
                evidence={foreign.evidence_id: foreign},
            )

    def test_prompt_contains_authoritative_complete_policy_and_exact_source_context(self) -> None:
        prompt = build_generation_prompt(request())
        self.assertIn("0-1) 숫자·날짜·고유명사·인용문은 원문 그대로 유지해라.", prompt)
        self.assertIn("1-3) 길이를 맞춰라.", prompt)
        self.assertIn("2-3) 원문에 없는 주관적 수식어는 특히 금지해라.", prompt)
        self.assertIn("3-1) 기사마다 같은 출력 구조를 유지해라.", prompt)
        self.assertIn("3-2) 불확실하면 변형을 최소화해라.", prompt)
        self.assertIn("3-3) 메타 발언 금지는 그대로 유지해라.", prompt)
        self.assertIn('"이 기사에서는", "요약하자면"', prompt)
        self.assertIn(SOURCE, prompt)
        self.assertNotIn("recovered rules only", prompt)
        self.assertIn("사실 보존", NEWS_REWRITE_POLICY_V1)

    def test_generator_is_frozen_to_groq20b_and_cites_request_evidence(self) -> None:
        client = FakeStructuredClient()
        draft = Groq20BBriefingGenerator(client).generate(request())
        self.assertEqual(draft.event_id, "event:phase7")
        self.assertEqual(draft.evidence_ids, ("ev:phase7",))
        self.assertEqual(client.last_schema_name, "insight_desk_briefing_generation")
        self.assertIn(SOURCE, client.last_prompt or "")

        with self.assertRaises(GenerationContractError):
            Groq20BBriefingGenerator(FakeStructuredClient(model_id=GROQ_120B))

    def test_preservation_accepts_exact_source_number_date_and_quote(self) -> None:
        draft = GeneratedDraft(
            event_id="event:phase7",
            headline="환율 1386.5원 마감",
            summary='2026-08-23 한국은행 부총재는 "물가 흐름을 더 지켜봐야 한다"고 밝혔다.',
            evidence_ids=("ev:phase7",),
        )
        report = validate_preservation(request(), draft)
        self.assertTrue(report.accepted)
        self.assertEqual(report.issues, ())

    def test_preservation_rejects_novel_number_and_date_before_verifiers(self) -> None:
        draft = GeneratedDraft(
            event_id="event:phase7",
            headline="환율 1390.0원 마감",
            summary="2026-08-24 기준으로 변동했다.",
            evidence_ids=("ev:phase7",),
        )
        report = validate_preservation(request(), draft)
        self.assertFalse(report.accepted)
        codes = {issue.code for issue in report.issues}
        self.assertIn(PreservationIssueCode.NOVEL_NUMBER, codes)
        self.assertIn(PreservationIssueCode.NOVEL_DATE, codes)

    def test_preservation_rejects_invented_quotation(self) -> None:
        draft = GeneratedDraft(
            event_id="event:phase7",
            headline="한국은행 물가 판단",
            summary='한국은행 부총재는 "금리 인하가 임박했다"고 밝혔다.',
            evidence_ids=("ev:phase7",),
        )
        report = validate_preservation(request(), draft)
        self.assertFalse(report.accepted)
        self.assertIn(
            PreservationIssueCode.NOVEL_QUOTED_TEXT,
            {issue.code for issue in report.issues},
        )

    def test_preservation_rejects_section3_meta_phrases(self) -> None:
        for phrase in ("이 기사에서는", "요약하자면"):
            draft = GeneratedDraft(
                event_id="event:phase7",
                headline="한국은행 물가 판단",
                summary=f"{phrase} 한국은행 부총재가 물가 흐름을 더 관찰하겠다고 밝혔다.",
                evidence_ids=("ev:phase7",),
            )
            report = validate_preservation(request(), draft)
            self.assertFalse(report.accepted)
            self.assertIn(
                PreservationIssueCode.META_PHRASE,
                {issue.code for issue in report.issues},
            )

    def test_preservation_rejects_cross_event_or_unknown_evidence(self) -> None:
        draft = GeneratedDraft(
            event_id="event:other",
            headline="한국은행 물가 판단",
            summary="한국은행 부총재가 물가 흐름을 지켜본다고 밝혔다.",
            evidence_ids=("ev:foreign",),
        )
        report = validate_preservation(request(), draft)
        self.assertFalse(report.accepted)
        codes = {issue.code for issue in report.issues}
        self.assertIn(PreservationIssueCode.EVENT_ID_MISMATCH, codes)
        self.assertIn(PreservationIssueCode.UNKNOWN_EVIDENCE, codes)

    def test_semantic_paraphrase_without_new_protected_atoms_is_left_for_verification(self) -> None:
        draft = GeneratedDraft(
            event_id="event:phase7",
            headline="한국은행 물가 판단",
            summary="한국은행 부총재가 물가 흐름을 더 관찰하겠다는 뜻을 밝혔다.",
            evidence_ids=("ev:phase7",),
        )
        report = validate_preservation(request(), draft)
        self.assertTrue(report.accepted)
        # General entailment is deliberately not claimed by this deterministic gate.


if __name__ == "__main__":
    unittest.main()
