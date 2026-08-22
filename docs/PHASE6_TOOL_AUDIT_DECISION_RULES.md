# Phase 6 tool-audit acceptance rules

A new tool is accepted only if all are true:

1. KRW 0 operating path; no paid fallback or required subscription.
2. No routine user action or annotation is required for production operation.
3. License is compatible with long-lived production use.
4. The tool fills a capability not already provided by the current deterministic core/Kiwi/RapidFuzz.
5. Its authority is narrower than event truth; ambiguity fails safe.
6. Locked positive/negative regressions do not degrade.
7. The tool does not move Phase 7 generation/verification into Phase 6.

Reject a candidate if it only duplicates an existing helper, requires repurposing selection labels as material-event truth, or adds a large ML dependency without measurable semantic gain.
