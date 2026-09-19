# Schedule Reliability V1

## Goal

For automated scheduled publication, publish no earlier than 07:30 Asia/Seoul, dispatch the first
eligible daily production as close to that target as GitHub permits, and prevent later redundant
triggers from producing a second briefing or notification on the same Korea-calendar date. Explicit
manual and main-push runs remain operator-controlled paths outside this scheduler rule.

## Platform constraint

GitHub documents that `schedule` events can be delayed under high load and that queued jobs may be
dropped. A single cron expression therefore cannot prove exact-time delivery. The production design
keeps GitHub Actions as the scheduler but removes the former single-trigger dependency.

Official reference:
https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule

## Runtime design

1. `.github/workflows/insight-desk-scheduler.yml` runs lightweight probes before 07:30 at offsets
   chosen to cover the observed 95–171 minute queue delay, plus an exact 07:30 trigger and an 08:17
   fallback.
2. `scripts/schedule_publication_gate.py` reads the exact `data-briefing-id` from the deployed Pages
   document. It permits dispatch only at or after 07:30 and only when that identity belongs to an
   earlier local date.
3. Before dispatch, the scheduler checks for a queued or running production workflow. Scheduler runs
   are serialized so two probes cannot dispatch concurrently.
4. The production workflow repeats the same date/time gate for scheduler-originated dispatches and
   for its independent 08:17 fallback. This is the second duplicate boundary.
5. Main production runs queue instead of cancelling one another. A later fallback can therefore not
   starve a valid build by repeatedly cancelling it.
6. Pages-state network or contract ambiguity fails closed for that probe. The next redundant trigger
   retries without risking a duplicate publication.

## Acceptance evidence

Static and deterministic tests prove the not-before rule, same-day duplicate suppression, invalid or
future deployment rejection, workflow dispatch permissions, serialized concurrency, and the
independent fallback. Final timing acceptance still requires a real default-branch scheduled run;
manual runs and PR preflights cannot prove GitHub's scheduler behavior.
