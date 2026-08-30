# Phase 4 Production Rewiring Closure

Status: **STRUCTURAL_COMPLETE / PRODUCTION_REWIRE_BLOCKED**

Exact code GREEN head: `781650a8b3bc10743c737c861691f8662c30ca73`

Phase 4 is structurally complete for the currently authorized migration scope. It is **not** permission to wire a new Event Understanding provider into production, run a fresh live, deploy, Push, or merge.

## What is closed

The production compatibility runtime now has one explicit owner per migrated responsibility:

- Canonical identity no longer calls claim-verification providers as a dedupe oracle.
- Canonical identity no longer reads `SourceDocument.body` or generated headline/summary surfaces.
- Legacy `CandidateEvent` / `EventFact` identity authority is not used by the active identity owner.
- BOK policy-meeting parent/child binding is derived from `CanonicalEvent` fields only. When the legacy bridge has a normalized `event_time`, that value is authoritative. When `event_time` is absent, a bounded fallback may use a matching explicit day-of-month marker already preserved in canonical action/object fields. Raw article bytes are never consulted.
- Generated headline/summary semantic duplicate authority has been removed from the active publication path.
- Duplicate evidence-integrity invocation has been removed; Phase 6 owns the active evidence-integrity decision.
- Typed `RelevanceDecision` ownership is explicit.
- Exact-source prose publication fallback was replaced with compact CanonicalEvent-driven recovery.
- Generic DEFER now has a bounded canonical identity resolution lane rather than verification-provider reuse.
- Verification is no longer followed by visible-topic/visible-quality semantic re-admission.
- A provider-free Event Understanding handoff boundary exists for validated `ArticleUnderstanding -> CanonicalEventDraft -> CanonicalEvent` promotion. Unresolved drafts cannot be silently promoted.

## Exact regression evidence at the GREEN head

GitHub Actions run `33246740065` on `781650a8b3bc10743c737c861691f8662c30ca73`:

- Infrastructure: SUCCESS
- Python core regressions: 1317 tests, 23 skipped, 0 failed
- preserved import/API boundaries: SUCCESS
- Push Worker: SUCCESS
- historical production replay: SUCCESS
- Phase 6 correctness + recall gate: SUCCESS

Daily Production run `33246740045` on the same head:

- PR live gate: SUCCESS
- build: SKIPPED
- deploy: SKIPPED
- push_notify: SKIPPED

No fresh live/deploy/Push was authorized or executed.

## Replay-discovered canonical identity correction

During the raw-body identity removal, historical replay initially failed only because `canonical_parent_events` dropped from the required minimum of 1 to 0.

A replay-only temporary registry diagnostic proved the actual economy CanonicalEvent shape produced by the current legacy bridge:

- event 1: actor `한국은행 금융통화위원회`; action `27일 회의를 열어 기준금리를 결정한다`; `event_time=null`; `object=null`; no participants.
- event 2: actor `한국은행`; action `27일 금융통화위원회에서 기준금리를 결정하고 수정 경제전망과 향후 6개월 점도표를 공개한다`; `event_time=null`; `object=null`; no participants.

The permanent identity rule was therefore corrected to consume the canonical action schedule marker only when normalized `event_time` is absent. A different explicit day marker remains DEFER and cannot bind the parent. The temporary diagnostic test was removed before the GREEN head.

## Why production rewiring remains blocked

`config/event_understanding_migration_gate_v2.json` still has exactly one active runtime blocker:

`candidate_event_direct_canonical_lift`

That bridge remains necessary because the active provider state is still:

```text
qualification_contract_status = AWAITING_PROVIDER_QUALIFICATION
provider_inventory_status = CANDIDATE_QUALIFICATION_BLOCKED
selected_event_understanding_provider = null
production_wired = false
full_production_correctness_claimed = false
```

The identity raw-body blocker and legacy candidate-identity blocker are both inactive.

Therefore:

- `production_rewire_allowed = false` remains correct.
- the legacy evidence-bound `CandidateEvent/EventFact -> CanonicalEvent` bridge remains active only as a compatibility bridge.
- no provider search/retry is authorized by this closure.
- no existing V4/V5 non-pass may be promoted or reused as a production selection.

## Phase transition

Phase 4 structural work is closed. The next permitted work is **Phase 5 production replay closure** using the same public production entrypoint and recorded external edges.

Phase 5 must continue to state the historical artifact limitation precisely: the preserved replay fixture contains exact historical source excerpts, not complete original publisher article bodies. That limitation cannot be relabeled as a full raw-body acquisition replay. Fresh acquisition proof belongs to the later fresh-canary phase.
