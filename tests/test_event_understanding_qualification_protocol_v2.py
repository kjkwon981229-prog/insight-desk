from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
import unittest

from insight_desk.core import (
    ArticleEventRole,
    ArticleUnderstanding,
    CanonicalEventDraft,
    EventUnderstandingRequest,
    TopicRelation,
    UnderstandingEvidenceField,
    UnderstandingEvidenceRef,
    UnderstandingStatus,
)
from scripts import qualify_event_understanding_provider as qualification


ROOT = Path(__file__).resolve().parents[1]


def _payload() -> dict[str, object]:
    return json.loads(qualification.DEFAULT_QUALIFICATION.read_text(encoding="utf-8"))


def _source_case(case_id: str) -> tuple[dict[str, object], object]:
    payload = _payload()
    source_fixture = json.loads((ROOT / payload["source_fixture"]).read_text(encoding="utf-8"))
    raw_case = next(item for item in source_fixture["cases"] if item["case_id"] == case_id)
    clock = datetime.fromisoformat(source_fixture["replay_clock"])
    return raw_case, qualification._source_from_case(raw_case, clock)


def _draft(
    source,
    *,
    draft_id: str,
    topic: str,
    actor: str,
    action: str,
    article_role: ArticleEventRole = ArticleEventRole.PRIMARY,
    topic_relation: TopicRelation = TopicRelation.DIRECT,
    object: str | None = None,
    participants: tuple[str, ...] = (),
    parent_event_hint: str | None = None,
    evidence_field: UnderstandingEvidenceField = UnderstandingEvidenceField.BODY,
) -> CanonicalEventDraft:
    source_text = source.title if evidence_field is UnderstandingEvidenceField.TITLE else source.body
    evidence = UnderstandingEvidenceRef.from_source(
        source,
        field=evidence_field,
        start=0,
        end=len(source_text),
    )
    return CanonicalEventDraft(
        draft_id=draft_id,
        topic=topic,
        actor=actor,
        action=action,
        object=object,
        event_type="semantic_event",
        source_ids=(source.source_id,),
        evidence_refs=(evidence,),
        article_role=article_role,
        topic_relation=topic_relation,
        understanding_status=UnderstandingStatus.RESOLVED,
        participants=participants,
        parent_event_hint=parent_event_hint,
    )


def _result(source, *, topic: str, drafts: tuple[CanonicalEventDraft, ...]) -> ArticleUnderstanding:
    return ArticleUnderstanding(
        understanding_id="qualification-test-result",
        topic=topic,
        source_ids=(source.source_id,),
        event_drafts=drafts,
        status=UnderstandingStatus.RESOLVED,
    )


def _request(source, *, topic: str) -> EventUnderstandingRequest:
    return EventUnderstandingRequest(
        topic=topic,
        semantic_scope="provider-neutral qualification test scope",
        sources=(source,),
    )


