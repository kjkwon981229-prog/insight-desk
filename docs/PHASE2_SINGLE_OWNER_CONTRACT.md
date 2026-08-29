# Phase 2 — Single-Owner Contract Freeze

Status: **FROZEN DESIGN CONTRACT / NO PRODUCTION REWIRE YET**

Phase 1 established what actually runs. Phase 2 establishes **who is allowed to decide what** before Phase 3 contract expansion and Phase 4 rewiring.

The central invariant is:

> One semantic question has exactly one runtime owner. Downstream components consume the owner's contract; they do not silently re-answer the same semantic question.

The Orchestrator coordinates calls, state, and failure routing. It is **not** a semantic judge.

---

## 1. Canonical pipeline

```text
Discovery
  -> ArticleCandidate
Source Acquisition
  -> SourceDocument
Relevance
  -> RelevanceDecision
Event Understanding
  -> ArticleUnderstanding / CanonicalEventDraft
Canonical Event Contract
  -> CanonicalEvent
Authoritative Enrichment
  -> AuthoritativeFact[]
Canonical Identity
  -> IdentityDecision / EventRelation
Generation
  -> PublicationDraft
Verification
  -> VerifiedClaims / VerificationDecision
Publication Contract
  -> VerifiedPublication
PWA Renderer
  -> deterministic UI bytes
Push Delivery
  -> publication-state notification
```

No stage may bypass the canonical object immediately upstream of it to recover hidden semantics from raw text unless that access is explicitly part of its own contract.

---

## 2. Orchestrator — coordination only

### Input

Pipeline state and typed outputs from owners.

### Output

Call ordering, retries/escalation according to explicit policy, audit state, and terminal run state.

### Allowed

- invoke the next owner;
- pass typed objects between owners;
- enforce budgets/timeouts;
- route `DEFER` to an explicit resolver/escalation path;
- stop on structural contract failure;
- record provenance and audit metadata.

### Forbidden

- infer topic relevance from text;
- decide event meaning;
- decide same-event identity;
- rewrite generation text;
- decide factual support;
- inspect a headline/summary and invent a semantic reject rule;
- convert `DEFER` into `EXCLUDE` merely for convenience.

---

## 3. Discovery Owner

### Input

`TopicIntent / SearchIntent`

### Output

`ArticleCandidate[]`

### Allowed decisions

- query construction;
- source-route invocation;
- candidate URL/title/source metadata collection;
- mechanical URL normalization;
- discovery-route availability/failure.

### Forbidden decisions

- article truth;
- event semantics;
- final relevance;
- same-event identity;
- publication quality.

### Failure behavior

One route failing must not redefine relevance. Other configured discovery routes may continue within budget.

### Current implementation lineage

`default_news_discovery()` with Naver + Bing RSS + GDELT.

---

## 4. Source Acquisition Owner

### Input

`ArticleCandidate`

### Output

`SourceDocument`

### Allowed decisions

- fetch/render route selection;
- extraction route selection;
- extraction-quality / body-usability checks;
- publisher/source URL/publication-time provenance binding;
- exact content hash.

### Forbidden decisions

- whether the story is interesting;
- event understanding;
- materiality as news meaning;
- same-event identity;
- summary generation.

### Failure behavior

Try the bounded acquisition fallback tree. If no usable source can be produced, return acquisition failure; do not synthesize article content.

### Current implementation lineage

HTTP+Trafilatura -> HTTP+deterministic extraction -> Playwright+Trafilatura -> Playwright+deterministic extraction.

---

## 5. Relevance Owner

### Input

`SourceDocument + TopicIntent`

### Output

`RelevanceDecision`

Suggested contract:

```text
RelevanceDecision {
  topic_id
  verdict: RELEVANT | IRRELEVANT | DEFER
  evidence_refs
  reason_codes
  confidence_or_resolution_state
}
```

### Allowed decisions

- whether this source is about the user's configured topic/intent;
- identify exact source evidence supporting the relevance decision;
- return `DEFER` when the source is genuinely ambiguous.

### Forbidden decisions

- extract final event facts;
- decide material-event truth separately from Event Understanding;
- dedupe;
- verify generated claims;
- judge headline/summary style.

### Escalation

`DEFER` may request additional source evidence or a bounded semantic resolver. It must not silently become a drop because a literal keyword is absent.

### Current debt to remove

- configured-literal `topic_relevant()` as the complete relevance contract;
- any downstream re-admission / visible-topic semantic gate.

---

## 6. Event Understanding Owner

### Input

`SourceDocument + RelevanceDecision`

### Output

`ArticleUnderstanding` containing one or more `CanonicalEventDraft` objects.

Required semantic responsibilities:

