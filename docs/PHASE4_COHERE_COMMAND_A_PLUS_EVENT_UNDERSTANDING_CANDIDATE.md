# Cohere Command A+ — Event Understanding V3 Qualification

Status: `NOT_QUALIFIED`

## Frozen candidate

- Provider: Cohere
- Model: `command-a-plus-05-2026`
- Qualification protocol: 3
- Core contract: `event_understanding_v2`
- Structured-output schema: `event_understanding_schema_v2`
- Source mode: historical exact-source excerpt only
- Candidate head: `c3a7bc7bcd7f81b9f8f31ef14922950f7a49ea57`
- Workflow run: `33104385499`
- Artifact: `9659910291`
- Artifact digest: `sha256:73594960aa92f046fef4e7ee151721b6d40ba09e064963f9d3f5ba619f567259`

## Result

`evaluated_cases = 4`, `passed_cases = 0`.

All four frozen cases ended with the same bounded diagnostic:

```text
adapter_contract:adapter_output_contract
```

Cases:

- `run413-bok-kbs-rate-decision`
- `run413-bok-kmib-outlook-child`
- `run413-kpop-alphadriveone-actor-preserved`
- `run413-kbo-osen-same-game-source`

This is a definitive active-protocol non-pass. It is not `NOT_CONFIGURED`, `RATE_LIMITED`, or `QUALIFICATION_BLOCKED_TRANSIENT`.

## Boundary

The candidate used the frozen V3 fixture, semantic scopes, Event Understanding prompt, schema, scorer, and acceptance policy. The provider adapter only translated the existing structured-client interface to Cohere's fixed `command-a-plus-05-2026` API contract. No production wiring was added.

The one-shot qualification lane is removed after this result. The Cohere candidate must not be tuned or rerun by changing prompt, schema, source scope, gold, scorer, evidence requirements, or case selection.

This evidence does not authorize migration-gate removal, production wiring, fresh live, marker, deploy, Push, or merge.
