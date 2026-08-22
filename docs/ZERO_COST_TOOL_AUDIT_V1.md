# Insight Desk — Zero-Cost Tool Audit V1

Status: `PHASE6_ZERO_COST_TOOL_AUDIT`
Date: 2026-08-23

## Non-negotiable boundary

Insight Desk operating cost remains ₩0. A tool is not accepted merely because it has a free tier. Core or required workflows may not depend on a subscription, billing account, automatic paid fallback, larger paid GitHub runner, or hosted annotation product.

## Accepted local semantic helpers

### kiwipiepy 0.23.2

- License: LGPL-3.0
- Execution: local Python package
- API key/account: none
- Network inference: none
- Role: Korean morphology and exact source-offset scaffold only
- Forbidden roles: NER truth, fact truth, event identity, material-event truth, selection, publication verification
- Canary: workflow `32598931598`, job `97094126726` — PASS
- Important observed limitation: `곽빈` was split rather than preserved as one proper-noun token. The exact source surface remained covered by valid offsets, so Kiwi is useful as a scaffold but is explicitly not a named-entity authority.

### RapidFuzz 3.14.5

- License: MIT
- Execution: local Python package
- API key/account: none
- Network inference: none
- Role: alias/string candidate retrieval only
- Forbidden roles: same-entity final decision, same-event final decision, fact truth, material-event truth
- Canary: workflow `32598931598`, job `97094126726` — PASS

## Accepted human annotation tool

### Label Studio OSS

- License: Apache-2.0
- Deployment: local self-hosted OSS only
- Runtime dependency: no
- Required cloud account: no
- Hosted Starter Cloud / Enterprise: not part of Insight Desk
- Purpose: create independent human gold for the two unresolved Phase 6 areas:
  1. material-event truth
  2. fact-span extraction

The two annotation tasks remain separate so material-event judgment does not contaminate fact-span extraction.

## Rejected

### dateparser 1.4.1

The package is free/open source, but zero monetary cost is not sufficient for adoption. It failed the locked Korean-news runtime canary:

- `2026년 9월 3일` → failed
- `9월 3일` → failed
- `오는 27일` → failed
- `지난 12일` → failed

Decision: do not add it to production. Korean date normalization should remain deterministic project code unless a later independently validated tool clearly improves it.

### GLiNER-ko

Rejected for the long-lived production core because the model is CC BY-NC 4.0 and introduces unnecessary license restrictions for this project. It is not needed to proceed.

## Held / deferred

### Stanza Korean dependency models

The Stanza library code is permissive, but model/data licensing depends on underlying UD resources and requires per-pack provenance review. Do not add it merely to gain another parser.

### SetFit

Library is suitable for later evaluation, but only after independent human material-event gold exists and the chosen base model has a separately audited permissive license.

### Evidently OSS

Potential Phase 9-12 monitoring tool. It is not needed to close current Phase 6 semantic blockers.

## GitHub Actions cost boundary

This repository is public. Only standard GitHub-hosted runners are permitted for these checks. Larger runners are forbidden by the project audit. The semantic-local CI is path-scoped so the relatively large Kiwi model is not downloaded for unrelated changes.

## Result

Current additions are intentionally small:

- Kiwi: morphology/source offsets
- RapidFuzz: alias candidate retrieval
- Label Studio OSS: human gold creation, offline from runtime

No new LLM/API role is added. No paid recovery path is added. No tool score is allowed to become semantic truth by itself.
