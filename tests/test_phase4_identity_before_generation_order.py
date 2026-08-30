from __future__ import annotations

import inspect

import scripts.phase11_daily_production_core as production_core


def _run_production_source() -> str:
    return inspect.getsource(production_core.run_production)


def test_canonical_identity_precedes_selection_generation_and_verification_budget() -> None:
    source = _run_production_source()

    identity_start = source.index("identity_text = generation_request.evidence_text")
    identity_exit = source.index("if duplicate_event or identity_deferred:")
    selection_start = source.index("assessment = phase6.assess_with_auto_material(")
    verification_budget = source.index(
        'if stats["verification_attempts"] >= MAX_VERIFICATION_ATTEMPTS_PER_TOPIC:'
    )
    phase7_start = source.index("entry_candidate = produce_phase7_entry_candidate(")

    assert identity_start < identity_exit < selection_start < verification_budget < phase7_start


def test_duplicate_or_deferred_identity_exits_before_phase6_and_phase7() -> None:
    source = _run_production_source()

    identity_exit = source.index("if duplicate_event or identity_deferred:")
    selection_start = source.index("assessment = phase6.assess_with_auto_material(")
    phase7_start = source.index("entry_candidate = produce_phase7_entry_candidate(")

    assert identity_exit < selection_start < phase7_start


def test_identity_resolved_selection_signal_is_only_asserted_after_identity_exit() -> None:
    source = _run_production_source()

    identity_exit = source.index("if duplicate_event or identity_deferred:")
    resolved_signal = source.index("identity_resolved=True")

    assert identity_exit < resolved_signal


def test_generation_request_is_available_for_identity_evidence_without_generating() -> None:
    source = _run_production_source()

    request_start = source.index(
        "generation_request = GenerationRequest(event=event, facts=article_facts, evidence=article_evidence)"
    )
    identity_start = source.index("identity_text = generation_request.evidence_text")
    phase7_start = source.index("entry_candidate = produce_phase7_entry_candidate(")

    assert request_start < identity_start < phase7_start


def test_v2_runtime_defers_local_claim_verifier_initialization_until_phase7() -> None:
    source = _run_production_source()

    identity_start = source.index("identity_text = generation_request.evidence_text")
    v2_legacy_guard = source.index(
        'and "_INSIGHT_DESK_V2_IDENTITY_OWNER" not in globals()'
    )
    identity_exit = source.index("if duplicate_event or identity_deferred:")
    selection_start = source.index("assessment = phase6.assess_with_auto_material(")
    phase7_start = source.index("entry_candidate = produce_phase7_entry_candidate(")
    verifier_init = "local_verifier = LocalNliVerifier.transformers_default()"
    first_init = source.index(verifier_init)
    phase7_init = source.rindex(verifier_init)

    # The pre-identity construction exists only for legacy direct-core compatibility. The V2
    # runtime installs this marker, so active production bypasses that branch entirely.
    assert identity_start < v2_legacy_guard < first_init < identity_exit

    # The active V2 path constructs the verification implementation only after identity has exited
    # and Phase6 selection has admitted the event, immediately before the real Phase7 call.
    assert identity_exit < selection_start < phase7_init < phase7_start
    assert first_init != phase7_init
