# Insight Desk V3 renderer mapping contract

Status: UI V3 DATA MAPPING CANDIDATE

This document maps the frozen Soft Geometry V3 UI to the existing Phase 4 clean-room core contracts. The renderer must not invent data that the core does not provide.

## D3 / Daily Edition

Can be populated now from:
- `RenderedBriefing.entries` → number and ranking of published events
- `RenderedEntry.headline` → cover/secondary story headline
- `RenderedEntry.summary` → editor note / why-it-matters copy
- `CandidateEvent.topic_id` → topic label
- `EventFact.temporal_state` → state label
- `EventFact.event_date` → displayed date when a single unambiguous date exists
- supported `VerifiedClaim.evidence_ids` → evidence count and evidence detail
- `RenderedEntry.render_mode` → generated vs extractive-fallback label

Must not invent:
- numeric confidence
- watch-next text when no watch contract exists
- event-history timestamps

## F3 / Split Desk

Can be populated now from:
- selected `RenderedEntry`
- `CandidateEvent`
- associated `EventFact` records
- `VerifiedClaim`
- `EvidenceSpan`
- `RawArticle.provenance`
- verification check failures via `VerificationCheck.error_code`

The fourth metric is `VERDICT`, not numeric confidence.

If multiple facts disagree on temporal state or date, the renderer must show an indeterminate/needs-review state instead of arbitrarily selecting one value.

## G3 / Mobile Focus

Uses the same event view model as D3/F3. Mobile changes presentation, not semantic data.

The responsive renderer must not create a separate factual interpretation for mobile.

## E / Event Ledger

The visual design is frozen, but the current `ContractBundle` is a snapshot and does not contain persistent event-state history.

Therefore the real Event Ledger is **not renderer-ready yet**.

Until an event-history contract is added in the engine phase:
- do not fabricate historical transitions
- do not derive event transition time from unrelated article fetch time
- do not display fake continuity
- hide or disable the real ledger route in production

The static prototype may retain sample ledger content as a design reference only.

## Optional fields

### Watch next
Current core contract: unavailable.
Renderer behavior: hide when `None`.
Future architecture may add an explicit follow-up/watch contract; do not derive it from LLM prose without evidence.

### Partial verifier failure
A supported claim may still contain a verification check that failed technically while another independent check supported the claim. The renderer mapping exposes this as `has_partial_verifier_failure` so the UI can disclose the degraded verification path without falsely downgrading a supported claim.

## Hard invariants

1. Only `VerificationVerdict.SUPPORTED` claims may populate a published briefing entry.
2. The renderer never converts a missing value into an asserted fact.
3. No numeric confidence is shown unless a future core contract explicitly defines and validates such a value.
4. Mobile and desktop share the same factual view model.
5. Event-history UI remains unavailable until history exists in the core contract.
6. Extractive fallback remains visibly distinguishable from generated copy when useful for QA/operations.
