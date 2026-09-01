# PHASE 4 — Event Understanding Migration Gate

Status: `STRUCTURAL_GATE_OPEN_PROVIDER_UNSELECTED`

The active PR must not wire Event Understanding into production merely because a provider passes bounded qualification.

Production rewiring requires both:

1. a selected Event Understanding provider with `MINIMUM_COMPATIBILITY_PASS`; and
2. removal of every legacy semantic bypass recorded in `config/event_understanding_migration_gate_v2.json`.

Current active blockers: none.

The direct `CandidateEvent -> CanonicalEvent` compatibility lift, its registry entry point, and the compatibility `SemanticPipeline` takeover have been removed. Canonical identity does not reopen raw source or generated text as identity authority.

The active deterministic compatibility owner now promotes only a resolved PRIMARY result through `CanonicalEventDraft` with exact source ranges. This is independent of provider selection.

The migration gate is mechanical. It does not decide news meaning, does not qualify providers, and does not authorize a fresh canary.

Current provider state remains separately unqualified and unselected. Opening this structural gate does not qualify, select, or wire a provider.

A production marker, fresh live, deploy, Push, or merge still requires its own full regression, replay, exact-provenance, publication-identity, and human-audit acceptance gates.
