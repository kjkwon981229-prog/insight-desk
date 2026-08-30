# Phase 4 — Cohere Command A Reasoning Event Understanding V5 Candidate

Status: FROZEN NOT_QUALIFIED — 2/4 — NO RETRY

## Exact candidate route

- provider: Cohere
- qualification provider id: `cohere_command_a_reasoning`
- exact model id: `command-a-reasoning-08-2025`
- endpoint: `/v2/chat`
- credential: existing `COHERE_API_KEY`
- production wiring: none
- active qualification protocol: V5
- required result: 4/4 only

This is a genuinely new exact provider/model route. Historical Cohere evidence remains frozen on
`command-a-plus-05-2026`; that route was not retried, reclassified, or reused as active V5 PASS
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
requests/minute and trial/new-model usage at up to 1,000 API calls/month, sufficient for this bounded
four-case qualification without a paid fallback.

Official references checked on 2026-08-29:

- `https://docs.cohere.com/docs/command-a-reasoning/`
- `https://docs.cohere.com/v2/docs/rate-limits`
- `https://docs.cohere.com/v2/reference/chat`
- `https://docs.cohere.com/v2/docs/structured-outputs`
- `https://cohere.com/pricing`

Historical GitHub Actions run `33104385499` had already proved that `COHERE_API_KEY` is configured in
the repository. That historical run evaluated the different frozen model `command-a-plus-05-2026`
under V3 and is not reused as semantic evidence for this route.

## Native V2 transport boundary

Command A Reasoning responses may contain a `thinking` content block before the final `text` block.
The qualification-only client therefore uses Cohere Chat V2 and mechanically ignores non-text
reasoning blocks, requiring exactly one final non-empty `text` block before JSON parsing. It does not
inspect, score, persist, or expose model reasoning and does not alter the provider-neutral V5
semantic contract.

The request uses Cohere V2 JSON-Schema structured output:

```text
response_format = {
  type: json_object,
  schema: <frozen V5 structured schema>
}
```

No candidate-specific source, semantic prompt, gold, scorer, threshold, or V5 schema change was
introduced.

## Frozen V5 contract

The candidate received the canonical V5 contract exactly as frozen in:

- `tests/fixtures/event_understanding_qualification_v5.json`
- `insight_desk/event_understanding_adapter_v4.py`
- `scripts/qualify_event_understanding_provider_v5.py`

The same four historical exact-source cases, source metadata, semantic gold, scorer, distinct
event-draft matching, exact-text evidence binding, deterministic invariants, and 4/4 acceptance were
used.

## Isolation boundary

Qualification/evidence files:

- `insight_desk/providers/cohere_command_a_reasoning.py`
- `scripts/qualify_cohere_command_a_reasoning_v5.py`
- `tests/test_cohere_command_a_reasoning_v5_event_understanding_provider.py`
- `tests/test_cohere_command_a_reasoning_v5_qualification_freeze.py`
- this document

The frozen `insight_desk/providers/cohere.py` remains unchanged. The candidate is not exported from
`insight_desk.providers`, is not added to production selection, and is not wired into production.
The wrapper scope-registers the candidate only inside the V5 runner and restores canonical runner
state on exit.

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

Corrected staging head `7d37e7bf4296c73fe4cf28dd5365b5ddb0fa9ea3` passed Actions run
`33229771741`:

- Infrastructure: SUCCESS;
- historical production replay: SUCCESS;
- Phase 6 correctness/recall: SUCCESS;
- `semantic-v5-provider-candidate-cohere-command-a-reasoning`: SKIPPED;
- provider calls: 0.

## Valid one-shot qualification result

The single trigger commit was:

`f264f06083bd9c23f425339d3b45ac12119dd585`

with exact marker:

`[semantic-v5-candidate:command-a-reasoning-08-2025]`

Actions run `33230437202` revalidated both ordinary dependencies before executing the provider lane:

- Infrastructure: SUCCESS;
- historical production replay: SUCCESS;
- Phase 6 correctness/recall: SUCCESS.

The one-shot qualification then produced a valid provider result:

- status: `NOT_QUALIFIED`;
- provider: `cohere_command_a_reasoning`;
- model: `command-a-reasoning-08-2025`;
- protocol: 5;
- evaluated cases: 4;
- passed cases: 2;
- source mode: `historical_exact_source_excerpt_only`;
- full production correctness claimed: false.

Passing cases:

- `run413-bok-kbs-rate-decision`;
- `run413-kpop-alphadriveone-actor-preserved`.

Failed cases:

- `run413-bok-kmib-outlook-child`
  - `event_drafts_min`
  - `expected_event_match`
  - `parent_hint_min`
- `run413-kbo-osen-same-game-source`
  - `expected_event_match`

This is a definitive semantic non-pass, not a transport, credential, rate-limit, provider-unavailable,
JSON-schema, or qualification-harness failure. The exact model route is therefore frozen and must
not be retried or candidate-specifically tuned.

## Frozen artifact evidence

GitHub Actions artifact:

- artifact ID: `9708318114`;
- artifact name: `event-understanding-v5-cohere-command-a-reasoning-candidate-33230437202`;
- artifact ZIP SHA-256:
  `8d695b37197d52e94f17fd488d0bb9645dc8464398fc8e946216451272f5610e`;
- internal report SHA-256:
  `e149d7fbd149e341c017a8ab96712a5f1032c60e15009348db69d915c8385d01`.

The artifact ZIP was downloaded independently after the run. Its SHA-256 matched the Actions digest,
and the internal JSON report was independently re-read and hashed. The report exactly confirmed the
2/4 result and case failures above.

The consumed one-shot CI lane was then removed immediately. `.github/workflows/ci.yml` was restored
to the ordinary workflow blob `72da8a9a2f8996ccdfb1af906c575911b25c28b0`.

## Machine-state consequence

This result does not create a selectable provider. Active V5 evidence now contains three definitive
non-passes:

- Mistral Medium 3.5: 3/4;
- Mistral Small 4: 1/4;
- Cohere Command A Reasoning: 2/4.

Therefore the machine state remains:

```text
active_qualification_protocol = 5
qualification_contract_status = AWAITING_PROVIDER_QUALIFICATION
provider_inventory_status = NO_ELIGIBLE_EXISTING_PROVIDER
selected_event_understanding_provider = null
production_wired = false
full_production_correctness_claimed = false
```

## Production and merge gates

A V5 4/4 result is still required before provider selection can begin. This 2/4 result does not
remove any migration blocker, wire production, authorize fresh live, deploy, Push, or merge.

PR #84 must remain OPEN and UNMERGED. The exact next semantic gate is to research and qualify one
genuinely new eligible provider/model under the same frozen V5 contract, with no retry of this exact
Cohere route and no provider-specific prompt/schema/source/gold/scorer/threshold tuning.
