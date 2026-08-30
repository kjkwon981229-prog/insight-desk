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
