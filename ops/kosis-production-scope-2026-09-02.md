# KOSIS production scope decision — 2026-09-02

## Decision

KOSIS authoritative enrichment is disabled in the current production scope. The client, credential support, CPI dataset definition, bounded retry behavior, and request-contract tests remain in the repository so the route can be revalidated and re-enabled later without semantic redesign.

## Evidence

- Exact production-preflight run 791 (`33525890768`) failed only on KOSIS; safe diagnosis: `URLError_TIMEOUT` after the bounded transport budget. NAVER, Bing, OpenDART, and push Worker health passed.
- The KOSIS request was aligned with the current documented parameter contract by removing the legacy `jsonVD` parameter. Infrastructure CI and historical production replay passed after that change.
- Exact production-preflight run 794 (`33526849472`) still failed only on KOSIS with `URLError_TIMEOUT`. Therefore the legacy parameter was not the root cause.
- Accepted fresh canary run `33326060814` had KOSIS configured and enabled but recorded `matched_events=0`, `calls=0`, `success=0`, and `facts=0`. KOSIS did not contribute to the P0/P1=0 accepted briefing.
- Scheduled production run `33458353377` likewise recorded KOSIS `matched_events=0`, `calls=0`, and `facts=0`.
- Authoritative enrichment is post-CanonicalEvent, item-local, and fail-soft; provider failure is not semantic evidence and does not delete or rewrite the event.

## Invariants preserved

- The strict live audit is not weakened. Active configured operational routes must still pass their bounded probes.
- KOSIS is reported as `DISABLED`, not falsely reported as healthy or unconfigured.
- No semantic threshold, source-grounding rule, publication gate, or human-acceptance requirement is relaxed.
- Re-enabling KOSIS requires a fresh bounded live validation from the actual production execution environment before it can re-enter the operational route set.