- actor / action / object;
- event type;
- event time and temporal/lifecycle state;
- participants;
- location / cause when supported;
- certainty / polarity;
- source evidence binding;
- parent/child hints when the source explicitly distinguishes events;
- multiple distinct events from one article when warranted;
- explicit uncertainty rather than fabricated completion.

### Allowed decisions

Only this owner may interpret source text into event semantics.

### Forbidden decisions

- global same-event comparison against other articles;
- final canonical identity merge;
- prose generation;
- claim verification;
- UI quality detection;
- publication acceptance.

### Failure / uncertainty behavior

Return typed uncertainty or `DEFER` with evidence, not an implicit negative semantic label.

The Orchestrator may obtain additional sources/authority or invoke an approved semantic resolver. It may not mutate the event meaning itself.

### Provider rule

The implementation may be a qualified model, deterministic semantic system, or a bounded adapter during migration, but **there is still exactly one Event Understanding owner contract**. Provider choice does not change ownership.

### Current debt to remove

`LegacySemanticPipeline -> EventFact/CandidateEvent -> direct CanonicalEvent lift` as permanent architecture.

---

## 7. Canonical Event Contract

This is a data contract, not a semantic owner.

A CanonicalEvent must preserve the evidence-bound semantic information needed downstream without forcing downstream owners to reread raw article text to recover lost meaning.

Phase 3 must define the exact schema, including at minimum:

- stable event id;
- topic;
- actor/action/object;
- event type;
- event time;
- temporal/lifecycle state;
- participants;
- location;
- cause;
- certainty;
- polarity;
- evidence references;
- source ids;
- parent event id / relation state;
- authoritative fact ids;
- explicit unresolved fields when necessary.

Raw source body remains in `SourceDocument`, not duplicated into the publication object.

---

## 8. Authoritative Enrichment Owner

### Input

`CanonicalEvent + SourceDocument + configured authoritative-source policy`

### Output

`AuthoritativeFact[]`

### Allowed decisions

- determine whether a configured authority query is applicable;
- query ECOS/KOSIS/OpenDART or another explicitly configured authority;
- attach source-identified authoritative facts;
- report no-match/unavailable without changing the event meaning.

### Forbidden decisions

- rewrite CanonicalEvent semantics merely because an authority is unavailable;
- decide article relevance;
- same-event dedupe;
- generation;
- claim verification.

### Failure behavior

Unavailable authority is enrichment-missing unless a later explicit publication policy requires a specific authority for that claim class.

---

## 9. Canonical Identity Owner

### Input

`CanonicalEvent candidate + existing CanonicalEvent set + source/evidence identity references needed by the identity contract`

### Output

```text
IdentityDecision {
  relation: SAME_EVENT | DIFFERENT_EVENT | PARENT_CHILD | DEFER
  canonical_event_id / parent_event_id
  evidence
  reason_codes
}
```

### Allowed decisions

- same event vs different event;
- parent/child event relation;
- deterministic identity conflicts;
- event merge/association under the identity contract.

### Forbidden decisions

- use generated headline/summary as semantic truth;
- call the claim-verification owner as a dedupe oracle;
- decide factual support of publication prose;
- alter event meaning to make two events merge;
- silently treat ambiguity as same-event or different-event.

### Escalation

Identity `DEFER` may invoke an identity-specific semantic resolver or obtain additional sources. It must not borrow Cloudflare/Local-NLI claim verification simply because those tools already exist.

### Current debt to remove

- verifier-family providers used by `judge_same_event_mutual_entailment`;
- legacy candidate identity authority;
- normalized headline/summary exact duplicate gates as semantic identity authority.

Mechanical source duplicate checks may remain at Source Acquisition/Discovery level when they prove byte/source duplication rather than event identity.

---

## 10. Generation Owner

### Input

`CanonicalEvent + evidence references + optional AuthoritativeFact[]`

### Output

```text
PublicationDraft {
  event_id
  headline
  summary
  evidence_refs
  render_mode
}
```

### Allowed decisions

- express already-understood event facts in concise user-facing Korean;
- choose wording/order;
- use an explicitly defined recovery mode when model generation fails.

### Forbidden decisions

- decide whether the source is relevant;
- invent event facts;
- decide same-event identity;
- perform final factual verification;
- copy raw article body as a substitute for understanding;
- re-run StoryAdmission or another semantic news-quality classifier.

### Required product contract

- headline compact and standalone;
- summary compact and event-centered;
- body replacement is forbidden;
- raw body prefix clipping is forbidden;
- exact-source recovery, if retained, must still satisfy the same publication semantics and compactness contract.

### Historical long-body acceptance invariant

For any long source article:

```text
PublicationDraft.summary != SourceDocument.body
PublicationDraft.summary is not a large body prefix
PublicationDraft.summary represents the CanonicalEvent
```

The current 120/420 hard ceilings remain useful structural safety rails but are not sufficient semantic quality guarantees.

---

## 11. Verification Owner

### Input

