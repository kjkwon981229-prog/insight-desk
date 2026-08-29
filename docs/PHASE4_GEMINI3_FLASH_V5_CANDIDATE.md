# Phase 4 — Gemini 3 Flash Preview Event Understanding V5 Candidate

Status: CANDIDATE PREFLIGHT — PROVIDER NOT YET CALLED

## Exact candidate route

- provider: Gemini
- qualification provider id: `gemini3_flash`
- exact model id: `gemini-3-flash-preview`
- endpoint: `https://generativelanguage.googleapis.com/v1beta/interactions`
- credential: existing `GEMINI_API_KEY`
- production wiring: none
- active qualification protocol: V5
- required result: 4/4 only

This exact model does not appear anywhere in the repository before this candidate branch. It is
distinct from the production verification-failover owner `gemini-3.1-flash-lite` and from every
previously frozen Gemini Event Understanding route (`gemini-3.7-flash`, `gemini-3.6-flash`,
`gemini-3.5-flash`, `gemini-3.5-flash-lite`, `gemini-2.5-pro`, and `gemini-2.5-flash`). No frozen
route is retried or reclassified.

## Current official provider evidence

Google Gemini API documentation checked on 2026-08-29 identifies `gemini-3-flash-preview` as:

- a current Gemini 3 preview model;
- 1,048,576-token input context and 65,536-token output limit;
- Thinking supported;
- Structured Outputs supported;
- text output supported;
- available through the Gemini API;
- Standard API input and output **free of charge on the Free Tier**.

The Gemini 3 developer guide describes Gemini 3 Flash as a reasoning-capable model with Pro-level
intelligence at Flash speed/pricing and explicitly confirms a Gemini API free tier for
`gemini-3-flash-preview`.

Official references checked on 2026-08-29:

- `https://ai.google.dev/gemini-api/docs/models/gemini-3-flash-preview`
- `https://ai.google.dev/gemini-api/docs/gemini-3`
- `https://ai.google.dev/gemini-api/docs/pricing`
- `https://ai.google.dev/gemini-api/docs/structured-output`

`gemini-3.1-pro-preview` was considered but rejected because its Gemini API Free Tier is explicitly
not available. The new candidate therefore preserves the KRW 0 execution constraint.

## Transport and structured-output boundary

The qualification-only client uses the same official Gemini Interactions API shape already proven by
the historical Gemini 3.5 Flash qualification route:

```text
POST https://generativelanguage.googleapis.com/v1beta/interactions
model = gemini-3-flash-preview
response_format = {
  type: text,
  mime_type: application/json,
  schema: <frozen V5 structured schema>
}
```

The HTTP transport is explicitly constructed with `attempts=1`, so a single qualification execution
cannot hide automatic provider retries. This is a transport-boundary safeguard only; it does not
change the V5 semantic contract.

No candidate-specific source, semantic prompt, gold, scorer, threshold, fixture, or V5 schema change
is introduced.

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
and is not production-wired. The wrapper scope-registers it only inside the V5 qualification runner
and restores canonical runner state on exit.

## One-shot execution gate

Before any real provider request:

1. ordinary Infrastructure must be SUCCESS on the exact candidate head;
2. historical production replay must be SUCCESS;
3. Phase 6 correctness/recall must be SUCCESS;
4. final diff must remain qualification-only;
5. a temporary branch-specific CI lane may be added without its trigger;
6. that lane must be observed SKIPPED while ordinary jobs remain GREEN;
7. exactly one later trigger commit may execute the four-case qualification.

The first valid result is frozen. There is no provider rerun and no candidate-specific tuning after a
valid result. A failure proven to be our qualification harness rather than provider behavior must be
classified separately and must not be entered as provider qualification evidence.

## Production and merge gates

A V5 4/4 result proves minimum compatibility only. It does not by itself remove the three migration
blockers, wire production, authorize fresh live, deploy, Push, or merge. PR #84 remains OPEN and
UNMERGED until all downstream migration/publication acceptance gates are separately proven.
