from __future__ import annotations

import unittest

from insight_desk.core import (
    IdentityKey,
    IdentityPrecheckVerdict,
    SelectionReason,
    SelectionSignals,
    SelectionVerdict,
    decide_selection,
    finalize_identity,
    precheck_identity,
)


class EventIdentityTests(unittest.TestCase):
    def test_different_event_dates_are_a_non_overridable_merge_block(self) -> None:
        left = IdentityKey(
            subject_key="hanwha-doosan",
            action_key="cancel",
            event_date_key="2026-08-12",
            location_key="seoul",
            cause_key="heat",
        )
        right = IdentityKey(
            subject_key="hanwha-doosan",
            action_key="cancel",
            event_date_key="2026-08-13",
            location_key="seoul",
            cause_key="heat",
        )
        precheck = precheck_identity(left, right)
        self.assertEqual(precheck.verdict, IdentityPrecheckVerdict.BLOCK_MERGE)
        self.assertIn("event_date", precheck.conflicting_fields)

        # Even a mistaken same-event judgment cannot override explicit canonical date conflict.
        decision = finalize_identity(precheck, llm_same_event=True)
        self.assertFalse(decision.same_event)
        self.assertTrue(decision.deterministic_block)
        self.assertFalse(decision.llm_judgment_used)

    def test_no_deterministic_conflict_still_requires_explicit_identity_judgment(self) -> None:
        left = IdentityKey(
            subject_key="kbo",
            action_key="resume",
            event_date_key="2026-08-11",
            cause_key="heat",
        )
        right = IdentityKey(
            subject_key="kbo",
            action_key="resume",
            event_date_key="2026-08-11",
            cause_key="heat",
        )
        precheck = precheck_identity(left, right)
        self.assertEqual(precheck.verdict, IdentityPrecheckVerdict.REQUIRE_LLM_JUDGMENT)

        unavailable = finalize_identity(precheck, llm_same_event=None)
        self.assertIsNone(unavailable.same_event)
        self.assertFalse(unavailable.llm_judgment_used)

        supported = finalize_identity(precheck, llm_same_event=True)
        self.assertTrue(supported.same_event)
        self.assertTrue(supported.llm_judgment_used)

    def test_different_canonical_subjects_are_not_silently_merged(self) -> None:
        precheck = precheck_identity(
            IdentityKey(subject_key="company-a", action_key="invest"),
            IdentityKey(subject_key="company-b", action_key="invest"),
        )
        self.assertEqual(precheck.verdict, IdentityPrecheckVerdict.BLOCK_MERGE)
        self.assertIn("subject", precheck.conflicting_fields)


class SelectionPolicyTests(unittest.TestCase):
    def test_real_event_can_be_excluded_without_becoming_a_non_event(self) -> None:
        signals = SelectionSignals(
            topic_relevant=False,
            material_event=True,
            fresh=True,
            source_usable=True,
            identity_resolved=True,
        )
        decision = decide_selection(signals)
        self.assertEqual(decision.verdict, SelectionVerdict.EXCLUDE)
        self.assertEqual(decision.reasons, (SelectionReason.TOPIC_IRRELEVANT,))
        self.assertTrue(signals.material_event)

    def test_unknown_semantic_signal_defers_instead_of_inventing_false(self) -> None:
        decision = decide_selection(
            SelectionSignals(
                topic_relevant=True,
                material_event=None,
                fresh=True,
                source_usable=True,
                identity_resolved=True,
            )
        )
        self.assertEqual(decision.verdict, SelectionVerdict.DEFER)
        self.assertEqual(decision.reasons, (SelectionReason.SEMANTIC_SIGNAL_MISSING,))

    def test_unresolved_identity_defers_even_for_material_relevant_event(self) -> None:
        decision = decide_selection(
            SelectionSignals(
                topic_relevant=True,
                material_event=True,
                fresh=True,
                source_usable=True,
                identity_resolved=False,
            )
        )
        self.assertEqual(decision.verdict, SelectionVerdict.DEFER)
        self.assertEqual(decision.reasons, (SelectionReason.IDENTITY_UNRESOLVED,))

    def test_verified_claims_are_not_a_phase6_selection_input(self) -> None:
        decision = decide_selection(
            SelectionSignals(
                topic_relevant=True,
                material_event=True,
                fresh=True,
                source_usable=True,
                identity_resolved=True,
            )
        )
        self.assertEqual(decision.verdict, SelectionVerdict.INCLUDE)
        self.assertFalse(hasattr(SelectionSignals, "verified_claim_count"))

    def test_fresh_relevant_material_event_is_phase6_eligible(self) -> None:
        decision = decide_selection(
            SelectionSignals(
                topic_relevant=True,
                material_event=True,
                fresh=True,
                source_usable=True,
                identity_resolved=True,
            )
        )
        self.assertEqual(decision.verdict, SelectionVerdict.INCLUDE)
        self.assertEqual(decision.reasons, (SelectionReason.ELIGIBLE,))


if __name__ == "__main__":
    unittest.main()