`PublicationDraft + bound source/evidence + applicable AuthoritativeFact[]`

### Output

`VerificationDecision / VerifiedClaims`

### Allowed decisions

- whether visible claims are supported, contradicted, or unresolved by their bound evidence;
- provider failover according to verification policy;
- produce auditable verification checks.

### Forbidden decisions

- same-event dedupe;
- relevance;
- event extraction;
- rewrite the draft;
- judge whether a story is interesting/material;
- manufacture missing source evidence.

### Current route

Logical primary: Cloudflare -> Gemini failover when primary unavailable/indeterminate; Local NLI is an independent second confirmation in the supported route.

Exact routing may evolve, but ownership does not.

---

## 12. Publication Contract Owner

### Input

`CanonicalEvent + PublicationDraft + successful VerificationDecision + source identity + optional authority identity`

### Output

`VerifiedPublication`

### Allowed decisions

Structural acceptance only:

- required IDs exist and agree;
- all required visible claims are verified;
- headline/summary satisfy hard publication shape constraints;
- source URL and identity are valid;
- event/source/claim/check identities are preserved;
- publication digest can be deterministically computed.

### Forbidden decisions

- reinterpret article semantics;
- rewrite headline/summary;
- perform dedupe;
- recover raw article body when draft fields are missing;
- turn verification `UNRESOLVED` into support.

### Body-leak invariant

`VerifiedPublication` must not contain or expose `SourceDocument.body` as a display field.

The publication path must fail closed if the supplied summary violates the generation/publication contract; it must never substitute the source body.

---

## 13. PWA Renderer

### Input

`VerifiedPublication[] + PublicationIdentityManifest + runtime UI config`

### Output

Deterministic static application bytes.

### Allowed decisions

- HTML escaping;
- layout/presentation;
- labels directly derived from render mode / verified metadata;
- source-link rendering;
- manifest embedding.

### Forbidden decisions

- summarize;
- truncate raw body into a summary;
- infer topic/event meaning;
- fabricate unsupported UI facts;
- alter publication identity.

### Security / product invariant

The PWA view model should not contain raw article body. If the renderer does not receive body bytes, body leakage through the renderer becomes structurally impossible.

---

## 14. Push Delivery Owner

### Input

Publication state / digest / briefing identity.

### Output

Idempotent user notification.

### Allowed decisions

- whether the publication digest is new;
- send/retry delivery according to delivery policy;
- maintain idempotency state.

### Forbidden decisions

- decide article semantics;
- choose which event is true;
- modify publication content;
- send based on an unvalidated publication state.

---

## 15. Explicit uncertainty policy

The target architecture distinguishes:

```text
EXCLUDE = owner has enough evidence for a negative decision
DEFER   = owner lacks enough evidence for a safe decision
ERROR   = structural/provider/runtime failure
```

These states are not interchangeable.

For semantic owners (`Relevance`, `Event Understanding`, `Identity`, `Verification`), `DEFER` must have an explicit next action or bounded terminal policy. Examples:

- acquire another independent source;
- query authoritative data;
- invoke the owner-specific qualified resolver;
- preserve the item for a later pass;
- terminally omit only after the bounded resolution policy is exhausted, with the omission auditable as unresolved rather than semantically false.

The system must not adopt `ambiguous => drop` as its primary correctness mechanism.

---

## 16. Cross-owner forbidden edges

The following edges are explicitly forbidden in the final architecture:

```text
Verification -> Same-event dedupe
Generation -> Relevance / materiality re-admission
PWA -> SourceDocument.body summary fallback
Identity -> Generated headline/summary semantic truth
Orchestrator -> semantic re-judgment
Publication -> raw-body recovery
Authoritative enrichment -> article-meaning replacement
```

Any runtime path requiring one of these edges is a migration blocker.

---

## 17. Phase 2 acceptance

Phase 2 is complete when this ownership matrix is treated as the canonical migration contract and Phase 3/4 work can be evaluated against it.

Frozen owners:

1. Discovery
2. Source Acquisition
3. Relevance
4. Event Understanding
5. Authoritative Enrichment
6. Canonical Identity
7. Generation
8. Verification
9. Publication Contract
10. PWA Renderer
11. Push Delivery

Orchestrator is coordination-only and is deliberately not counted as a semantic owner.

**PHASE 2 = COMPLETE AS A DESIGN/OWNERSHIP FREEZE.**

No claim is made that current production already satisfies every contract above. The known violations become Phase 3/4 migration work.

---

## 18. Next permitted work — Phase 3

Freeze the full `CanonicalEvent` contract and associated typed decisions so downstream owners no longer need to recover semantics from legacy `EventFact`, `CandidateEvent`, generated text, or raw source body.

Phase 3 must include contract tests for information preservation and explicit uncertainty. It must not begin production rewiring until the contract itself is RED/GREEN proven.
