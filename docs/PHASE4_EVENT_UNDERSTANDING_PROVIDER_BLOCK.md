# PHASE 4 — Event Understanding Provider Block

Status: `NO_ELIGIBLE_EXISTING_PROVIDER`

Exact architecture freeze head before this inventory closure: `e92b59787337db4cb3dd8b1537feeb5494ce37ab`.

## Qualification results already frozen

- Groq GPT-OSS 20B (`openai/gpt-oss-20b`): `NOT_QUALIFIED`, valid run `33026646693`, 0/4 passed.
- Gemini Flash Lite (`gemini-3.1-flash-lite`): `NOT_QUALIFIED`, valid run `33026927524`, 0/4 passed.
- Groq GPT-OSS 120B: `EXCLUDED`; its temporal auxiliary role remains frozen.

Neither failed candidate is eligible for a retry or prompt-tuning loop under the frozen qualification contract.

## Existing provider inventory

The repository contains no remaining provider that can be assigned Event Understanding without violating an existing responsibility boundary:

- Groq 20B — generation responsibility; additionally failed Event Understanding qualification.
- Gemini Flash Lite — verification failover responsibility; additionally failed Event Understanding qualification.
- Cloudflare Llama 3.3 70B — primary external verification responsibility.
- Local mDeBERTa NLI — secondary verification responsibility and entailment classifier, not a generative Event Understanding owner.
- Groq 120B — temporal auxiliary responsibility, explicitly excluded from reassignment.

Therefore no current provider may be silently reused as Event Understanding.

## Binding consequence

`config/event_understanding_provider_status_v2.json` now declares:

```text
provider_inventory_status = NO_ELIGIBLE_EXISTING_PROVIDER
selected_event_understanding_provider = null
production_wired = false
```

The mechanical selector rejects all of the following:

- selecting a `NOT_QUALIFIED` provider,
- selecting an `EXCLUDED` provider,
- selecting any provider while inventory status is `NO_ELIGIBLE_EXISTING_PROVIDER`,
- setting `production_wired=true` without a selected qualified provider.

A later dedicated candidate must first obtain `MINIMUM_COMPATIBILITY_PASS` under a separately authorized qualification and then move the inventory status to `ELIGIBLE_CANDIDATE_AVAILABLE`. Only after both conditions are true may production Event Understanding wiring begin.

No production marker, fresh news canary, deploy, or Push is authorized by this provider-block closure.
