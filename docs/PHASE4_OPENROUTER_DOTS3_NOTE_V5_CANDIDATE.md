# Phase 4 — OpenRouter Dots3-Note Preview Event Understanding V5 Candidate

Status: FROZEN — VALID V5 RESULT 2/4 NOT_QUALIFIED — NO RETRY

## Exact candidate route

- provider: OpenRouter
- qualification provider id: `openrouter_dots3note`
- exact model id: `dots-studio/dots-3-note-preview:free`
- endpoint: `https://openrouter.ai/api/v1/chat/completions`
- credential: existing `OPENROUTER_API_KEY`
- production wiring: none
- active qualification protocol: V5
- acceptance threshold: 4/4 only
- final result: 2/4 `NOT_QUALIFIED`
- retry status: prohibited for this exact route

This exact model did not appear in the repository before this candidate branch. It is distinct from
the previously frozen OpenRouter Event Understanding routes, including Nemotron 3 Super, GLM 5.2,
GPT-5.4 Mini, and Qwen3 235B. No frozen exact route was retried or reclassified.

## Provider evidence used for candidate selection

OpenRouter model/catalog pages checked on 2026-08-29 identified Dots Studio Dots3-Note Preview as a
free route released in August 2026 with a 512K context window, reasoning capability, and JSON Schema
structured-output support. The route was explicitly priced at $0 input/output, preserving the KRW 0
qualification constraint.

Public references checked on 2026-08-29:

- `https://openrouter.ai/dots-studio/dots-3-note-preview:free`
- OpenRouter models catalog filtered for free structured-output-capable routes

## Frozen V5 and transport boundary

The candidate received the canonical V5 contract exactly as frozen in:

- `tests/fixtures/event_understanding_qualification_v5.json`
- `insight_desk/event_understanding_adapter_v4.py`
- `scripts/qualify_event_understanding_provider_v5.py`

The same four historical exact-source cases, source metadata, semantic gold, scorer, distinct event
draft matching, exact-text evidence binding, deterministic invariants, and 4/4 acceptance applied.
No candidate-specific source, semantic prompt, gold, scorer, threshold, fixture, or V5 schema change
was introduced.

The qualification-only client fixed the exact model slug, used strict JSON Schema with
`provider.require_parameters = true`, and constructed the HTTP transport with `attempts=1`. There
was no random model fallback and no hidden automatic HTTP retry.

## Proven pre-call evidence

Qualification-only preflight head:

`21d51fcf8086a98dea8b1440961c62dbb8c894a6`

Actions run `33232043675`:

- Infrastructure: SUCCESS
- historical production replay: SUCCESS
- Phase 6 correctness/recall: SUCCESS
- provider calls: 0

The pre-call diff versus PR head `db7469a6963c816eb01ba92f517e68c720608c82` was exactly four added
qualification-only files, ahead 4 / behind 0.

Temporary one-shot lane staging head:

`e48f40a9813627cb9e266f0e25e5b7ffec0378a4`

Actions run `33232100583`:

- Infrastructure: SUCCESS
- historical production replay: SUCCESS
- Phase 6 correctness/recall: SUCCESS
- `semantic-v5-provider-candidate-openrouter-dots3-note`: SKIPPED
- provider calls: 0

## Valid one-shot V5 qualification

The sole trigger head was:

`2e62c43167754f6598cb12b990bf2a0a17a34a35`

Actions run: `33232152925`

Qualification job: `99046806251`

Exact result:

- status: `NOT_QUALIFIED`
- evaluated cases: 4
- passed cases: 2
- source mode: `historical_exact_source_excerpt_only`
- production correctness claimed: false

Case results:

- `run413-bok-kbs-rate-decision`: PASS
- `run413-bok-kmib-outlook-child`: FAIL
  - `provider_transport:invalid_output`
- `run413-kpop-alphadriveone-actor-preserved`: PASS
- `run413-kbo-osen-same-game-source`: FAIL
  - `expected_event_match`

Failure classification:

`MIXED_INVALID_OUTPUT_AND_EVENT_MATCH_FAILURE`

This is a valid first provider result for the exact route. The same route successfully returned
usable structured output on two cases, while one case produced invalid output and one produced a
semantic event-match failure. It is not a whole-run credential, model-unavailable, or qualification
harness failure. Under the one-shot rule, the exact route is frozen and must not be retried, given a
larger token budget, or receive candidate-specific schema/prompt/scorer tuning.

## Frozen artifact evidence

- artifact ID: `9708845325`
- artifact ZIP SHA-256: `16536bedff717a665403581c4346a8ddfbae1caac87e0e69cb7d2bfc4f815729`
- report SHA-256: `ce6e0af6e8137c3762eb1d15826c3fd98d7a9512d0b2cf98b4a0a7d20b47bbbd`

The downloaded ZIP was independently rehashed and matched the GitHub Actions artifact digest. The
contained report was independently hashed and its JSON content rechecked against the 2/4 result and
case failures above.

The consumed one-shot CI lane was removed immediately after evidence capture and the ordinary
workflow blob was restored. The final candidate diff must not contain `.github/workflows/ci.yml`.

## Registry and selection state

The result is recorded as `openrouter_dots3note_v5` in
`config/event_understanding_provider_status_v2.json`.

Active V5 definitive evidence is now:

- `mistral_medium35_v5`: 3/4 `NOT_QUALIFIED`
- `mistral_small4_v5`: 1/4 `NOT_QUALIFIED`
- `cohere_command_a_reasoning_v5`: 2/4 `NOT_QUALIFIED`
- `gemini_3_flash_v5`: 2/4 `NOT_QUALIFIED`
- `openrouter_dots3note_v5`: 2/4 `NOT_QUALIFIED`

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
