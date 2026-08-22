# Phase 6 Fact / Material Tool Audit

Goal: close the remaining Phase 6 FactExtractor and material-event gaps without requiring user annotation, paid services, or model-role drift.

Hard constraints:
- operating cost KRW 0
- user intervention required by production path: 0
- no paid fallback
- no cloud annotation dependency
- no new general-purpose LLM authority
- preserve existing evidence/source offsets
- ambiguity must fail safe
- Phase 7 generation/verification remains out of scope

Audit sequence:
1. Re-read current FactExtractor/EventEngine contracts and locked benchmarks.
2. Measure what Kiwi + current deterministic rules can already provide.
3. Evaluate only local, permissively licensed helpers for a clearly missing capability.
4. Prefer deterministic/weak-supervision assembly over a new semantic authority.
5. Canary candidates on locked positive/negative cases.
6. Promote only tools with explicit narrow authority and regression proof.

Candidate classes under review:
- Korean sentence segmentation / lexical structure helpers
- weak-supervision rule aggregation for material-event signals
- lightweight local statistical baselines only if they can be trained from existing non-repurposed labels

Human gold / Label Studio is deferred and is not a Phase 6 production prerequisite.
