# Event Understanding V5 — Corrected Qualification Contract

## Status

Protocol V5 is the active provider-qualification contract. Protocol V4 and all earlier provider results remain frozen historical evidence and are not reclassified by this migration.

Current machine state after the V5 contract migration:

- core contract: `event_understanding_v2`
- structured output schema: `event_understanding_schema_v4`
- active qualification protocol: `5`
- qualification state: `AWAITING_PROVIDER_QUALIFICATION`
- provider inventory: `NO_ELIGIBLE_EXISTING_PROVIDER`
- selected Event Understanding provider: `null`
- production wired: `false`
- full production correctness claimed: `false`

No provider API call is part of the V5 contract migration itself.

## Why V5 Exists

The V4 qualification path correctly moved exact source-range calculation to a deterministic binder, but its model-facing prompt/schema did not explicitly state every deterministic invariant later enforced by `CanonicalEventDraft` and `ArticleUnderstanding`.

That meant a provider could satisfy the visible structured-output shape and still fail later with a generic `event_draft_contract` or `article_understanding_contract` error because of a requirement that had not been presented to the semantic owner before generation.

The observability audit made those deterministic failures distinguishable for future evidence. V5 removes the hidden-contract mismatch by stating the bounded deterministic invariants in the provider-facing contract before the output is judged.

## What V5 Does Not Change

V5 does not change qualification difficulty or semantic acceptance. It preserves V4's:

- four historical exact-source cases
- source fixture and source metadata handoff
- semantic gold expectations
- scoring policy and scorer implementation
- distinct event-draft matching
- exact-text evidence binding
- 4-of-4 minimum compatibility requirement
- no-fresh-news rule
- no-production-wiring rule

V5 does not tune a provider after failure, modify a gold label, relax the scorer, or reinterpret any V4 provider result.

## Explicit Deterministic Contract

V5 explicitly presents the bounded invariants already enforced by the core contract, including:

- duplicate evidence references are forbidden within an event
- duplicate participants are forbidden
- duplicate event/article uncertainty reasons are forbidden
- non-empty event time must be ISO-8601
- datetime event time must contain an explicit timezone
- `metric` and `value` must be present together
- resolved event/article output must not contain uncertainty reasons
- unresolved event/article output must contain uncertainty reasons
- resolved article output must contain at least one event
- resolved article output must contain at least one primary event

These are contract-alignment instructions, not new semantic detectors.

## Historical Evidence Invariant

All Protocol V4 records retain their original provider/model IDs, run IDs, head SHAs, case results, failure classifications, artifact IDs, artifact digests, and report digests. A V4 result cannot be selected under active Protocol V5 even if a historical or synthetic V4 result is `MINIMUM_COMPATIBILITY_PASS`.

## Migration Gate

The production migration gate remains closed. The three runtime blockers remain active:

1. `candidate_event_direct_canonical_lift`
2. `identity_reads_source_body`
3. `legacy_candidate_identity_authority`

A future provider must first obtain `MINIMUM_COMPATIBILITY_PASS` under active Protocol V5. Provider qualification alone does not remove these blockers or authorize production rewiring.

## Next Permitted Step

After this provider-neutral V5 contract is ordinary-CI GREEN, the next semantic action is one qualification run for a genuinely new, eligible zero-cost provider/model using the frozen V5 contract. The first result must be frozen without provider-specific prompt/schema/source/gold/scorer tuning or retry loops.
