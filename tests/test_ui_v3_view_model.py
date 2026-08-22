import importlib.util
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

from insight_desk.core import (
    CandidateEvent,
    ContractBundle,
    EvidenceField,
    EvidenceSpan,
    EventFact,
    RawArticle,
    RenderMode,
    RenderedBriefing,
    RenderedEntry,
    SourceProvenance,
    TemporalState,
    VerificationCheck,
    VerificationVerdict,
    VerifiedClaim,
)


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "design" / "prototype-v3" / "view_model.py"
HTML = (ROOT / "design" / "prototype-v3" / "index.html").read_text(encoding="utf-8")
SPEC = importlib.util.spec_from_file_location("ui_v3_view_model", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def make_bundle(*, with_partial_failure: bool = False) -> ContractBundle:
    now = datetime(2026, 8, 23, 1, 0, tzinfo=timezone.utc)
    body = "신규 AI 규제안은 9월 3일부터 시행한다. 적용 대상은 별도 고시한다."
    article = RawArticle(
        article_id="a1",
        provenance=SourceProvenance(
            source_id="s1",
            source_name="공식 발표",
            url="https://example.invalid/official",
            retrieved_via="fixture",
            fetched_at=now,
            published_at=now,
        ),
        title="신규 AI 규제안 시행 일정 발표",
        body=body,
        topic_ids=("ai-tech",),
    )
    phrase = "9월 3일부터 시행한다"
    start = body.index(phrase)
    evidence = EvidenceSpan.from_article(
        evidence_id="e1",
        article=article,
        field=EvidenceField.BODY,
        start=start,
        end=start + len(phrase),
    )
    fact = EventFact(
        fact_id="f1",
        subject="신규 AI 규제안",
        action="시행한다",
        object="규제안",
        evidence_ids=("e1",),
        temporal_state=TemporalState.ANNOUNCED_PROSPECTIVE,
        event_date="2026-09-03",
    )
    event = CandidateEvent(
        event_id="event-1",
        topic_id="ai-tech",
        fact_ids=("f1",),
        article_ids=("a1",),
    )
    checks = [
        VerificationCheck(
            check_id="c1",
            verifier_id="cloudflare",
            model_id="llama-3.3-70b",
            evidence_ids=("e1",),
            entailed=True,
        )
    ]
    if with_partial_failure:
        checks.append(
            VerificationCheck(
                check_id="c2",
                verifier_id="local-nli",
                model_id="mdeberta",
                evidence_ids=("e1",),
                entailed=None,
                error_code="TEMPORARY_MODEL_FAILURE",
            )
        )
    claim = VerifiedClaim(
        claim_id="claim-1",
        event_id="event-1",
        text="신규 AI 규제안은 9월 3일부터 시행될 예정이다.",
        evidence_ids=("e1",),
        checks=tuple(checks),
        verdict=VerificationVerdict.SUPPORTED,
    )
    entry = RenderedEntry(
        event_id="event-1",
        headline="AI 규제안, 9월 초 시행 일정 발표",
        summary="새로운 점은 규제의 존재가 아니라 실제 시행 시점이 생겼다는 것입니다.",
        claim_ids=("claim-1",),
        render_mode=RenderMode.GENERATED,
    )
    briefing = RenderedBriefing(
        briefing_id="briefing-1",
        generated_at=now,
        entries=(entry,),
    )
    return ContractBundle(
        articles=(article,),
        evidence=(evidence,),
        facts=(fact,),
        events=(event,),
        claims=(claim,),
        briefing=briefing,
    )


class UiV3ViewModelTests(unittest.TestCase):
    def test_supported_entry_maps_without_inventing_confidence_or_history(self):
        bundle = make_bundle()
        view = MODULE.build_briefing_views(bundle)[0]
        self.assertEqual(view.headline, "AI 규제안, 9월 초 시행 일정 발표")
        self.assertEqual(view.state_label, "발표 → 예정")
        self.assertEqual(view.event_date, "2026-09-03")
        self.assertEqual(view.evidence_count, 1)
        self.assertEqual(view.evidence[0].source_name, "공식 발표")
        self.assertEqual(view.verdict_label, "검증 완료")
        self.assertEqual(view.render_mode_label, "검증 생성")
        self.assertIsNone(view.watch_next)
        self.assertFalse(view.history_available)
        self.assertFalse(hasattr(view, "confidence"))

    def test_partial_verifier_failure_remains_visible_even_when_claim_is_supported(self):
        bundle = make_bundle(with_partial_failure=True)
        view = MODULE.build_briefing_views(bundle)[0]
        self.assertTrue(view.has_partial_verifier_failure)
        self.assertEqual(view.verdict_label, "검증 완료")

    def test_empty_briefing_maps_to_empty_ui(self):
        bundle = ContractBundle()
        self.assertEqual(MODULE.build_briefing_views(bundle), ())

    def test_static_prototype_does_not_display_unsupported_numeric_confidence(self):
        self.assertNotIn("CONF.", HTML)
        self.assertNotIn("0.98", HTML)
        self.assertIn("VERDICT", HTML)
        self.assertIn("검증 완료", HTML)


if __name__ == "__main__":
    unittest.main()
