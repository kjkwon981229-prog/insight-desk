# Phase 4 — OpenRouter Liquid LFM2.5-2.6B Event Understanding V5 Candidate

Status: FROZEN — NOT_QUALIFIED (1/4)

## Exact candidate route

- provider: OpenRouter
- qualification provider id: `openrouter_lfm25_26b`
- exact model id: `liquid/lfm-2.5-2.6b:free`
- endpoint: `https://openrouter.ai/api/v1/chat/completions`
- credential: existing `OPENROUTER_API_KEY`
- production wiring: none
- active qualification protocol: V5
- acceptance requirement: 4/4 only
- frozen result: 1/4, `NOT_QUALIFIED`
- rerun: forbidden for this exact route

Repository search before branch creation found no existing `lfm-2.5-2.6b` or `liquid` provider route. This was therefore a genuinely new exact candidate route rather than a retry or reroute of a frozen model.

## Provider evidence before the call

OpenRouter pages checked on 2026-08-29 identified `liquid/lfm-2.5-2.6b:free` as:

- zero prompt/completion token pricing on the exact free route;
- 65,536-token context and up to 8,192 completion tokens;
- released 2026-08-11;
- a compact reasoning model aimed at agent workflows, data extraction, RAG, and long-context processing;
- strict structured-output support via JSON schema in `response_format`;
- 100% three-day uptime at the time of research but materially weaker service availability: 26.54% over three days and 10.98% over the latest 24-hour window shown then.

The low availability was treated as a risk, not hidden and not used to justify retries. The exact route was allowed one bounded qualification attempt. Availability/transport failures and semantic failures remained distinct evidence classes.

OpenRouter's structured-output documentation states that support is endpoint-specific, that `structured_outputs` identifies strict JSON-schema support, and that `provider.require_parameters=true` restricts routing to endpoints capable of the requested parameters.

Public references checked on 2026-08-29:

- `https://openrouter.ai/liquid/lfm-2.5-2.6b:free`
- `https://openrouter.ai/models/?fmt=table&order=pricing-low-to-high&q=free&supported_parameters=response_format%2Cstructured_outputs`
- `https://openrouter.ai/docs/features/structured-outputs`

The current free + strict structured-output filter contained Dots3-Note Preview, LFM2.5-2.6B, GLM 5.2, and Nemotron 3 Super. Dots3-Note, GLM 5.2, and Nemotron 3 Super were already frozen exact routes in this project, leaving LFM2.5-2.6B as the only genuinely new route in that strict-zero-cost OpenRouter set at candidate selection time.

## Transport and structured-output boundary

The qualification-only client fixed the exact free model slug and used:

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

`provider.require_parameters=true` prevented routing to an endpoint that could not accept the frozen structured-output requirement. The exact `:free` slug prevented a paid model route. The HTTP transport was constructed with `attempts=1`; no hidden HTTP retry was allowed. No random free router was used.

No candidate-specific source, semantic prompt, gold, scorer, threshold, fixture, token-budget tuning, or V5 schema change was introduced.

## Frozen V5 contract

The candidate received the canonical V5 contract exactly as frozen in:

- `tests/fixtures/event_understanding_qualification_v5.json`
- `insight_desk/event_understanding_adapter_v4.py`
- `scripts/qualify_event_understanding_provider_v5.py`

The same four historical exact-source cases, source metadata, semantic gold, scorer, distinct event draft matching, exact-text evidence binding, deterministic invariants, and 4/4 acceptance applied.

## Isolation boundary

Qualification-only implementation files:

- `insight_desk/providers/openrouter_lfm25_26b.py`
- `scripts/qualify_openrouter_lfm25_26b_v5.py`
- `tests/test_openrouter_lfm25_26b_v5_event_understanding_provider.py`
- this document

The candidate was not exported from `insight_desk.providers`, was not added to production selection, and was not production-wired. The wrapper scope-registered it only inside the V5 qualification runner and restored canonical runner state on exit.

## Preflight and one-shot gate

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

Single permitted trigger:

- trigger SHA: `6c30921b4ec9a33729f3049ace216376c3651c5f`
- run: `33235012040`
- Infrastructure: SUCCESS
- historical production replay: SUCCESS
- Phase 6 correctness/recall: SUCCESS
- provider qualification: executed exactly once

The consumed temporary one-shot lane was removed at `dfcad1872843b36f9ff1eb115a46bcefb5679418`. It is absent from the frozen branch workflow.

## Frozen provider result

The first provider result is final evidence for this exact route:

- status: `NOT_QUALIFIED`
- evaluated: 4
- passed: 1
- failure classification: `MIXED_SEMANTIC_AND_INVALID_OUTPUT`

Cases:

1. `run413-bok-kbs-rate-decision` — PASS
2. `run413-bok-kmib-outlook-child` — FAIL
   - `event_drafts_min`
   - `expected_event_match`
   - `parent_hint_min`
3. `run413-kpop-alphadriveone-actor-preserved` — FAIL
   - `expected_event_match`
4. `run413-kbo-osen-same-game-source` — FAIL
   - `provider_transport:invalid_output`

Evidence binding:

- artifact id: `9709657693`
- artifact ZIP SHA-256: `b518f05f8a79ac0138a84291241b79736867a45bb631d351c3a966400a1f48dc`
- report SHA-256: `64817b024f235a0e50e6a69f6730bbe3a4199b64b8fa5d7913514072c167ac3a`

The artifact ZIP digest was independently recomputed and matched GitHub's artifact digest. The report digest was independently recomputed from the extracted qualification report.

This is a definitive non-pass, not a provider-unavailable classification. No rerun, prompt retuning, schema retuning, token-budget retuning, scorer change, gold change, or candidate-specific exception is permitted for this exact route.

## Evidence-only freeze closure

Freeze regression commit `ef70369700bb069c0e856d407b9e733c35780bc6` intentionally produced RED run `33238277698`: the new freeze test alone failed because the LFM result had not yet been recorded in the central provider-status registry. Historical replay and Phase 6 remained green.

Status-record commit `034627c0f6f18d6476421ebd18da8870f45ea714` then exposed one existing inventory expectation that enumerated all active V5 evidence records but did not yet include this new provider id. Run `33238394171` therefore failed only that bookkeeping assertion.

Inventory-evidence commit `6706bab2f11148855d8291a8e519fba1e1d4162a` added the LFM non-pass record to that expected active V5 set. Run `33238446177` closed GREEN:

- Infrastructure: SUCCESS
- Python: 1283 tests / 23 skipped / 0 failed
- benchmark: 85 / 7 / 16 / 15 / 44
- Push Worker: 20/20 PASS
- npm audit: 0 vulnerabilities
- historical production replay: 3/3 PASS
- Phase 6 correctness/recall: 3/3 PASS

The closure changed qualification/evidence bookkeeping only. It did not change semantic gold, scorer, V5 provider contract, migration gate, production orchestration, publication, renderer, PWA, or Push behavior.

## Production and merge gates

The frozen state remains:

- provider inventory: `CANDIDATE_QUALIFICATION_BLOCKED`
- selected event-understanding provider: `null`
- production wiring: `false`
- full production correctness claimed: `false`
- qualification contract: `AWAITING_PROVIDER_QUALIFICATION`

A V5 provider result never authorizes production by itself. This 1/4 result does not remove migration blockers, wire production, authorize a fresh live run, deploy, Push, or merge. PR #84 must remain OPEN and UNMERGED while the architecture/runtime-map closure continues.
