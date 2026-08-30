# Post-merge Event Understanding Provider Qualification V6

## Decision

**No provider is selected. Production keeps the existing compatibility Event Understanding owner.**

This is a successful qualification outcome: the production gate requires a candidate to prove that it is non-regressive before wiring. The frozen shortlist did not produce such a candidate, so no semantic provider is promoted and production wiring remains unchanged.

## Scope

Protocol V6 is post-merge qualification only. It does not reopen PR #84 architecture and does not add article-specific detectors, regex rules, blacklists, or provider-specific semantic exceptions.

The benchmark preserves the four V5 historical exact-source cases and adds seven frozen post-merge regression cases for prior P1/centrality/background failure classes. Automatic scoring is structural and evidence-bound; subtle free-form semantic fidelity is reserved for human review rather than converted into lexical rules.

## Frozen run

- Branch: `postmerge-event-understanding-provider-qualification`
- Qualification head: `14bea1d29af283a476cab38e35e6f67c5e102536`
- V6 workflow run: `33311240112`
- V6 contract job: SUCCESS
- Qualification set: 11 cases
- Automatic pass alone cannot select or wire a provider.

### Cerebras GLM 4.7

- Candidate: `cerebras_glm_47`
- Model: `zai-glm-4.7`
- Outcome: `QUALIFICATION_BLOCKED_PROVIDER_UNAVAILABLE`
- Passed: 0 / 11
- Failure: all 11 cases returned `provider_transport:invalid_output` with HTTP 404.
- Artifact: `9732041762`

Interpretation: this is a provider/model route availability failure, not a semantic-quality judgment.

### Groq 120B

- Candidate: `groq_120b`
- Model: `openai/gpt-oss-120b`
- Outcome: `NOT_QUALIFIED`
- Passed: 2 / 11
- Artifact: `9732045682`

The candidate failed semantic/contract cases before rate limiting began:

- rate-decision case: wrong status / no required primary-direct event / expected-event mismatch
- outlook-child case: insufficient event drafts / expected-event mismatch / missing parent hints
- K-pop actor-preservation case: expected-event mismatch

It later encountered rate limits, but the pre-rate-limit semantic failures are sufficient to prevent classifying the run as merely transiently blocked.

### Cohere Command A+

- Candidate: `cohere_command_a_plus`
- Model: `command-a-plus-05-2026`
- Outcome: `NOT_QUALIFIED`
- Passed: 0 / 11
- Artifact: `9732137305`

Observed failures:

- one `provider_transport:transient_provider`
- ten `adapter_contract:adapter_output_contract`

The run also had materially worse operational latency than the other shortlisted candidates. No case reached an automatic pass and the mandatory PSAT human-review case had no valid draft to review.

## Compatibility-owner baseline

The current compatibility owner remains the baseline rather than being replaced by an unqualified model. On the same qualification head, normal repository validation remained green:

- Infrastructure CI run `33311240117`: SUCCESS
- historical production replay: SUCCESS
- Phase 6 correctness and recall gate: SUCCESS

The seven post-merge V6 regression semantics are frozen from the compatibility-owner regression classes that currently protect primary-vs-context/background behavior. The external candidates failed to establish a non-regressive replacement under the stricter V6 contract.

## Production gate result

The following remain intentionally unchanged:

- selected Event Understanding provider: **none**
- production provider wiring: **false / unchanged**
- Identity ownership: unchanged
- Generation ownership: unchanged
- Verification ownership: unchanged
- Publication ownership: unchanged

No fresh canary is justified because no candidate passed the automatic qualification gate. A canary is downstream of provider qualification, not a mechanism for rescuing an unqualified candidate.

## Closure

Issue #85 is resolved as **no qualified winner**. Further provider search should be a new, explicitly bounded evaluation only when a materially different candidate or provider contract becomes available. Do not continue a prompt-tuning or provider-hunting loop from this result.
