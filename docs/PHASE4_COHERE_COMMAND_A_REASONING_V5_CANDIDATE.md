# Phase 4 — Cohere Command A Reasoning Event Understanding V5 Candidate

Status: ONE-SHOT QUALIFICATION TRIGGERED — FIRST VALID RESULT MUST FREEZE

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

## Proven preflight and staging evidence

Initial qualification-only preflight head `47715e6f754207c816b7be187c6e95890f9af206` passed ordinary
validation in Actions run `33229670144`:

- Infrastructure: SUCCESS;
- historical production replay: SUCCESS;
- Phase 6 correctness/recall: SUCCESS;
- Python: 1236 tests / 23 skipped / 0 failed;
- benchmark: 85 / 7 / 16 / 15 / 44;
- Push Worker: 20/20;
- npm audit: 0 vulnerabilities;
- provider calls: 0.

The temporary lane was then staged without a trigger. Run `33229735386` exposed exactly one stale
historical test: the V3 Cohere A+ freeze test incorrectly forbade the shared `COHERE_API_KEY` string
from appearing anywhere in the workflow, even for a different exact Cohere route. No provider call
occurred in that failed staging run.

That stale assertion was narrowed only to its intended invariant — the historical A+ exact lane and
trigger remain absent. No production semantics, provider contract, V5 fixture, source, gold, scorer,
threshold, or acceptance rule changed.

Corrected staging head `7d37e7bf4296c73fe4cf28dd5365b5ddb0fa9ea3` then passed Actions run
`33229771741`:

- Infrastructure: SUCCESS;
- historical production replay: SUCCESS;
- Phase 6 correctness/recall: SUCCESS;
- `semantic-v5-provider-candidate-cohere-command-a-reasoning`: SKIPPED;
- provider calls: 0.

Therefore every pre-call one-shot gate is satisfied before this trigger commit.

## One-shot execution gate

This commit is the single trigger commit and contains the exact marker:

`[semantic-v5-candidate:command-a-reasoning-08-2025]`

The temporary branch-specific lane may therefore execute exactly one four-case V5 qualification
after its ordinary dependencies pass again on this exact trigger head.

The first valid provider result is final evidence for this exact model route. There is no provider
rerun and no candidate-specific tuning after the result. If the run is invalid because of our own
qualification harness rather than provider behavior, that must be classified separately and must
not be entered as provider qualification evidence.

## Production and merge gates

A V5 4/4 result proves minimum compatibility only. It does not by itself remove the three migration
blockers, wire production, authorize fresh live, deploy, Push, or merge. PR #84 remains OPEN and
UNMERGED until all downstream migration/publication acceptance gates are separately proven.
