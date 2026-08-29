# Phase 4 — OpenRouter Liquid LFM2.5-2.6B Event Understanding V5 Candidate

Status: QUALIFICATION-ONLY ONE-SHOT TRIGGERED

## Exact candidate route

- provider: OpenRouter
- qualification provider id: `openrouter_lfm25_26b`
- exact model id: `liquid/lfm-2.5-2.6b:free`
- endpoint: `https://openrouter.ai/api/v1/chat/completions`
- credential: existing `OPENROUTER_API_KEY`
- production wiring: none
- active qualification protocol: V5
- required result: 4/4 only

Repository search before branch creation found no existing `lfm-2.5-2.6b` or `liquid` provider route. This is therefore a genuinely new exact candidate route rather than a retry or reroute of a frozen model.

## Current provider evidence before the call

OpenRouter pages checked on 2026-08-29 identify `liquid/lfm-2.5-2.6b:free` as:

- zero prompt/completion token pricing on the exact free route;
- 65,536-token context and up to 8,192 completion tokens;
- released 2026-08-11;
- a compact reasoning model aimed at agent workflows, data extraction, RAG, and long-context processing;
- strict structured-output support via JSON schema in `response_format`;
- currently 100% three-day uptime but materially weaker service availability: 26.54% over three days and 10.98% over the latest 24-hour window shown during candidate research.

The low availability is explicitly treated as a risk, not hidden. It does not justify retries. The exact route is allowed one bounded qualification attempt; an availability/transport failure is frozen separately from semantic performance.

OpenRouter's structured-output documentation states that support is endpoint-specific, that `structured_outputs` identifies strict JSON-schema support, and that `provider.require_parameters=true` restricts routing to endpoints capable of the requested parameters.

Public references checked on 2026-08-29:

- `https://openrouter.ai/liquid/lfm-2.5-2.6b:free`
- `https://openrouter.ai/models/?fmt=table&order=pricing-low-to-high&q=free&supported_parameters=response_format%2Cstructured_outputs`
- `https://openrouter.ai/docs/features/structured-outputs`

The current free + strict structured-output filter contained Dots3-Note Preview, LFM2.5-2.6B, GLM 5.2, and Nemotron 3 Super. Dots3-Note, GLM 5.2, and Nemotron 3 Super are already frozen exact routes in this project, leaving LFM2.5-2.6B as the only genuinely new route in that current strict-zero-cost OpenRouter set.

## Transport and structured-output boundary

The qualification-only client fixes the exact free model slug and uses:

```text
POST https://openrouter.ai/api/v1/chat/completions
model = liquid/lfm-2.5-2.6b:free
response_format = {
  type: json_schema,
  json_schema: {
    name: <schema name>,
    strict: true,
    schema: <frozen V5 schema>
  }
}
provider.require_parameters = true
temperature = 0
max_tokens = 4096
```

`provider.require_parameters=true` prevents routing to an endpoint that cannot accept the frozen structured-output requirement. The exact `:free` slug prevents a paid model route. The HTTP transport is constructed with `attempts=1`; no hidden HTTP retry is allowed. No random free router is used.

No candidate-specific source, semantic prompt, gold, scorer, threshold, fixture, token-budget tuning, or V5 schema change is introduced.

## Frozen V5 contract

The candidate receives the canonical V5 contract exactly as frozen in:

- `tests/fixtures/event_understanding_qualification_v5.json`
- `insight_desk/event_understanding_adapter_v4.py`
- `scripts/qualify_event_understanding_provider_v5.py`

The same four historical exact-source cases, source metadata, semantic gold, scorer, distinct event draft matching, exact-text evidence binding, deterministic invariants, and 4/4 acceptance apply.

## Isolation boundary

Qualification-only files:

- `insight_desk/providers/openrouter_lfm25_26b.py`
- `scripts/qualify_openrouter_lfm25_26b_v5.py`
- `tests/test_openrouter_lfm25_26b_v5_event_understanding_provider.py`
- this document

The candidate is not exported from `insight_desk.providers`, is not added to production selection, and is not production-wired. The wrapper scope-registers it only inside the V5 qualification runner and restores canonical runner state on exit.

## Preflight and staged one-shot gate

Qualification-only preflight head `480b09d0b750707fa23c3a55097e80b8439c5f56`, run `33234917897`:

- Infrastructure: SUCCESS
- historical production replay: SUCCESS
- Phase 6 correctness/recall: SUCCESS
- provider calls: 0

Temporary-lane staging head `499f52f7e86963b2ac39dc79051c0d4c32a64f08`, run `33234966630`:

- Infrastructure: SUCCESS
- historical production replay: SUCCESS
- Phase 6 correctness/recall: SUCCESS
- `semantic-v5-provider-candidate-openrouter-lfm25-26b`: SKIPPED
- provider calls: 0

The next commit is the only permitted trigger commit for this exact route. The first provider result is final evidence for this route: pass, semantic non-pass, or availability/transport block. No rerun is allowed.

## Production and merge gates

Even a V5 4/4 result proves minimum compatibility only. It does not by itself remove migration blockers, wire production, authorize fresh live, deploy, Push, or merge. PR #84 remains OPEN and UNMERGED until downstream migration/publication acceptance is separately proven.
