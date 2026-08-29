# Phase 4 — Gemini 3 Flash Preview Event Understanding V5 Candidate

Status: FROZEN — VALID V5 RESULT 2/4 NOT_QUALIFIED — NO RETRY

## Exact candidate route

- provider: Gemini
- qualification provider id: `gemini3_flash`
- exact model id: `gemini-3-flash-preview`
- endpoint: `https://generativelanguage.googleapis.com/v1beta/interactions`
- credential: existing `GEMINI_API_KEY`
- production wiring: none
- active qualification protocol: V5
- acceptance threshold: 4/4 only
- final result: 2/4 `NOT_QUALIFIED`
- retry status: prohibited for this exact route

This exact model did not appear in the repository before this candidate branch. It is distinct from
the production verification-failover owner `gemini-3.1-flash-lite` and from every previously frozen
Gemini Event Understanding route (`gemini-3.7-flash`, `gemini-3.6-flash`, `gemini-3.5-flash`,
`gemini-3.5-flash-lite`, `gemini-2.5-pro`, and `gemini-2.5-flash`). No frozen route is retried or
reclassified.

## Current official provider evidence

Google Gemini API documentation checked on 2026-08-29 identifies `gemini-3-flash-preview` as a
current Gemini 3 preview model with 1,048,576-token input context, 65,536-token output limit,
Thinking and Structured Outputs support, and Standard API input/output free on the Free Tier.
`gemini-3.1-pro-preview` was rejected because its Gemini API Free Tier is not available.

Official references checked on 2026-08-29:

- `https://ai.google.dev/gemini-api/docs/models/gemini-3-flash-preview`
- `https://ai.google.dev/gemini-api/docs/gemini-3`
- `https://ai.google.dev/gemini-api/docs/pricing`
- `https://ai.google.dev/gemini-api/docs/structured-output`

## Frozen V5 contract

The candidate received the canonical V5 contract exactly as frozen in:

- `tests/fixtures/event_understanding_qualification_v5.json`
- `insight_desk/event_understanding_adapter_v4.py`
- `scripts/qualify_event_understanding_provider_v5.py`

The same four historical exact-source cases, source metadata, semantic gold, scorer, distinct event
draft matching, exact-text evidence binding, deterministic invariants, and 4/4 acceptance applied.
No candidate-specific source, semantic prompt, gold, scorer, threshold, fixture, or V5 schema change
was introduced.

The qualification-only transport used `attempts=1`, so the valid run contains no hidden automatic
HTTP retry.

## Pre-call evidence

Initial candidate head `4c47b83006a1bad33954dfe3dd80076267919857` exposed exactly one
qualification-test ImportError: the new test guessed `GEMINI_MODEL`, while the preserved production
verification owner actually exports `GEMINI_FLASH_LITE`. No provider call occurred and this run is
not provider qualification evidence.

Only the candidate test import/assertion was corrected. Production Gemini code and the V5 contract
were unchanged.

Corrected ordinary preflight head `cc0b70bffaa7161432bba3766743cc5dad5476e6`, Actions run
`33231056204`:

- Infrastructure: SUCCESS;
- historical production replay: SUCCESS;
- Phase 6 correctness/recall: SUCCESS;
- Python: 1245 tests / 23 skipped / 0 failed;
- benchmark: 85 / 7 / 16 / 15 / 44;
- Push Worker: 20/20;
- npm audit: 0 vulnerabilities;
- provider calls: 0.

A temporary one-shot lane was then staged without its trigger. Staging head
`4ec7a563b1e8cafee5f6e24617c9bf5f2535d253`, Actions run `33231107036`:

- Infrastructure: SUCCESS;
- historical production replay: SUCCESS;
- Phase 6 correctness/recall: SUCCESS;
- `semantic-v5-provider-candidate-gemini-3-flash`: SKIPPED;
- provider calls: 0.

## Valid one-shot V5 qualification

The sole trigger head was:

`11af67fe1f30954db53c1f0c772e48887fef37e4`

Actions run: `33231176013`

Qualification job: `99044263949`

Exact result:

- status: `NOT_QUALIFIED`
- evaluated cases: 4
- passed cases: 2
- source mode: `historical_exact_source_excerpt_only`
- production correctness claimed: false

Case results:

- `run413-bok-kbs-rate-decision`: PASS
- `run413-bok-kmib-outlook-child`: FAIL
  - `event_drafts_min`
  - `expected_event_match`
  - `parent_hint_min`
- `run413-kpop-alphadriveone-actor-preserved`: FAIL
  - `adapter_contract:evidence_contract`
- `run413-kbo-osen-same-game-source`: PASS

Failure classification:

`MIXED_CHILD_EVENT_AND_EVIDENCE_CONTRACT_FAILURE`

This is a valid provider result, not a credential, transport, rate-limit, model-unavailable, or
qualification-harness failure. The exact route is therefore frozen and must not be retried or tuned.

## Frozen artifact evidence

- artifact ID: `9708548294`
- artifact ZIP SHA-256: `06ca070f3a35001d4e4ccb4e15bed39bebcc281e4b470b705641087880712e39`
- report SHA-256: `c498b45b22198f3e0ebddaa2e76a66799b366fab9c625ed750f6349185881fce`

The downloaded ZIP was independently rehashed and matched the GitHub Actions artifact digest. The
contained report was independently hashed and its JSON content rechecked against the 2/4 result and
case failures above.

The consumed one-shot CI lane was removed immediately after evidence capture. The ordinary workflow
blob was restored; the final candidate diff must not contain `.github/workflows/ci.yml`.

## Registry and selection state

The frozen result is recorded as `gemini_3_flash_v5` in
`config/event_understanding_provider_status_v2.json`.

Active V5 definitive evidence is now:

- `mistral_medium35_v5`: 3/4 `NOT_QUALIFIED`
- `mistral_small4_v5`: 1/4 `NOT_QUALIFIED`
- `cohere_command_a_reasoning_v5`: 2/4 `NOT_QUALIFIED`
- `gemini_3_flash_v5`: 2/4 `NOT_QUALIFIED`

Therefore machine state remains:

- `qualification_contract_status = AWAITING_PROVIDER_QUALIFICATION`
- `provider_inventory_status = NO_ELIGIBLE_EXISTING_PROVIDER`
- `selected_event_understanding_provider = null`
- `production_wired = false`

All three migration blockers remain active.

## Isolation and production boundary

Qualification-only candidate files remain isolated. The candidate is not exported from
`insight_desk.providers`, is not added to production selection, and is not production-wired.

This result does not authorize migration blocker removal, production wiring, a fresh canary, deploy,
Push, or merge. PR #84 must remain OPEN and UNMERGED until a valid active-protocol provider reaches
4/4 and all downstream migration/publication acceptance gates are separately proven.
