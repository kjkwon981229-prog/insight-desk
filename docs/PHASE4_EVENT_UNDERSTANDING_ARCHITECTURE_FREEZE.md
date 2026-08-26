# PHASE 4 — Event Understanding Architecture Freeze

Status: ARCHITECTURE AUDIT / NO FRESH LIVE

This document supersedes the post-#464 live-derived patch direction. The branch has been restored to the pre-live orchestration baseline. No new detector, regex gate, marker, or fresh production run is authorized by this document.

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

`CanonicalEventDraft` is not a final event identity. `draft_id` is provisional and source-scoped. Only the identity owner may merge drafts, split them, or assign canonical parent/child event identities.

## 4. Uncertainty contract

`UNRESOLVED` is a first-class semantic result. It must not be converted to DROP by a boolean relevance helper.

Resolution order remains:

1. additional source evidence,
2. authoritative source/API when applicable,
3. semantic reevaluation,
4. verifier assistance where the question is claim support,
5. hold only when still unresolved.

Recall must not be purchased by silently discarding unresolved events.

## 5. Provider freeze

This phase does not assign a new role to Groq 120B or any other provider. Provider selection for Event Understanding is a separate wiring decision and must be justified by existing provider capability/evidence before implementation.

## 6. Test policy

No new live-derived sentence detector regressions.

Allowed tests before runtime rewiring:

- contract invariants for `ArticleUnderstanding` / `CanonicalEventDraft`,
- single-owner input/output/forbidden-decision contracts,
- structural tests proving downstream owners do not reopen source text,
- production replay only where real source material is actually preserved.

Fresh canary remains blocked until the runtime implements this handoff and replay evidence is sufficient to assess both correctness and recall.
