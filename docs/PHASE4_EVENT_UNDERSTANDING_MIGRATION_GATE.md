# PHASE 4 — Event Understanding Migration Gate

Status: `CLOSED`

The active PR must not wire Event Understanding into production merely because a provider passes bounded qualification.

Production rewiring requires both:

1. a selected Event Understanding provider with `MINIMUM_COMPATIBILITY_PASS`; and
2. removal of every legacy semantic bypass recorded in `config/event_understanding_migration_gate_v2.json`.

Current active blockers:

- `CandidateEvent -> CanonicalEvent` direct compatibility lift via `canonical_event_from_candidate()`;
- canonical identity reading `SourceDocument.body` and reinterpreting raw source;
- legacy `CandidateEvent` identity comparison remaining authoritative inside the compatibility path.

These blockers are intentionally left in place while no qualified Event Understanding provider exists, because deleting them now would only break the compatibility runtime without replacing its semantic owner.

The migration gate is mechanical. It does not decide news meaning, does not qualify providers, and does not authorize a fresh canary.

Current provider state is separately blocked by the missing GitHub Actions `MISTRAL_API_KEY` for the prepared Mistral Large 3 candidate. Mistral has evaluated zero semantic cases and is not `NOT_QUALIFIED`.

No production marker, fresh live, deploy, Push, or merge is authorized while this gate is closed.
