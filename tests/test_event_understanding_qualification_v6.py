from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from insight_desk.core import (
    ArticleEventRole,
    ArticleUnderstanding,
    CanonicalEventDraft,
    EventUnderstandingRequest,
    SourceDocument,
    TopicRelation,
    UnderstandingEvidenceField,
    UnderstandingEvidenceRef,
    UnderstandingStatus,
)
from insight_desk.providers.groq import GROQ_120B
from scripts import qualify_event_understanding_provider_v6 as v6


ROOT = Path(__file__).resolve().parents[1]


class EventUnderstandingQualificationV6Tests(unittest.TestCase):
    def test_fixture_extends_historical_minimum_with_postmerge_regressions(self) -> None:
        qualification = json.loads(
            (ROOT / "tests/fixtures/event_understanding_qualification_v6.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(qualification["schema_version"], 6)
        self.assertEqual(len(qualification["cases"]), 11)
        case_ids = {case["case_id"] for case in qualification["cases"]}
        self.assertTrue(
            {
                "run413-bok-kbs-rate-decision",
                "run413-kbo-osen-same-game-source",
                "regression-economy-background-burden",
                "regression-kbo-later-lineup-context",
                "regression-kbo-preview-stat-context",
                "regression-psat-definition-context",
                "regression-kbo-explicit-old-event-context",
                "regression-ai-generic-context",
                "regression-psat-2027-separate-test",
            }.issubset(case_ids)
        )
        psat = next(
            case
            for case in qualification["cases"]
            if case["case_id"] == "regression-psat-2027-separate-test"
        )
        self.assertTrue(psat["manual_semantic_review_required"])
        self.assertFalse(
            qualification["acceptance"]["provider_selection_eligible_from_automatic_pass_alone"]
        )

    def test_context_gold_rejects_primary_promotion_without_action_blacklist(self) -> None:
        body = (
            "한국은행은 기준금리를 0.25%포인트 인상했다. "
            "이에 따라 영끌족과 빚투 투자자의 부담이 가중되는 상황이다."
        )
        source = SourceDocument(
            source_id="source:fixture",
            candidate_ids=("candidate:fixture",),
            publisher="fixture",
            url="https://fixture.invalid/v6",
            title="한국은행 기준금리 인상, 차주 부담 확대",
            body=body,
            fetched_at=datetime(2026, 8, 30, tzinfo=timezone.utc),
            publication_time=None,
            retrieved_via="fixture",
            content_sha256=hashlib.sha256(body.encode("utf-8")).hexdigest(),
        )
        request = EventUnderstandingRequest(
            topic="economy",
            semantic_scope="Current substantive economic events.",
            sources=(source,),
        )
        context = "영끌족과 빚투 투자자의 부담이 가중되는 상황"
        start = body.index(context)
        ref = UnderstandingEvidenceRef.from_source(
            source,
            field=UnderstandingEvidenceField.BODY,
            start=start,
            end=start + len(context),
        )
        wrong = CanonicalEventDraft(
            draft_id="draft:wrong",
            topic="economy",
            actor="투자자",
            action="부담이 가중되는 상황이다",
            event_type="economic_state",
            source_ids=(source.source_id,),
            evidence_refs=(ref,),
            article_role=ArticleEventRole.PRIMARY,
            topic_relation=TopicRelation.DIRECT,
            understanding_status=UnderstandingStatus.RESOLVED,
        )
        result = ArticleUnderstanding(
            understanding_id="understanding:wrong",
            topic="economy",
            source_ids=(source.source_id,),
            event_drafts=(wrong,),
            status=UnderstandingStatus.RESOLVED,
        )
        passed, failures = v6._score_v6(
            request,
            result,
            {
                "expected_status": "resolved",
                "event_drafts_min": 1,
                "primary_direct_min": 1,
                "primary_direct_max": 1,
                "context_evidence_literals": [context],
            },
        )
        self.assertFalse(passed)
        self.assertIn("context_promoted_primary", failures)

    def test_groq_120b_is_qualification_candidate_not_production_selection(self) -> None:
        self.assertIn("groq_120b", v6.PROVIDER_CHOICES)
        self.assertEqual(v6._provider_model("groq_120b"), GROQ_120B)

        with tempfile.TemporaryDirectory() as temp_dir:
            report_path = Path(temp_dir) / "report.json"
            with patch.object(v6, "_provider_configured", return_value=False):
                code = v6.qualify(
                    provider="groq_120b",
                    qualification_path=v6.DEFAULT_QUALIFICATION,
                    scopes_path=v6.DEFAULT_SCOPES,
                    report_path=report_path,
                )
            report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(code, 2)
        self.assertEqual(report["status"], "NOT_CONFIGURED")
        self.assertFalse(report["provider_selection_eligible"])
        self.assertFalse(report["production_wired"])
        self.assertFalse(report["full_production_correctness_claimed"])


if __name__ == "__main__":
    unittest.main()
