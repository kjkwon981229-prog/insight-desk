# Phase 3 — Canonical Event Contract Freeze

Status: **CONTRACT MIGRATION IN PROGRESS / PRODUCTION REWIRE NOT AUTHORIZED**

Phase 2 froze semantic ownership. Phase 3 now freezes the event data contract that those owners exchange.

## 1. Primary invariant

Downstream owners must not need to reread raw article text, generated prose, or legacy EventFact objects merely to recover semantic information that Event Understanding already established.

The canonical event boundary therefore preserves source-bound event semantics explicitly.

## 2. CanonicalEvent semantic payload

`CanonicalEvent` now has additive first-class slots for:

- `fact_ids`
- `evidence_ids`
- `temporal_state`
- `certainty`
- `polarity`
- `location`
- `cause`

Existing canonical fields remain unchanged and backward compatible.

The current production bridge populates these fields directly from the single evidence-bound `EventFact` used to create the candidate. It does not infer new values.

Synthetic parent events do not fabricate child-specific certainty, polarity, location, cause, or evidence identity. Optional fields remain unset unless the parent contract can support them independently.

## 3. CanonicalEventDraft semantic payload

`CanonicalEventDraft` now has additive optional slots for the same event-semantic dimensions:

- `temporal_state`
- `certainty`
- `polarity`
- `location`
- `cause`

This keeps the future Event Understanding handoff capable of expressing the same semantics that the current legacy bridge can preserve.

`UnderstandingEvidenceRef` remains the preferred future evidence-lineage contract. Legacy `evidence_ids` are preserved on the current production CanonicalEvent so migration does not destroy provenance before the new owner is wired.

## 4. Uncertainty remains first-class

The existing Event Understanding contract already distinguishes:

- `UnderstandingStatus.RESOLVED`
- `UnderstandingStatus.UNRESOLVED`

and requires `uncertainty_reasons` for unresolved article/event understanding.

This is preserved. Missing semantic values are not automatically false values, and unresolved understanding is not equivalent to DROP.

## 5. V5 provider qualification boundary is intentionally frozen

The currently frozen provider qualification protocol is V5 and uses `event_understanding_schema_v4`.

Phase 3 does **not** silently mutate that provider-facing schema or adapter. Doing so would retroactively change the contract under which existing provider artifacts were evaluated.

Consequences:

1. Existing V5 qualification evidence remains historically valid for exactly the frozen V5 contract.
2. No V5 provider is selected or production-wired now, so no runtime behavior is lost by keeping the provider-facing contract frozen.
3. The newly added optional internal draft fields do not change old V5 payload parsing; old payloads simply leave those fields unset.
4. Before a future provider can become the production Event Understanding owner for the expanded Phase 3 contract, the migration gate must explicitly define whether these fields are:
   - provider-required,
   - owner-derived from another evidence-bound semantic component, or
   - legitimately optional for that event class.
5. If the provider-facing contract is expanded, that requires a **new qualification protocol/schema version**, not an edit to frozen V5 evidence.

Provider search is still stopped. This requirement is a migration invariant, not authorization to resume candidate shopping.

## 6. Information-preservation regressions

Two RED/GREEN families freeze the Phase 3 boundary:

### Production bridge preservation

`tests/test_phase3_canonical_event_information_preservation.py`

Proves that the current `EventFact -> CanonicalEvent` bridge preserves fact/evidence identity and temporal/certainty/polarity/location/cause semantics.

### Event Understanding draft capacity

`tests/test_phase3_event_understanding_draft_semantics.py`

Proves that `CanonicalEventDraft` can carry the expanded event-semantic fields without requiring a provider-facing schema mutation.

## 7. Remaining Phase 3 work

Before declaring Phase 3 complete, the migration boundary still needs one explicit transformation contract:

```text
CanonicalEventDraft
  + canonical identity assignment
  + source/evidence lineage
  -> CanonicalEvent
```

That transformation must prove:

- semantic fields are copied without loss;
- exact evidence lineage is retained in a canonical representation;
- unresolved drafts cannot be silently promoted into publishable resolved events;
- identity may assign canonical ids/relations but may not rewrite Event Understanding semantics;
- parent/child relations do not destroy child semantics.

Only after that transformation is RED/GREEN proven may Phase 3 be marked COMPLETE and Phase 4 production rewiring begin.

## 8. Long-body publication relevance

This contract work is directly related to the historical oversized-article UI failure class.

The intended data flow is:

```text
SourceDocument.body
  -> Event Understanding evidence
  -> CanonicalEventDraft / CanonicalEvent semantics
  -> compact PublicationDraft
  -> verification
  -> VerifiedPublication
  -> PWA
```

Raw body is evidence input, not a publication substitute. Phase 4 will address the remaining bounded exact-source generation fallback and enforce the final publication-side no-body-substitution rule without article-specific detectors.
