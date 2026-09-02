# KOSIS production scope decision — 2026-09-02

## Current decision

KOSIS authoritative enrichment is active again in the current production scope and is subject to the original fail-closed marked-preflight rule. The earlier temporary disablement described below is superseded and is retained only as incident history.

The live probe remains bounded to one latest CPI period. The marked preflight uses KOSIS `outputFields` with the compact identity/value field shape used by current URL-generator examples (`ORG_ID`, `TBL_ID`, `TBL_NM`, `ITM_ID`, `ITM_NM`, `UNIT_NM`, `PRD_SE`, `PRD_DE`, `DT`). Normal production enrichment does not inherit that probe-only field restriction and retains the complete provider response contract.

KOSIS's compact developer-guide request table does not currently list `jsonVD`, but KOSIS URL-generator/Q&A examples from 2024–2025 still emit `format=json&jsonVD=Y` for `statisticsParameterData.do`. The client therefore follows the generated JSON request contract and sends `jsonVD=Y`; this is an evidence-driven compatibility correction, not a relaxation of the live gate.

## Incident history and evidence

- Exact production-preflight run 791 (`33525890768`) failed only on KOSIS; safe diagnosis: `URLError_TIMEOUT` after the bounded transport budget. NAVER, Bing, OpenDART, and push Worker health passed.
- Removing `jsonVD` based only on the compact request-variable table did not resolve the problem. Exact production-preflight run 794 (`33526849472`) still failed only on KOSIS with `URLError_TIMEOUT`.
- KOSIS was then temporarily disabled while the route was non-operational. That scope reduction did not change semantic authority, but it is not the final acceptance state for this PR.
- After fail-closed reactivation, exact production-preflight run 816 (`33590211292`) used only `PRD_DE` and `DT` as probe output fields. The request returned quickly instead of exhausting the transport timeout, but KOSIS alone failed with safe `error_kind=ValueError`, consistent with a non-JSON response reaching the JSON decoder. Production was correctly skipped.
- Current KOSIS examples show richer generated `outputFields` selections and continue to include `jsonVD=Y`; the next probe aligns to that generated request shape.
- Accepted fresh canary run `33326060814` had previously recorded KOSIS `matched_events=0`, `calls=0`, `success=0`, and `facts=0`; scheduled production run `33458353377` likewise recorded zero KOSIS event matches. Those observations explain why the temporary disablement did not alter those particular briefings, but they do not prove the integration healthy.

## Invariants preserved

- Active configured operational routes must pass their bounded live probes. KOSIS is not exempted by being marked disabled.
- A KOSIS timeout, invalid response, or provider failure remains a marked-preflight failure; it is not reclassified as healthy, unconfigured, or non-blocking.
- Retry count and timeout budget are unchanged.
- No semantic threshold, source-grounding rule, publication gate, or human-acceptance requirement is relaxed.
- `outputFields` is used only to minimize the marked probe response shape; it does not change the production enrichment field contract.
