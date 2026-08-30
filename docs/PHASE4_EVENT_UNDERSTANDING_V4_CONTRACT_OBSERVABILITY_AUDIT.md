# Phase 4 Event Understanding V4 — Contract Observability Audit

## Scope

This audit is provider-neutral. It does not change the V4 prompt, structured-output schema, historical source fixture, semantic scorer, gold expectations, acceptance threshold, provider selection state, production wiring, or migration blockers. It performs no provider API call and does not retry any frozen provider/model route.

## Trigger

Gemini 3.5 Flash V4 qualified 3/4 in run `33141373191`. The only failed case, `run413-bok-kbs-rate-decision`, was persisted as:

`adapter_contract:event_draft_contract`

The historical qualification artifact did not persist the underlying `ContractError` message or provider response. Therefore the exact sub-cause of that historical failure cannot be reconstructed without a forbidden provider rerun.

## Root cause of the observability gap

V4 structured output accepts fields such as `event_time`, `participants`, `metric`, `value`, and `uncertainty_reasons` as ordinary JSON strings/arrays. `CanonicalEventDraft` then enforces additional deterministic cross-field and structural invariants. Before this audit, every `ContractError` raised while constructing a draft was wrapped as the single failure code `event_draft_contract`, and the V4 qualification runner persisted only that coarse code.

The result was diagnostic compression: structurally different failures were indistinguishable in the persisted qualification report.

## Provider-output-reachable `event_draft_contract` sub-causes

The audit identifies the following bounded sub-causes that can be reached from a schema-conforming V4 provider response before semantic scoring:

- `duplicate_evidence_refs`
- `duplicate_participants`
- `duplicate_event_uncertainty_reasons`
- `event_time_format`
- `event_time_timezone`
- `value_requires_metric`
- `metric_requires_value`
- `resolved_event_with_uncertainty`
- `unresolved_event_without_uncertainty`

Article-level deterministic invariants are also assigned bounded diagnostic codes, including resolved/unresolved uncertainty consistency and required primary-event structure.

These codes describe deterministic contract failures only. They do not expose source text, provider payloads, prompts, generated content, or exception text in qualification reports.

## Implementation rule

The primary failure classification is unchanged. A future V4 failure remains, for example:

`adapter_contract:event_draft_contract`

and may now carry an additional bounded detail such as:

`adapter_detail:value_requires_metric`

Historical V3 reporting remains generic and unchanged. The V4 qualification outcome classifier is unchanged, so a detailed failure is still a non-pass. No old provider result is retroactively converted to PASS or assigned a guessed sub-cause.

## Historical interpretation

Gemini 3.6 Flash's 3/4 failure remains a genuine scorer-level semantic-structure failure because its persisted failures were `event_drafts_min`, `expected_event_match`, and `parent_hint_min` after the adapter completed successfully.

Gemini 3.5 Flash's 3/4 failure is narrower but unresolved at the sub-cause level: the evidence proves a deterministic `CanonicalEventDraft` contract rejection, but the old report cannot distinguish among the provider-output-reachable sub-causes listed above. It must not be relabeled as a specific semantic failure without new evidence, and the exact frozen route must not be retried merely to recover missing diagnostics.

## Acceptance impact

None. V4 remains 4/4-only. Provider selection remains blocked until an active V4 provider reaches `MINIMUM_COMPATIBILITY_PASS`. The three migration blockers remain active. No fresh live, deploy, Push, or merge is authorized by this audit.
