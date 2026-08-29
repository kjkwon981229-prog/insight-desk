# Phase 4 — OpenRouter Dots3-Note Preview Event Understanding V5 Candidate

Status: ONE-SHOT QUALIFICATION TRIGGERED — FIRST VALID RESULT MUST FREEZE

## Exact candidate route

- provider: OpenRouter
- qualification provider id: `openrouter_dots3note`
- exact model id: `dots-studio/dots-3-note-preview:free`
- endpoint: `https://openrouter.ai/api/v1/chat/completions`
- credential: existing `OPENROUTER_API_KEY`
- production wiring: none
- active qualification protocol: V5
- required result: 4/4 only

This exact model does not appear in the repository before this candidate branch. It is distinct from
the previously frozen OpenRouter Event Understanding routes, including Nemotron 3 Super, GLM 5.2,
GPT-5.4 Mini, and Qwen3 235B. No frozen exact route is retried or reclassified.

## Current provider evidence

OpenRouter model/catalog pages checked on 2026-08-29 identify Dots Studio Dots3-Note Preview as a
new free route released in August 2026 with a 512K context window, reasoning capability, and support
for JSON Schema structured outputs. The route is explicitly priced at $0 input/output. This keeps
the qualification within the KRW 0 execution constraint.

The candidate is preferred over currently listed free GLM 5.2 and Nemotron 3 Super routes because
those exact underlying OpenRouter models are already frozen historical Event Understanding evidence.
A much smaller free LFM route was not selected because the current failures require stronger semantic
event decomposition and evidence binding rather than a lower-capacity extraction route.

Public references checked on 2026-08-29:

- `https://openrouter.ai/dots-studio/dots-3-note-preview:free`
- OpenRouter models catalog filtered for free structured-output-capable routes

## Transport and structured-output boundary

The qualification-only client uses the existing OpenRouter Chat Completions contract:

```text
POST https://openrouter.ai/api/v1/chat/completions
model = dots-studio/dots-3-note-preview:free
response_format = {
  type: json_schema,
  json_schema: {
    name: <schema name>,
    strict: true,
    schema: <frozen V5 schema>
  }
}
provider.require_parameters = true
```

The exact free model slug is mandatory. `provider.require_parameters = true` prevents routing to an
endpoint that does not support the requested structured-output parameters. The HTTP transport is
constructed with `attempts=1`, so the one-shot execution cannot hide automatic HTTP retries.

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

- `insight_desk/providers/openrouter_dots3note.py`
- `scripts/qualify_openrouter_dots3note_v5.py`
- `tests/test_openrouter_dots3note_v5_event_understanding_provider.py`
- this document

The candidate is not exported from `insight_desk.providers`, is not added to production selection,
and is not production-wired. The wrapper scope-registers it only inside the V5 qualification runner
and restores canonical runner state on exit.

## Proven pre-call evidence

Corrected qualification-only preflight head `21d51fcf8086a98dea8b1440961c62dbb8c894a6`, Actions run
`33232043675`:

- Infrastructure: SUCCESS;
- historical production replay: SUCCESS;
- Phase 6 correctness/recall: SUCCESS;
- provider calls: 0.

The pre-call diff versus PR head `db7469a6963c816eb01ba92f517e68c720608c82` was exactly four added
qualification-only files, ahead 4 / behind 0.

A temporary one-shot lane was then staged without its trigger. Staging head
`e48f40a9813627cb9e266f0e25e5b7ffec0378a4`, Actions run `33232100583`:

- Infrastructure: SUCCESS;
- historical production replay: SUCCESS;
- Phase 6 correctness/recall: SUCCESS;
- `semantic-v5-provider-candidate-openrouter-dots3-note`: SKIPPED;
- provider calls: 0.

Therefore every pre-call gate is satisfied.

## One-shot execution gate

This commit is the single trigger commit and contains the exact marker:

`[semantic-v5-candidate:openrouter-dots3-note-preview]`

The branch-specific lane may execute exactly one four-case V5 qualification after its ordinary
dependencies pass again on this exact trigger head. The first valid provider result is final evidence
for this exact model route. There is no provider rerun and no candidate-specific tuning after a valid
result. A failure proven to be our qualification harness rather than provider behavior must be
classified separately and must not be entered as provider evidence.

## Production and merge gates

A V5 4/4 result proves minimum compatibility only. It does not by itself remove the three migration
blockers, wire production, authorize fresh live, deploy, Push, or merge. PR #84 remains OPEN and
UNMERGED until all downstream migration/publication acceptance gates are separately proven.
