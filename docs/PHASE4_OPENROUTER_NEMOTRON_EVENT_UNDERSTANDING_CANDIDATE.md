# PHASE 4 — OpenRouter Nemotron Event Understanding Candidate

Status: `NOT_QUALIFIED / NO PRODUCTION WIRING`

Candidate provider: OpenRouter
Candidate model: `nvidia/nemotron-3-super-120b-a12b:free`

## Candidate boundary

This was a qualification-only Event Understanding candidate. It was never exported through the production provider package surface and was never wired into production.

The model id was frozen to the explicit `:free` variant. The random `openrouter/free` router was forbidden, and the paid model variant without `:free` was also forbidden.

The request used `provider.require_parameters = true`, so OpenRouter could only use an endpoint supporting the requested structured-output parameters. There was no cross-model fallback.

## Qualification contract

The candidate reused, without modification:

- `tests/fixtures/event_understanding_qualification_v1.json`
- `config/semantic_topics_v2.json`
- `EVENT_UNDERSTANDING_SCHEMA_V1`
- the existing source-range evidence binding
- the existing scorer and all four historical exact-source excerpt cases

No fresh news, production marker, PWA build, deploy, or Push was involved.

## Valid one-shot qualification result

After `OPENROUTER_API_KEY` was deliberately configured, exact-head push run `33057003750` evaluated the frozen candidate at head `7b1230ea9ae5d0b5da3dc5725df55b2bb9fea1bf`.

Both prerequisite jobs completed successfully before qualification began:

- infrastructure: SUCCESS
- historical-production-replay: SUCCESS

The provider credential was present and masked by GitHub Actions, so this was not a credential-preflight failure. The real qualification result was:

```text
status = NOT_QUALIFIED
evaluated_cases = 4
passed_cases = 1
```

Per-case result:

- `run413-bok-kbs-rate-decision`: FAIL — `required_structured_literal`
- `run413-bok-kmib-outlook-child`: FAIL — `provider_transport:invalid_output`
- `run413-kpop-alphadriveone-actor-preserved`: FAIL — `provider_transport:invalid_output`
- `run413-kbo-osen-same-game-source`: PASS

Evidence artifact:

- artifact id: `9640144162`
- digest: `sha256:20a5a412407d5d1e80e4f14b1a23622872f3932cdf8f882debed6c0e85d90b61`

This is a valid bounded qualification failure. It does not authorize per-case prompt/schema/gold tuning, model-alias substitution, random free-router fallback, or retrying the same frozen candidate.

## Frozen consequence

`OpenRouter + nvidia/nemotron-3-super-120b-a12b:free` is frozen as `NOT_QUALIFIED` for `event_understanding_v1`.

The machine provider inventory remains `NO_ELIGIBLE_EXISTING_PROVIDER`, `selected_event_understanding_provider` remains null, and `production_wired` remains false.

The one-shot candidate workflow is removed after this result is frozen so the same candidate cannot retry automatically.

No production marker, fresh discovery, PWA build, deploy, or Push is authorized by this qualification result.

A future Event Understanding provider must be a deliberately selected independent candidate and must use the same frozen bounded qualification contract. Existing verification/generation/temporal owners may not be silently repurposed.

Independently, even a future `MINIMUM_COMPATIBILITY_PASS` does not by itself authorize production wiring. The PHASE 4 migration gate must still remove the three legacy semantic bypasses and preserve source-range-bound Event Understanding output before production rewiring can open.
