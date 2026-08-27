# PHASE 4 — Event Understanding Architecture Freeze

Status: ARCHITECTURE AUDIT / NO FRESH LIVE

This document supersedes the post-#464 live-derived patch direction. The branch was restored to the pre-live orchestration baseline. No new detector, regex gate, production marker, or fresh production run is authorized by this document.

## 1. Product invariant

Insight Desk exists to discover enough relevant current news, understand the actual events, consolidate event identity, express verified cards, render them in the PWA, and notify users when the publication set changes.

The engine is not a bad-sentence detector.

## 2. Current baseline audit

### KEEP

- `SourceDocument` exact URL/provenance/body SHA binding.
- `AuthoritativeFact` and the ECOS/KOSIS/OpenDART enrichment boundary.
- `VerifiedPublication`, publication identity manifest/digest, PWA projection, and Push publication binding.
- Execution-scoped V2 runtime installation/restoration.
- Mechanical evidence-integrity and publication-contract validation.

### DEMOTE

- `SemanticPipeline`, `FactDraft`, `EventFact`, and `CandidateEvent` are evidence/fact extraction auxiliaries only.
- Deterministic date recovery may provide an evidence-bound hint, but it is not event understanding.
- Existing source/headline fingerprints may remain historical regression evidence, not canonical identity authority.

### REMOVE FROM PRODUCTION AUTHORITY

- Direct `CandidateEvent -> CanonicalEvent` wrapping through `canonical_event_from_candidate()`.
- Any event-level relevance stage that re-reads source/evidence after semantic understanding and independently decides article meaning.
- Identity logic that re-opens raw article bodies to decide same/different/parent-child after the understanding handoff.
- Visible headline/summary semantic admission or dedupe as an event-identity authority.
- Human-audit-derived one-off semantic patches.

### REPLACE

- Add a real Event Understanding owner that consumes relevant `SourceDocument` sets and produces `ArticleUnderstanding`.
- `ArticleUnderstanding` contains one or more `CanonicalEventDraft` values with explicit primary/context role, topic relation, event type, actor/action/object, time, attribution, metrics, evidence lineage, and uncertainty.
- Authoritative enrichment attaches authoritative facts to drafts without deciding relevance or identity.
- Canonical identity consumes only enriched event drafts and produces final `CanonicalEvent` identities/parent-child relationships.

## 3. Required semantic handoff

```text
ArticleCandidate
    -> SourceDocument
    -> RelevanceDecision
    -> EventUnderstandingRequest(topic, semantic_scope, SourceDocument[])
    -> ArticleUnderstanding
         -> CanonicalEventDraft[]
    -> EnrichedEventDraftSet
    -> CanonicalEventSet
    -> PublicationDraft
    -> VerifiedClaims
    -> VerifiedPublication
    -> PWA
    -> Push
```

`semantic_scope` is a natural-language statement of the user's topic interest. It is deliberately separate from discovery/relevance keyword lists; `intent_anchors`, `required_intent_terms`, and `event_terms` are not Event Understanding inputs.

`CanonicalEventDraft` is not a final event identity. `draft_id` is provisional and source-scoped. Only the identity owner may merge drafts, split them, or assign canonical parent/child event identities.

## 4. Evidence-lineage contract

The Event Understanding provider may interpret meaning, but it may not invent provenance.

Every event draft cites one or more `UnderstandingEvidenceRef` values:

- `source_id`
- `field` (`title` or `body`)
- `start`
- `end`
- SHA-256 of the exact referenced substring

The provider chooses an exact verbatim source substring. The adapter locates that substring and deterministic code validates source membership, range bounds, and digest equality against immutable `SourceDocument` bytes. It does not judge the meaning of the cited text.

Legacy `EvidenceSpan` IDs are not the semantic handoff contract and cannot be used to make `SemanticPipeline` the Event Understanding authority.

## 5. Provider-agnostic port

`EventUnderstandingPort` exposes only:

```text
EventUnderstandingRequest(topic, semantic_scope, SourceDocument[])
    -> ArticleUnderstanding
```

No model is selected by this contract. A provider adapter must prove suitability separately before production wiring.

- Groq 120B remains frozen to its existing temporal auxiliary role.
- Groq 20B remains the existing briefing generator unless a separate bounded Event Understanding qualification demonstrates minimum compatibility.
- Strict JSON-schema capability alone is not semantic-quality evidence.

## 6. Bounded provider qualification

The only currently recoverable source-backed set contains four historical exact-source excerpts. A one-shot qualification may use those four records to test minimum semantic-contract compatibility. It must explicitly report that full raw bodies are unavailable and must not claim full production correctness or recall.

A failed provider/model qualification is a terminal `NOT_QUALIFIED` result for that tested contract. Do not tune the prompt against individual failures and rerun a patch loop.

No fresh article discovery, production PWA generation, deploy, or Push is part of provider qualification.

## 7. Uncertainty contract

`UNRESOLVED` is a first-class semantic result. It must not be converted to DROP by a boolean relevance helper.

Resolution order remains:

1. additional source evidence,
2. authoritative source/API when applicable,
3. semantic reevaluation,
4. verifier assistance where the question is claim support,
5. hold only when still unresolved.

Recall must not be purchased by silently discarding unresolved events.

## 8. Test policy

No new live-derived sentence detector regressions.

Allowed before runtime rewiring:

- contract invariants for `ArticleUnderstanding` / `CanonicalEventDraft`,
- exact source-range/digest provenance validation,
- provider-port conformance with fake adapters,
- single-owner input/output/forbidden-decision contracts,
- structural tests proving downstream owners do not reopen source text,
- bounded provider qualification over preserved real source excerpts,
- production replay only where real source material is actually preserved.

Fresh canary remains blocked until the runtime implements this handoff and replay evidence is sufficient to assess both correctness and recall.
