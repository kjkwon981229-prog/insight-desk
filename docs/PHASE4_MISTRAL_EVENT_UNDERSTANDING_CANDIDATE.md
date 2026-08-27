# PHASE 4 — Dedicated Mistral Event Understanding Candidate

Status: `QUALIFICATION_BLOCKED_TRANSIENT UNDER ACTIVE V3 / NO PRODUCTION WIRING`

Candidate provider: Mistral API  
Candidate model: `mistral-large-2512` (Mistral Large 3)

## Candidate boundary

This candidate is separate from the existing Groq generation and Cloudflare/Gemini/local-NLI verification responsibilities. It remains qualification-only and is not exported through the production provider package surface or wired into production.

The active bounded qualification uses the frozen Event Understanding semantic gold, topic scopes, four historical exact-source excerpt cases, `event_understanding_v2` core contract, and `event_understanding_schema_v2` structured-output schema. Protocol V3 additionally binds the corrected SourceDocument metadata and explicit evidence-range handoff.

## Historical V1 evidence

Configured V1 run `33050426588`, head `71d4c88731ae86a0084ef34862ac1c2d7bc30bbd`:

- qualification protocol: 1
- evaluated: 4
- passed: 0
- recorded failure classification: `ContractError`
- artifact: `9637447266`
- digest: `sha256:a84835d17ad5b9dae372ba381e4809c682b74cee63c7b661a15bdd0b051475fa`

This record remains historical evidence only. It cannot be reused as an active V3 qualification result.

## V3 one-shot prerequisite

Before any V3 provider call, the corrected adapter/source contract and bounded failure observability were independently GREEN. Qualification diagnostics expose stage or transport codes only; article body text, date strings, raw exception text, and provider payloads are not written into the qualification artifact.

Mistral was eligible for one V3 qualification because it was already the dedicated `event_understanding_candidate`, while the earlier result belonged to protocol 1 before the corrected V3 source/evidence contract. Existing generation, verification, and temporal owners were not repurposed.

## V3 run evidence

Exact push run `33094503683`, head `a417ac291031358e547b00d59bccce2412fb9044`:

- infrastructure: SUCCESS
- historical-production-replay: SUCCESS
- Phase 6 correctness and recall gate: SUCCESS
- qualification protocol: 3
- evaluated: 4
- passed: 0
- raw harness status at that head: `NOT_QUALIFIED`

All four fixed cases ended with the same bounded transport code:

- `run413-bok-kbs-rate-decision` — `provider_transport:transient_provider`
- `run413-bok-kmib-outlook-child` — `provider_transport:transient_provider`
- `run413-kpop-alphadriveone-actor-preserved` — `provider_transport:transient_provider`
- `run413-kbo-osen-same-game-source` — `provider_transport:transient_provider`

Evidence artifact:

- artifact id: `9656236318`
- digest: `sha256:5d469827740b3a08c7367fde230beccdd8e82f422491113cebd33a86b51dc666`

The artifact is immutable evidence of what the V3 harness emitted at that head. It is not rewritten after the lifecycle correction.

## Lifecycle correction

Independent review found that the V3 harness collapsed every non-PASS outcome into `NOT_QUALIFIED`, even when no semantic, schema, adapter, or scoring result had been obtained because the provider was transiently unavailable. That conflated operational unavailability with definitive incompatibility.

The qualification lifecycle therefore distinguishes:

- `MINIMUM_COMPATIBILITY_PASS` — every fixed case passed;
- `NOT_QUALIFIED` — at least one definitive semantic, adapter, contract, scoring, or non-transient output failure exists;
- `QUALIFICATION_BLOCKED_TRANSIENT` — all unresolved cases are blocked only by transient provider transport or rate limiting;
- `NOT_CONFIGURED` — credential preflight stopped before provider evaluation.

Under that corrected lifecycle, run `33094503683` is normalized in machine state to `QUALIFICATION_BLOCKED_TRANSIENT`. The original artifact field `status=NOT_QUALIFIED` remains preserved as `raw_run_status` evidence rather than being silently rewritten.

This correction does **not** claim Mistral passed qualification and does **not** prove Mistral failed semantic compatibility. It says only that the active V3 qualification remains incomplete because the provider was operationally unavailable during every fixed case.

## Current consequence

Machine state is `CANDIDATE_QUALIFICATION_BLOCKED`; `selected_event_understanding_provider` remains null and `production_wired` remains false. A transiently blocked provider is mechanically ineligible for selection.

No automatic retry is enabled. Any later continuation of Mistral qualification must be separately authorized after the lifecycle correction itself is GREEN and must use exactly the same V3 provider/model/prompt/schema/gold/scorer contract. A transient continuation is not permission to tune the candidate or enter a patch/retry loop.

No production marker, fresh discovery, fresh canonical live, PWA build, deploy, Push, or merge is authorized.

Even a later `MINIMUM_COMPATIBILITY_PASS` would not itself authorize production wiring. The PHASE 4 migration gate remains closed until the legacy semantic bypasses are removed and identity consumes source-range-bound CanonicalEvent drafts without raw-source reinterpretation.
