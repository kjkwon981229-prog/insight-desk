# Phase 4 — OpenRouter Qwen3-Next 80B Event Understanding V5 Candidate

Status: ONE-SHOT QUALIFICATION TRIGGERED AFTER GREEN STAGING GATE

## Exact candidate route

- provider: OpenRouter
- qualification provider id: `openrouter_qwen3next80b`
- exact model id: `qwen/qwen3-next-80b-a3b-instruct:free`
- endpoint: `https://openrouter.ai/api/v1/chat/completions`
- credential: existing `OPENROUTER_API_KEY`
- production wiring: none
- active qualification protocol: V5
- required result: 4/4 only

The exact model is distinct from frozen Qwen routes including OpenRouter Qwen3 235B A22B 2507 and
Hugging Face/DeepInfra Qwen3.6 35B A3B. It is the Qwen3-Next 80B A3B Instruct model, not a rerun of a
frozen exact provider/model pair.

## Current provider evidence before the call

OpenRouter pages checked on 2026-08-29 identify `qwen/qwen3-next-80b-a3b-instruct:free` as:

- free, with zero prompt/completion token pricing on the free route;
- 262,144-token context;
- an instruction-tuned Qwen3-Next 80B A3B model optimized for stable final answers, reasoning,
  multilingual use, RAG, tool use, and agentic workflows;
- served by a free Venice endpoint whose supported parameters include `Response Format`;
- recent endpoint uptime shown as 100%;
- structured-output error telemetry available for the endpoint.

This is materially stronger for the frozen V5 contract than free endpoints that do not accept
`response_format`. For example, the current Nemotron 3 Ultra free endpoint explicitly does not support
`response_format` and was therefore rejected before qualification.

Public references checked on 2026-08-29:

- `https://openrouter.ai/qwen/qwen3-next-80b-a3b-instruct:free/pricing`
- `https://openrouter.ai/qwen/qwen3-next-80b-a3b-instruct:free/api`
- `https://openrouter.ai/qwen/qwen3-next-80b-a3b-instruct:free/performance`

## Transport and structured-output boundary

The qualification-only client fixes the exact free model slug and uses:

```text
POST https://openrouter.ai/api/v1/chat/completions
model = qwen/qwen3-next-80b-a3b-instruct:free
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

`provider.require_parameters = true` prevents routing to a provider endpoint that cannot accept the
requested structured-output parameters. The HTTP transport is constructed with `attempts=1`; no
hidden HTTP retry is allowed. No random free router is used.

No candidate-specific source, semantic prompt, gold, scorer, threshold, fixture, token-budget tuning,
or V5 schema change is introduced.

## Frozen V5 contract

The candidate receives the canonical V5 contract exactly as frozen in:

- `tests/fixtures/event_understanding_qualification_v5.json`
- `insight_desk/event_understanding_adapter_v4.py`
- `scripts/qualify_event_understanding_provider_v5.py`

The same four historical exact-source cases, source metadata, semantic gold, scorer, distinct event
draft matching, exact-text evidence binding, deterministic invariants, and 4/4 acceptance apply.

## Isolation boundary

Qualification-only files:

- `insight_desk/providers/openrouter_qwen3next80b.py`
- `scripts/qualify_openrouter_qwen3next80b_v5.py`
- `tests/test_openrouter_qwen3next80b_v5_event_understanding_provider.py`
- this document

The candidate is not exported from `insight_desk.providers`, is not added to production selection,
and is not production-wired. The wrapper scope-registers it only inside the V5 qualification runner
and restores canonical runner state on exit.

## Preflight and staged one-shot gate

Qualification-only preflight head `0ef0d0c3204a12299438ba371bd0fb2bb370a436`, run `33233784216`:

- Infrastructure: SUCCESS
- historical production replay: SUCCESS
- Phase 6 correctness/recall: SUCCESS
- provider calls: 0

Temporary-lane staging head `ec35097e51ce761e1fae97d33c7d17940673f43d`, run `33233835884`:

- Infrastructure: SUCCESS
- historical production replay: SUCCESS
- Phase 6 correctness/recall: SUCCESS
- `semantic-v5-provider-candidate-openrouter-qwen3-next-80b`: SKIPPED
- provider calls: 0

The branch-specific lane is armed only by the explicit commit-message marker. This document-only
commit is the single authorized one-shot trigger.

The first valid provider result is frozen. There is no provider rerun and no candidate-specific tuning
after a valid result. A failure proven to be our qualification harness rather than provider behavior
must be classified separately and must not be entered as provider evidence.

## Production and merge gates

Even a V5 4/4 result proves minimum compatibility only. It does not by itself remove migration
blockers, wire production, authorize fresh live, deploy, Push, or merge. PR #84 remains OPEN and
UNMERGED until downstream migration/publication acceptance is separately proven.
