# Insight Desk Push Worker

This Worker is an optional delivery signal for the GitHub Pages briefing. It
sends one application-controlled message:

- `READY`: 오늘 브리핑 준비 완료

Safe abstention and operational failures stay in GitHub Actions and never
become end-user notifications.

It does not collect user profiles. `PUSH_SUBSCRIPTIONS` stores only normalized
browser subscription endpoint/key data plus short-lived delivery idempotency
markers. `POST /send` requires `Authorization: Bearer ...` and is never a
public endpoint.

## Configuration

The existing Cloudflare KV namespace must be bound as
`PUSH_SUBSCRIPTIONS`. Set the public `VAPID_PUBLIC_KEY` variable in the
Worker dashboard. Store only these private values as Cloudflare secrets:

- `VAPID_PRIVATE_KEY`
- `PUSH_SEND_TOKEN`

`VAPID_SUBJECT` is a non-secret HTTPS subject configured in `wrangler.jsonc`.
The namespace ID is intentionally a manual placeholder until the existing
`insight-desk-push` namespace is selected.

## Endpoints

- `GET /health`
- `GET /vapid-public-key`
- `POST /subscribe`
- `DELETE /subscribe`
- authenticated `POST /send`

Only the Pages origin is allowed for browser CORS. `POST /send` accepts only a
READY payload bound to an exact `briefing_id` and publication SHA-256 through
the deployed publication gateway. No scheduled Worker handler or cron trigger
exists. Main-branch Worker changes deploy through the dedicated workflow,
which also synchronizes the empty trigger set and verifies the public health
contract.
