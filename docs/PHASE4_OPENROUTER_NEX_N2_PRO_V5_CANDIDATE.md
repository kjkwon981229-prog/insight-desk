# Phase 4 — OpenRouter Nex-N2-Pro Event Understanding V5 Candidate

Status: ONE-SHOT QUALIFICATION TRIGGERED AFTER GREEN STAGING GATE

## Exact candidate route

- provider: OpenRouter
- qualification provider id: `openrouter_nexn2pro`
- exact model id: `nex-agi/nex-n2-pro:free`
- endpoint: `https://openrouter.ai/api/v1/chat/completions`
- credential: existing `OPENROUTER_API_KEY`
- production wiring: none
- active qualification protocol: V5
- required result: 4/4 only

Repository search found no pre-existing Nex-N2-Pro route before this candidate branch. This exact
model is distinct from every frozen OpenRouter Event Understanding route, including Nemotron 3 Super,
GLM 5.2, GPT-5.4 Mini, Qwen3 235B, and Dots3-Note Preview. No frozen exact route is retried or
reclassified.

## Current provider evidence

OpenRouter pages checked on 2026-08-29 identify `nex-agi/nex-n2-pro:free` as:

- a 397B-parameter sparse MoE with 17B active parameters;
- built by Nex AGI on a Qwen3.5 architecture with its own agentic post-training;
- reasoning-capable;
- supporting function calling and structured outputs;
- 262,144-token context;
- released 2026-06-08;
- explicitly free at $0 input/output on the free route.

OpenRouter also exposes active structured-output telemetry for the route and multiple hosting
providers. This makes it a materially different current candidate rather than a reroute of the frozen
Qwen direct models.

Public references checked on 2026-08-29:

- `https://openrouter.ai/nex-agi/nex-n2-pro:free`
- `https://openrouter.ai/nex-agi/nex-n2-pro:free/providers`
- `https://openrouter.ai/nex-agi/nex-n2-pro:free/performance`

## Transport and structured-output boundary

The qualification-only client fixes the exact free model slug and uses:

```text
POST https://openrouter.ai/api/v1/chat/completions
model = nex-agi/nex-n2-pro:free
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
requested structured-output parameters. The HTTP transport is constructed with `attempts=1`; the
one-shot execution cannot hide automatic HTTP retries. No random free router is used.

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

- `insight_desk/providers/openrouter_nexn2pro.py`
- `scripts/qualify_openrouter_nexn2pro_v5.py`
- `tests/test_openrouter_nexn2pro_v5_event_understanding_provider.py`
- this document

The candidate is not exported from `insight_desk.providers`, is not added to production selection,
and is not production-wired. The wrapper scope-registers it only inside the V5 qualification runner
and restores canonical runner state on exit.

## Preflight and staged one-shot gate

Qualification-only preflight head `83463473a1b9ee434aab0ae9e335a2f4ee4adcc4`, run `33232701196`:

- Infrastructure: SUCCESS
- historical production replay: SUCCESS
- Phase 6 correctness/recall: SUCCESS
- Python: 1263 tests / 23 skipped / 0 failed
- benchmark: 85 / 7 / 16 / 15 / 44
- Push Worker: 20/20
- npm audit: 0 vulnerabilities
- provider calls: 0

Temporary-lane staging head `3cea0a5098c9407e77b5b8db3e0e0e5e78a3cfa1`, run `33232948886`:

- Infrastructure: SUCCESS
- historical production replay: SUCCESS
- Phase 6 correctness/recall: SUCCESS
- `semantic-v5-provider-candidate-openrouter-nex-n2-pro`: SKIPPED
- provider calls: 0

The branch-specific lane is therefore armed only by the explicit commit-message marker. This
document-only commit is the single authorized one-shot trigger.

The first valid provider result is frozen. There is no provider rerun and no candidate-specific tuning
after a valid result. A failure proven to be our qualification harness rather than provider behavior
must be classified separately and must not be entered as provider evidence.

## Production and merge gates

A V5 4/4 result proves minimum compatibility only. It does not by itself remove the three migration
blockers, wire production, authorize fresh live, deploy, Push, or merge. PR #84 remains OPEN and
UNMERGED until all downstream migration/publication acceptance gates are separately proven.
