from __future__ import annotations

import unittest

from insight_desk.core import RelevanceDecision, RelevanceReason, RelevanceVerdict
from insight_desk.production_relevance_v2 import (
    project_event_relevance,
    rewrite_event_relevance_attempt,
)


class RelevanceDeferAuditProjectionTests(unittest.TestCase):
    def test_defer_is_not_collapsed_into_skip_in_legacy_loop_audit(self) -> None:
        decision = RelevanceDecision(
            topic_id="fixture",
            verdict=RelevanceVerdict.DEFER,
            evidence_refs=("ev-1",),
            reasons=(RelevanceReason.RESOLUTION_REQUIRED,),
        )
        self.assertFalse(project_event_relevance(decision))
        status, reason = rewrite_event_relevance_attempt(
            stage="event_topic_relevance",
            status="skip",
            reason="configured_literal_missing_in_event_evidence",
        )
        self.assertEqual(status, "defer")
        self.assertEqual(reason, RelevanceReason.RESOLUTION_REQUIRED.value)

    def test_projection_does_not_rewrite_unrelated_audit_stage(self) -> None:
        decision = RelevanceDecision(
            topic_id="fixture",
            verdict=RelevanceVerdict.DEFER,
            evidence_refs=("ev-1",),
            reasons=(RelevanceReason.RESOLUTION_REQUIRED,),
        )
        self.assertFalse(project_event_relevance(decision))
        status, reason = rewrite_event_relevance_attempt(
            stage="acquisition",
            status="skip",
            reason="network_error",
        )
        self.assertEqual((status, reason), ("skip", "network_error"))
        status, reason = rewrite_event_relevance_attempt(
            stage="event_topic_relevance",
            status="skip",
            reason="configured_literal_missing_in_event_evidence",
        )
        self.assertEqual(status, "defer")
        self.assertEqual(reason, RelevanceReason.RESOLUTION_REQUIRED.value)


if __name__ == "__main__":
    unittest.main()
