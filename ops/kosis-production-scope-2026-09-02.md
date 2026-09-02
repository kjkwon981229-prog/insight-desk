# KOSIS production scope decision — 2026-09-02

## Current decision

KOSIS authoritative enrichment is active again in the current production scope and is subject to the original fail-closed marked-preflight rule. The earlier temporary disablement described below is superseded and is retained only as incident history.

The live probe remains bounded to one latest CPI period. To distinguish provider-side response cost from transport reachability without weakening the route, the marked preflight additionally requests only the documented `PRD_DE` and `DT` response fields through KOSIS `outputFields`. Normal production enrichment does not inherit that probe-only field restriction and retains the complete provider response contract.

## Incident history and evidence

- Exact production-preflight run 791 (`33525890768`) failed only on KOSIS; safe diagnosis: `URLError_TIMEOUT` after the bounded transport budget. NAVER, Bing, OpenDART, and push Worker health passed.
- The KOSIS request was aligned with the current documented parameter contract by removing the legacy `jsonVD` parameter. Infrastructure CI and historical production replay passed after that change.
- Exact production-preflight run 794 (`33526849472`) still failed only on KOSIS with `URLError_TIMEOUT`. Therefore the legacy parameter was not the root cause.
- KOSIS was then temporarily disabled while the route was non-operational. That scope reduction did not change semantic authority, but it is not the final acceptance state for this PR.
- Accepted fresh canary run `33326060814` had previously recorded KOSIS `matched_events=0`, `calls=0`, `success=0`, and `facts=0`; scheduled production run `33458353377` likewise recorded zero KOSIS event matches. Those observations explain why the temporary disablement did not alter those particular briefings, but they do not prove the integration healthy.

## Invariants preserved

- Active configured operational routes must pass their bounded live probes. KOSIS is no longer exempted by being marked disabled.
- A KOSIS timeout or provider failure remains a marked-preflight failure; it is not reclassified as healthy, unconfigured, or non-blocking.
- Retry count and timeout budget are unchanged.
- No semantic threshold, source-grounding rule, publication gate, or human-acceptance requirement is relaxed.
- `outputFields` is used only to minimize the marked probe response shape; it does not change the production enrichment data contract.
