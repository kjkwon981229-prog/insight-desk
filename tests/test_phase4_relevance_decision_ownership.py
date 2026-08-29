from __future__ import annotations

from pathlib import Path
import unittest

from insight_desk.core import (
    RelevanceDecision,
    RelevanceReason,
    RelevanceVerdict,
)


class RelevanceDecisionContractTests(unittest.TestCase):
    def test_relevance_contract_preserves_explicit_defer(self) -> None:
        decision = RelevanceDecision(
            topic_id="economy",
            verdict=RelevanceVerdict.DEFER,
            evidence_refs=(),
            reasons=(RelevanceReason.RESOLUTION_REQUIRED,),
        )
        self.assertEqual(decision.verdict, RelevanceVerdict.DEFER)
        self.assertFalse(decision.is_relevant)
        self.assertTrue(decision.requires_resolution)

    def test_relevance_contract_requires_reason_codes(self) -> None:
        with self.assertRaises(ValueError):
            RelevanceDecision(
                topic_id="economy",
                verdict=RelevanceVerdict.IRRELEVANT,
                evidence_refs=(),
                reasons=(),
            )


class ProductionRelevanceOwnershipTests(unittest.TestCase):
    def test_daily_production_consumes_typed_relevance_decision(self) -> None:
        source = Path("scripts/phase11_daily_production_core.py").read_text(encoding="utf-8")
        self.assertIn("source_relevance = relevance_decision(", source)
        self.assertIn("RelevanceVerdict.IRRELEVANT", source)
        self.assertIn("RelevanceVerdict.DEFER", source)
        self.assertIn('stage="topic_relevance"', source)
        self.assertIn('status="defer"', source)
        self.assertNotIn("if not topic_relevant(title=article.title, body=article.body, topic=topic):", source)

    def test_v2_runtime_installs_one_relevance_decision_owner(self) -> None:
        source = Path("insight_desk/production_runtime_v2.py").read_text(encoding="utf-8")
        self.assertIn("ConfiguredLiteralRelevanceOwner", source)
        self.assertIn("core_module.relevance_decision = relevance_owner.decide", source)


if __name__ == "__main__":
    unittest.main()