class EventUnderstandingQualificationProtocolV2Tests(unittest.TestCase):
    def test_active_protocol_is_v2_and_does_not_score_free_text_by_literal_reproduction(self) -> None:
        self.assertEqual(
            qualification.DEFAULT_QUALIFICATION.name,
            "event_understanding_qualification_v2.json",
        )
        payload = _payload()
        self.assertEqual(payload["schema_version"], 2)
        self.assertFalse(payload["scoring_policy"]["free_text_literal_scoring"])
        self.assertTrue(payload["acceptance"]["free_text_literal_reproduction_forbidden"])
        for case in payload["cases"]:
            self.assertNotIn("required_structured_literals", case)
            self.assertTrue(case["expected_events"])
            for expected_event in case["expected_events"]:
                self.assertTrue(expected_event["required_evidence_literals"])
                self.assertIn("required_entity_literals", expected_event)

    def test_semantic_paraphrase_passes_without_gold_literal_in_free_text_fields(self) -> None:
        raw_case, source = _source_case("run413-bok-kbs-rate-decision")
        topic = raw_case["topic_id"]
        draft = _draft(
            source,
            draft_id="rate",
            topic=topic,
            actor="한국은행 금융통화위원회",
            action="통화정책 결정을 위한 회의를 진행한다",
        )
        expected = next(
            item for item in _payload()["cases"] if item["case_id"] == raw_case["case_id"]
        )
        passed, failures = qualification._score(
            _request(source, topic=topic),
            _result(source, topic=topic, drafts=(draft,)),
            expected,
        )
        self.assertTrue(passed, failures)
        self.assertNotIn("기준금리", draft.action)

    def test_exact_evidence_does_not_substitute_for_missing_structured_entity(self) -> None:
        raw_case, source = _source_case("run413-bok-kbs-rate-decision")
        topic = raw_case["topic_id"]
        draft = _draft(
            source,
            draft_id="missing-entity",
            topic=topic,
            actor="금융통화위원회",
            action="정책 결정을 한다",
        )
        expected = next(
            item for item in _payload()["cases"] if item["case_id"] == raw_case["case_id"]
        )
        passed, failures = qualification._score(
            _request(source, topic=topic),
            _result(source, topic=topic, drafts=(draft,)),
            expected,
        )
        self.assertFalse(passed)
        self.assertIn("expected_event_match", failures)

    def test_free_text_literal_does_not_substitute_for_missing_bound_evidence(self) -> None:
        raw_case, source = _source_case("run413-bok-kbs-rate-decision")
        topic = raw_case["topic_id"]
        draft = _draft(
            source,
            draft_id="title-only",
            topic=topic,
            actor="한국은행",
            action="기준금리를 결정한다",
            evidence_field=UnderstandingEvidenceField.TITLE,
        )
        expected = next(
            item for item in _payload()["cases"] if item["case_id"] == raw_case["case_id"]
        )
        passed, failures = qualification._score(
            _request(source, topic=topic),
            _result(source, topic=topic, drafts=(draft,)),
            expected,
        )
        self.assertFalse(passed)
        self.assertIn("expected_event_match", failures)

    def test_context_event_cannot_satisfy_primary_direct_expected_event(self) -> None:
        raw_case, source = _source_case("run413-kpop-alphadriveone-actor-preserved")
        topic = raw_case["topic_id"]
        context = _draft(
            source,
            draft_id="context",
            topic=topic,
            actor="알파드라이브원",
            action="무대를 선보인다",
            article_role=ArticleEventRole.CONTEXT,
        )
        unrelated_primary = _draft(
            source,
            draft_id="primary",
            topic=topic,
            actor="Mnet",
            action="방송을 편성한다",
        )
        expected = next(
            item for item in _payload()["cases"] if item["case_id"] == raw_case["case_id"]
        )
        passed, failures = qualification._score(
            _request(source, topic=topic),
            _result(source, topic=topic, drafts=(context, unrelated_primary)),
            expected,
        )
        self.assertFalse(passed)
        self.assertIn("expected_event_match", failures)

    def test_one_draft_cannot_satisfy_two_expected_events(self) -> None:
        raw_case, source = _source_case("run413-bok-kmib-outlook-child")
        topic = raw_case["topic_id"]
        one_draft = _draft(
            source,
            draft_id="collapsed",
            topic=topic,
            actor="한국은행",
            action="금통위 회의에서 여러 정책 자료를 다룬다",
            parent_event_hint="same meeting",
        )
        expected = deepcopy(
            next(item for item in _payload()["cases"] if item["case_id"] == raw_case["case_id"])
        )
        expected["event_drafts_min"] = 1
        expected["parent_hint_min"] = 0
        passed, failures = qualification._score(
            _request(source, topic=topic),
            _result(source, topic=topic, drafts=(one_draft,)),
            expected,
        )
        self.assertFalse(passed)
        self.assertIn("expected_event_match", failures)


if __name__ == "__main__":
    unittest.main()
