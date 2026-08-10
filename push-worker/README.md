# Insight Desk Push Worker

This Worker is an optional delivery signal for the GitHub Pages briefing. It
sends only two application-controlled messages:

- `READY`: 오늘 브리핑 준비 완료
- `FAILURE`: 오늘 브리핑 업데이트 실패 / 마지막 정상본 유지

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

Only the Pages origin is allowed for browser CORS. The cron watchdog runs at
00:00 UTC (09:00 KST) and emits a failure signal only when that day's ready
marker is absent. The Pages workflow trigger is added only after the Worker is
deployed and its public URL and send token are configured.
