# Phase 4 — Gemini 3 Flash Preview Event Understanding V5 Candidate

Status: ONE-SHOT QUALIFICATION TRIGGERED — FIRST VALID RESULT MUST FREEZE

## Exact candidate route

- provider: Gemini
- qualification provider id: `gemini3_flash`
- exact model id: `gemini-3-flash-preview`
- endpoint: `https://generativelanguage.googleapis.com/v1beta/interactions`
- credential: existing `GEMINI_API_KEY`
- production wiring: none
- active qualification protocol: V5
- required result: 4/4 only

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

## Transport and structured-output boundary

The qualification-only client uses the Gemini Interactions API shape already proven by the frozen
Gemini 3.5 Flash route:

```text
POST https://generativelanguage.googleapis.com/v1beta/interactions
model = gemini-3-flash-preview
response_format = {
  type: text,
  mime_type: application/json,
  schema: <frozen V5 structured schema>
}
```

The HTTP transport is explicitly `attempts=1`, so the one-shot execution cannot hide automatic HTTP
retries. No candidate-specific source, semantic prompt, gold, scorer, threshold, fixture, or V5
schema change is introduced.

## Frozen V5 contract

The candidate receives the canonical V5 contract exactly as frozen in:

- `tests/fixtures/event_understanding_qualification_v5.json`
- `insight_desk/event_understanding_adapter_v4.py`
- `scripts/qualify_event_understanding_provider_v5.py`

The same four historical exact-source cases, source metadata, semantic gold, scorer, distinct event
draft matching, exact-text evidence binding, deterministic invariants, and 4/4 acceptance apply.

## Isolation boundary

Qualification-only files:

- `insight_desk/providers/gemini3flash.py`
- `scripts/qualify_gemini3_flash_v5.py`
- `tests/test_gemini3_flash_v5_event_understanding_provider.py`
- this document

The candidate is not exported from `insight_desk.providers`, is not added to production selection,
and is not production-wired. The wrapper scope-registers it only inside the V5 runner and restores
canonical runner state on exit.

## Proven pre-call evidence

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

Therefore every pre-call gate is satisfied.

## One-shot execution gate

This commit is the single trigger commit and contains the exact marker:

`[semantic-v5-candidate:gemini-3-flash-preview]`

The branch-specific lane may execute exactly one four-case V5 qualification after its ordinary
dependencies pass again on this exact trigger head. The first valid provider result is final evidence
for this exact model route. There is no provider rerun and no candidate-specific tuning after a valid
result. A failure proven to be our qualification harness rather than provider behavior must be
classified separately and must not be entered as provider evidence.

## Production and merge gates

A V5 4/4 result proves minimum compatibility only. It does not by itself remove the three migration
blockers, wire production, authorize fresh live, deploy, Push, or merge. PR #84 remains OPEN and
UNMERGED until all downstream migration/publication acceptance gates are separately proven.
