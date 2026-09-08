import json
import unittest
from pathlib import Path

from insight_desk.core import RecoveryAction, VerificationPolicy
from insight_desk.providers import (
    CLOUDFLARE_MODEL,
    CLOUDFLARE_VERIFIER_ID,
    GROQ_20B,
    GROQ_120B,
    LOCAL_NLI_MODEL,
    LOCAL_NLI_VERIFIER_ID,
)


ROOT = Path(__file__).resolve().parents[1]
FREEZE = json.loads((ROOT / "config" / "architecture_freeze_v1.json").read_text(encoding="utf-8"))


class ArchitectureFreezeTests(unittest.TestCase):
    def test_zero_cost_hard_rules_are_fail_closed(self):
        rules = FREEZE["hard_rules"]
        self.assertTrue(rules["zero_cost_only"])
        self.assertFalse(rules["paid_fallback_allowed"])
        self.assertFalse(rules["global_abort_from_item_failure_allowed"])
        self.assertFalse(rules["generation_failure_may_delete_existing_event"])
        self.assertFalse(rules["llm_may_override_explicit_identity_contradiction"])
        self.assertFalse(rules["single_llm_selection_final_gate_allowed"])
        self.assertFalse(rules["numeric_confidence_without_validated_contract_allowed"])

    def test_provider_roles_match_frozen_implementation_constants(self):
        roles = FREEZE["provider_roles"]
        self.assertEqual(roles["generation_primary"]["model"], GROQ_20B)
        self.assertEqual(roles["temporal_auxiliary"]["model"], GROQ_120B)
        self.assertEqual(roles["claim_verification_primary"]["model"], CLOUDFLARE_MODEL)
        self.assertEqual(
            roles["claim_verification_primary"]["verifier_id"], CLOUDFLARE_VERIFIER_ID
        )
        self.assertEqual(roles["claim_verification_secondary"]["model"], LOCAL_NLI_MODEL)
        self.assertEqual(
            roles["claim_verification_secondary"]["verifier_id"], LOCAL_NLI_VERIFIER_ID
        )

    def test_claim_verification_policy_uses_independent_ids(self):
        roles = FREEZE["provider_roles"]
        policy = VerificationPolicy(
            primary_verifier_id=roles["claim_verification_primary"]["verifier_id"],
            secondary_verifier_id=roles["claim_verification_secondary"]["verifier_id"],
        )
        self.assertNotEqual(policy.primary_verifier_id, policy.secondary_verifier_id)

    def test_identity_and_selection_boundaries_remain_conservative(self):
        boundaries = FREEZE["semantic_boundaries"]
        self.assertTrue(boundaries["event_identity"]["deterministic_contradictions_first"])
        self.assertTrue(boundaries["event_identity"]["explicit_date_conflict_forces_separate"])
        self.assertEqual(boundaries["event_identity"]["ambiguous_default"], "keep_separate")
        self.assertFalse(boundaries["event_identity"]["embedding_similarity_final_authority"])
        self.assertTrue(boundaries["selection"]["material_event_separate_from_selection"])
        self.assertFalse(boundaries["selection"]["llm_final_authority"])

    def test_non_core_models_cannot_silently_become_semantic_authorities(self):
        self.assertFalse(FREEZE["provider_roles"]["rare_optional_adjudication"]["core_dependency"])
        self.assertFalse(
            FREEZE["provider_roles"]["same_event_candidate_retrieval"]["identity_authority"]
        )
        # The historical architecture freeze remains immutable. Phase 12B may add an optional
        # availability/failover adapter, but that must not silently promote Gemini into semantic
        # identity/selection authority or a required paid/core dependency.
        gemini_path = ROOT / "insight_desk" / "providers" / "gemini.py"
        self.assertTrue(gemini_path.exists())
        gemini_source = gemini_path.read_text(encoding="utf-8")
        self.assertIn('GEMINI_API_KEY', gemini_source)
        self.assertIn('def configured(', gemini_source)
        self.assertNotIn('paid', gemini_source.casefold())
        rejected = FREEZE["explicit_non_roles"]
        self.assertFalse(rejected["cloudflare_llama_generic_selection_gate"])
        self.assertFalse(rejected["cloudflare_llama_event_identity_gate"])
        self.assertFalse(rejected["groq_sole_fact_verifier"])
        self.assertFalse(rejected["gemini_core_runtime"])
        self.assertFalse(rejected["minilm_event_identity_gate"])

    def test_failure_policy_has_no_paid_recovery_action(self):
        action_values = {action.value for action in RecoveryAction}
        self.assertFalse(any("paid" in value or "billing" in value for value in action_values))

    def test_ui_and_phase5_boundaries_are_explicit(self):
        self.assertFalse(FREEZE["ui_freeze"]["production_css_integrated"])
        self.assertTrue(FREEZE["ui_freeze"]["event_ledger_requires_future_history_contract"])
        extraction = FREEZE["acquisition_selection"]["article_extraction"]
        self.assertEqual(extraction["primary"], "Trafilatura")
        self.assertEqual(extraction["fallback"], "Playwright")
        self.assertEqual(extraction["status"], "selected_not_yet_implemented")
        self.assertEqual(FREEZE["next_phase"], "Phase 5 Acquisition Pipeline")


if __name__ == "__main__":
    unittest.main()
