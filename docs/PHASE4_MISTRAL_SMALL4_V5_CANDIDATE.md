# Phase 4 — Mistral Small 4 Event Understanding V5 Candidate

Status: CANDIDATE PREFLIGHT — PROVIDER NOT YET CALLED

## Exact candidate route

- provider: Mistral AI
- qualification provider id: `mistral_small4`
- exact model id: `mistral-small-2603`
- endpoint: `/v1/chat/completions`
- credential: existing `MISTRAL_API_KEY`
- production wiring: none
- active qualification protocol: V5
- required result: 4/4 only

This is a genuinely new exact model route. Frozen Mistral routes `mistral-large-2512` and
`mistral-medium-3-5` are not retried, reclassified, or reused as active V5 PASS evidence.

## Current provider evidence checked before implementation

Mistral's current official documentation checked on 2026-08-29 identifies Mistral Small 4 as:

- model id `mistral-small-2603`;
- GA, v26.03;
- a hybrid generalist combining instruct, reasoning, and coding behavior;
- 119B total parameters / 6.5B active parameters;
- 256k context;
- supporting Structured Outputs on `/v1/chat/completions` and `/v1/conversations`.

Official references checked on 2026-08-29:

- `https://docs.mistral.ai/models/mistral-small-4-26-03`
- `https://docs.mistral.ai/models`
- `https://docs.mistral.ai/studio/conversations/structured-output`

Mistral Small 4 has ordinary metered pricing. This project does not authorize paid fallback or a
pay-as-you-go activation. As with the previous Mistral candidate, the bounded qualification is
permitted only against already included zero-cost usage available to the existing Mistral
Workspace. If the first one-shot attempt is rejected for quota, billing, payment, or model
availability, that first result is frozen. No payment is enabled and no retry is performed.

Mistral Free-mode / Workspace quota references previously verified and still applicable to the same
existing `MISTRAL_API_KEY`:

- `https://docs.mistral.ai/getting-started/quickstarts/studio/activate-and-generate-api-key`
- `https://docs.mistral.ai/admin/billing-usage/usage-limits`
- `https://docs.mistral.ai/admin/identity-access/api-keys`

## Candidate selection rationale

This candidate is not chosen by tuning against the Mistral Medium 3.5 failed output. It is a
separate current GA model route with a different hybrid instruct/reasoning architecture while still
supporting the frozen structured-output contract.

Not selected:

- `mistral-medium-3-5`: frozen V5 3/4 NOT_QUALIFIED; no retry.
- `mistral-large-2512`: frozen historical Mistral route; no retry.
- Leanstral: specialized for formal-proof engineering rather than general news event semantics.
- Mistral-hosted Z.ai GLM 5.2: the same underlying GLM 5.2 model family already has frozen provider
  evidence through OpenRouter; it is not used as an ambiguous model reroute.

## Frozen V5 contract

No candidate-specific semantic contract change is allowed. This candidate receives the canonical
V5 contract exactly as frozen in:

- `tests/fixtures/event_understanding_qualification_v5.json`
- `insight_desk/event_understanding_adapter_v4.py`
- `scripts/qualify_event_understanding_provider_v5.py`

The candidate must use the same:

- four historical exact-source cases;
- source handoff and metadata;
- semantic gold;
- scorer and distinct event-draft matching;
- deterministic exact-text evidence binding;
- deterministic output invariants;
- acceptance threshold of 4/4.

No source, gold, scorer, acceptance threshold, prompt, or V5 schema is changed for this model.

## Isolation boundary

The candidate implementation is qualification-only:

- `insight_desk/providers/mistral_small4.py`
- `scripts/qualify_mistral_small4_v5.py`
- `tests/test_mistral_small4_v5_event_understanding_provider.py`
- this document

The new client is not exported from `insight_desk.providers`, not selected in the provider registry,
and not wired into production. The wrapper scope-registers `mistral_small4` only inside the V5
runner and restores canonical runner state afterward.

## One-shot execution gate

Before any real provider request:

1. ordinary Infrastructure must be SUCCESS on the exact candidate head;
2. historical production replay must be SUCCESS;
3. Phase 6 correctness/recall must be SUCCESS;
4. final diff must remain qualification-only;
5. a temporary branch-specific CI lane may then be added without its trigger;
6. the lane itself must be observed SKIPPED while ordinary jobs remain GREEN;
7. exactly one later trigger commit may execute the four-case qualification.

The first valid execution result is frozen. There is no provider retry loop and no candidate-specific
tuning after the result.

## Production and merge gates

A V5 4/4 result proves minimum compatibility only. It does not by itself remove the three migration
blockers, wire production, authorize a fresh canary, deploy, Push, or merge. PR #84 remains open and
unmerged until the downstream migration and publication acceptance sequence is separately proven.
