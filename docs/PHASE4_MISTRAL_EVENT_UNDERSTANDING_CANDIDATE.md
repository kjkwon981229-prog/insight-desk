# PHASE 4 — Dedicated Mistral Event Understanding Candidate

Status: `NOT_QUALIFIED UNDER ACTIVE QUALIFICATION V3 / PROVIDER TRANSIENT FAILURE / NO PRODUCTION WIRING`

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

Mistral was eligible for one V3 qualification because it was already the dedicated `event_understanding_candidate`, while the earlier result belonged to protocol 1 before the corrected V3 source/evidence contract. Groq, Gemini, Cloudflare, local NLI, and Groq 120B were not repurposed because they retain separate generation, verification, or temporal responsibilities.

## Final V3 one-shot outcome

Exact push run `33094503683`, head `a417ac291031358e547b00d59bccce2412fb9044`:

- infrastructure: SUCCESS
- historical-production-replay: SUCCESS
- Phase 6 correctness and recall gate: SUCCESS
- qualification protocol: 3
- evaluated: 4
- passed: 0
- status: `NOT_QUALIFIED`
- outcome classification: `PROVIDER_TRANSIENT_FAILURE`

All four fixed cases ended with the same bounded transport code:

- `run413-bok-kbs-rate-decision` — `provider_transport:transient_provider`
- `run413-bok-kmib-outlook-child` — `provider_transport:transient_provider`
- `run413-kpop-alphadriveone-actor-preserved` — `provider_transport:transient_provider`
- `run413-kbo-osen-same-game-source` — `provider_transport:transient_provider`

Evidence artifact:

- artifact id: `9656236318`
- digest: `sha256:5d469827740b3a08c7367fde230beccdd8e82f422491113cebd33a86b51dc666`

The artifact contains only bounded qualification metadata and failure codes. It does not expose source article text, raw provider responses, raw exception messages, or credentials.

## Interpretation boundary

This V3 outcome does **not** prove that Mistral Large 3 is semantically incapable of Event Understanding. The provider never produced a qualification result that could be scored for semantic compatibility in these four cases. What is proven is narrower: under the fixed V3 one-shot run, Mistral did not achieve `MINIMUM_COMPATIBILITY_PASS` because every case ended in provider transient transport failure.

The result must therefore not be converted into a semantic defect, prompt problem, schema problem, or evidence-contract problem. It also must not be used to justify candidate-specific prompt/schema/gold/scorer changes followed by retry.

## Frozen consequence

Mistral Large 3 is frozen in machine state as `NOT_QUALIFIED` under active qualification protocol V3 with `PROVIDER_TRANSIENT_FAILURE` classification. The historical protocol 1 evidence remains nested as prior evidence rather than being rewritten.

The provider inventory remains `NO_ELIGIBLE_EXISTING_PROVIDER`, `selected_event_understanding_provider` remains null, and `production_wired` remains false. The temporary Mistral V3 qualification workflow is removed after freezing this outcome, so ordinary branch activity cannot silently re-run the candidate.

No production marker, fresh discovery, fresh canonical live, PWA build, deploy, Push, or merge is authorized by this result.

A future Event Understanding candidate must be deliberately chosen as a new independent provider/model contract under the single-owner architecture and use protocol V3 unchanged. Existing generation, verification, identity, or temporal owners may not be silently repurposed.

Even a future `MINIMUM_COMPATIBILITY_PASS` would not itself authorize production wiring. The PHASE 4 migration gate remains closed until its legacy semantic bypasses are removed and identity consumes source-range-bound CanonicalEvent drafts without raw-source reinterpretation.
