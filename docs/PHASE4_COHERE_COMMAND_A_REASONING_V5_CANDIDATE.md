# Phase 4 — Cohere Command A Reasoning Event Understanding V5 Candidate

Status: CANDIDATE PREFLIGHT — PROVIDER NOT YET CALLED

## Exact candidate route

- provider: Cohere
- qualification provider id: `cohere_command_a_reasoning`
- exact model id: `command-a-reasoning-08-2025`
- endpoint: `/v2/chat`
- credential: existing `COHERE_API_KEY`
- production wiring: none
- active qualification protocol: V5
- required result: 4/4 only

This is a genuinely new exact provider/model route. Historical Cohere evidence is frozen on
`command-a-plus-05-2026`; that route is not retried, reclassified, or used as active V5 PASS
evidence.

## Current official provider evidence

Cohere documentation checked on 2026-08-29 identifies Command A Reasoning as:

- model id `command-a-reasoning-08-2025`;
- Live;
- 111B parameters;
- 256k context;
- up to 32k output;
- multilingual reasoning in 23 languages;
- Structured Outputs capable;
- available through Chat V2, Chat Completions, and Chat V1.

Cohere explicitly states that **for both trial keys and production keys, Command A Reasoning is free
until rate limits are reached**. Current rate-limit documentation lists Command A Reasoning at 20
requests/minute and trial/new-model usage at up to 1,000 API calls/month, which is sufficient for
this bounded four-case qualification without a paid fallback.

Official references checked on 2026-08-29:

- `https://docs.cohere.com/docs/command-a-reasoning/`
- `https://docs.cohere.com/v2/docs/rate-limits`
- `https://docs.cohere.com/v2/reference/chat`
- `https://docs.cohere.com/v2/docs/structured-outputs`
- `https://cohere.com/pricing`

Historical GitHub Actions run `33104385499` already proved that `COHERE_API_KEY` is configured in the
repository. That historical run evaluated the different frozen model `command-a-plus-05-2026` under
V3 and is not reused as a semantic result for this route.

## Native V2 transport boundary

Command A Reasoning responses may contain a `thinking` content block before the final `text` block.
The qualification-only client therefore uses Cohere Chat V2 and mechanically ignores non-text
reasoning blocks, requiring exactly one final non-empty `text` block before JSON parsing. This does
not inspect, score, persist, or expose model reasoning and does not alter the provider-neutral V5
semantic contract.

The request uses Cohere V2 JSON-Schema structured output:

```text
response_format = {
  type: json_object,
  schema: <frozen V5 structured schema>
}
```

No candidate-specific source, semantic prompt, gold, scorer, threshold, or V5 schema change is
introduced.

## Frozen V5 contract

The candidate receives the canonical V5 contract exactly as frozen in:

- `tests/fixtures/event_understanding_qualification_v5.json`
- `insight_desk/event_understanding_adapter_v4.py`
- `scripts/qualify_event_understanding_provider_v5.py`

The same four historical exact-source cases, source metadata, semantic gold, scorer, distinct
event-draft matching, exact-text evidence binding, deterministic invariants, and 4/4 acceptance are
used.

## Isolation boundary

Qualification-only files:

- `insight_desk/providers/cohere_command_a_reasoning.py`
- `scripts/qualify_cohere_command_a_reasoning_v5.py`
- `tests/test_cohere_command_a_reasoning_v5_event_understanding_provider.py`
- this document

The frozen `insight_desk/providers/cohere.py` remains unchanged. The candidate is not exported from
`insight_desk.providers`, not added to production selection, and not wired into production. The
wrapper scope-registers the candidate only inside the V5 runner and restores canonical runner state
on exit.

## One-shot execution gate

Before any real provider request:

1. ordinary Infrastructure must be SUCCESS on the exact candidate head;
2. historical production replay must be SUCCESS;
3. Phase 6 correctness/recall must be SUCCESS;
4. final diff must remain qualification-only;
5. a temporary branch-specific CI lane may be added without its trigger;
6. that lane must be observed SKIPPED while ordinary jobs remain GREEN;
7. exactly one later trigger commit may execute the four-case qualification.

The first valid result is frozen. There is no provider rerun and no candidate-specific tuning after
the result.

## Production and merge gates

A V5 4/4 result proves minimum compatibility only. It does not by itself remove the three migration
blockers, wire production, authorize fresh live, deploy, Push, or merge. PR #84 remains OPEN and
UNMERGED until all downstream migration/publication acceptance gates are separately proven.
