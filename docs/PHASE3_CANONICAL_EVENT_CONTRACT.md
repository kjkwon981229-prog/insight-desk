# Phase 3 — Canonical Event Contract Freeze

Status: **COMPLETE / PRODUCTION REWIRE NOT YET AUTHORIZED BY THIS DOCUMENT**

Phase 2 froze semantic ownership. Phase 3 freezes the event data contract that those owners exchange and proves the lossless resolved-draft-to-canonical boundary.

## 1. Primary invariant

Downstream owners must not need to reread raw article text, generated prose, or legacy EventFact objects merely to recover semantic information that Event Understanding already established.

The canonical event boundary therefore preserves source-bound event semantics explicitly.

## 2. CanonicalEvent semantic payload

`CanonicalEvent` now has additive first-class slots for:

- `fact_ids`
- `evidence_ids`
- `evidence_refs`
- `temporal_state`
- `certainty`
- `polarity`
- `location`
- `cause`

Existing canonical fields remain backward compatible.

The current production bridge populates the legacy-compatible fact/evidence ids and semantic fields directly from the single evidence-bound `EventFact` used to create the candidate. It does not infer new values.

Synthetic parent events do not fabricate child-specific certainty, polarity, location, cause, or evidence identity. Optional fields remain unset unless the parent contract can support them independently.

## 3. Exact canonical evidence lineage

`CanonicalEvidenceRef` preserves immutable source-range provenance with:

```text
source_id
field = title | body
start
end
text_sha256
```

`CanonicalPublicationBundle.validate()` validates every canonical evidence range against the referenced `SourceDocument` bytes and digest.

This prevents a future downstream owner from treating generated prose as provenance or reconstructing source evidence approximately.

Legacy `evidence_ids` remain during migration for compatibility. New Event Understanding migration uses exact `evidence_refs`.

## 4. CanonicalEventDraft semantic payload

`CanonicalEventDraft` has additive optional slots for:

- `temporal_state`
- `certainty`
- `polarity`
- `location`
- `cause`

This keeps the future Event Understanding handoff capable of expressing the same semantics that the current legacy bridge preserves.

## 5. Lossless resolved draft -> canonical lift

`canonical_event_from_draft()` is now a public clean-core contract.

It performs only the canonical boundary transformation:

```text
CanonicalEventDraft
  + identity-assigned event_id
  + publication_time
  + optional identity-assigned parent_event_id
  -> CanonicalEvent
```

It copies event semantics without reinterpretation and converts every `UnderstandingEvidenceRef` into a `CanonicalEvidenceRef` with the same source/field/range/digest.

Important ownership rules:

- an `UNRESOLVED` draft cannot become a CanonicalEvent;
- `parent_event_hint` is not promoted automatically;
- the Canonical Identity owner must supply a real `parent_event_id` after event-family resolution;
- identity may assign IDs/relations but may not rewrite Event Understanding semantics;
- no legacy fact/evidence id is fabricated when lifting a new-style draft.

The public `insight_desk.core` API exports both `CanonicalEvidenceRef` and `canonical_event_from_draft`.

## 6. Uncertainty remains first-class

The Event Understanding contract distinguishes:

- `UnderstandingStatus.RESOLVED`
- `UnderstandingStatus.UNRESOLVED`

and requires `uncertainty_reasons` for unresolved article/event understanding.

This is preserved. Missing semantic values are not automatically false values, and unresolved understanding is not equivalent to DROP.

The canonical lift enforces that boundary by refusing unresolved drafts.

## 7. V5 provider qualification boundary is intentionally frozen

The currently frozen provider qualification protocol is V5 and uses `event_understanding_schema_v4`.

Phase 3 does **not** silently mutate that provider-facing schema or adapter. Doing so would retroactively change the contract under which existing provider artifacts were evaluated.

Consequences:

1. Existing V5 qualification evidence remains historically valid for exactly the frozen V5 contract.
2. No V5 provider is selected or production-wired now, so no runtime behavior is lost by keeping the provider-facing contract frozen.
3. The newly added optional internal draft fields do not change old V5 payload parsing; old payloads simply leave those fields unset.
4. Before a future provider can become the production Event Understanding owner for the expanded Phase 3 contract, the migration gate must explicitly define whether these fields are provider-required, evidence-bound owner-derived, or legitimately optional for that event class.
5. If the provider-facing contract is expanded, that requires a **new qualification protocol/schema version**, not an edit to frozen V5 evidence.

Provider search remains stopped. This requirement is a migration invariant, not authorization to resume candidate shopping.

## 8. RED/GREEN evidence

Three regression families freeze the Phase 3 boundary.

### Production bridge preservation

`tests/test_phase3_canonical_event_information_preservation.py`

Proves that the current `EventFact -> CanonicalEvent` bridge preserves fact/evidence identity and temporal/certainty/polarity/location/cause semantics.

### Event Understanding draft capacity

`tests/test_phase3_event_understanding_draft_semantics.py`

Proves that `CanonicalEventDraft` can carry the expanded event-semantic fields without mutating the frozen V5 provider-facing schema.

### Draft -> canonical lift

`tests/test_phase3_event_draft_to_canonical_lift.py`

Proves both:

- a resolved draft lifts without semantic or exact evidence-range loss;
- an unresolved draft cannot be silently promoted to a CanonicalEvent.

## 9. Same-head GREEN evidence

Exact code/API head before this documentation-only completion commit:

`09835798f575a87292eeace2d2a83f29cbab7d24`

Infrastructure CI:

- Python: **1287 tests / 23 skipped / 0 failed**
- benchmark: **85 / 7 / 16 / 15 / 44**
- Push Worker: **20 / 20 PASS**
- npm audit: **0 vulnerabilities**

Historical production replay: **SUCCESS**

Phase 6 correctness and recall gate: **SUCCESS**

Daily production safety gate: **SUCCESS**, while build / deploy / push_notify were **SKIPPED**.

No fresh production live was authorized or executed by this closure.

## 10. Long-body publication relevance

This contract work directly addresses the architecture behind the historical oversized-article UI failure class.

The required data flow is:

```text
SourceDocument.body
  -> Event Understanding evidence
  -> CanonicalEventDraft / CanonicalEvent semantics
  -> compact PublicationDraft
  -> Verification
  -> VerifiedPublication
  -> PWA
```

Raw body is evidence input, not a publication substitute.

Current normal generation/publication/PWA contracts already prevent a multi-thousand-character raw body from reaching the UI through the standard path. Phase 4 must still remove the bounded exact-source prose fallback as a semantic/product bypass and enforce the final no-body-substitution rule without article-specific detectors.

## 11. Phase 3 acceptance

The Phase 3 contract now proves:

- current EventFact semantics are not lost at the CanonicalEvent bridge;
- future CanonicalEventDrafts can carry the same semantic dimensions;
- exact source-range provenance can survive into CanonicalEvent;
- unresolved understanding cannot be promoted into a resolved canonical event;
- identity assignment is separated from semantic rewriting;
- frozen V5 qualification evidence remains unchanged.

**PHASE 3 = COMPLETE.**

## 12. Next permitted work — Phase 4

Phase 4 may now rewire production against the frozen Phase 2 ownership and Phase 3 contracts.

Priority migration blockers are:

1. remove verification-family providers from same-event identity judgment;
2. route new Event Understanding output through `CanonicalEventDraft -> canonical_event_from_draft()` when a qualified production owner exists, while preserving a bounded migration adapter until then;
3. remove downstream headline/summary duplicate gates as semantic event-identity authorities;
4. remove duplicate evidence-integrity invocation;
5. replace configured-literal relevance with an explicit `RelevanceDecision` owner contract without reintroducing downstream re-admission;
6. redesign generation recovery so raw/extractive source prose is never used as a substitute for compact CanonicalEvent-driven publication text;
7. implement an explicit bounded DEFER/resolution lane rather than silent semantic omission.

Phase 4 must proceed by structural RED/GREEN migrations. It must not resume regex/detector patching, provider shopping, fresh live, deployment, Push, or merge.