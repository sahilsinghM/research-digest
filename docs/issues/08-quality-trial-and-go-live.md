---
title: Quality trial, then go live
type: HITL
label: ready-for-agent
status: in-progress
---

# Quality trial, then go live

## Parent

`docs/prd/2026-10-13-research-digest-prd.md`

## What to build

The owner reads real dry-run digests for several days and says what is wrong; prompts, thresholds, quotas and keyword lists are tuned. When the owner is satisfied: run once for real and confirm messages arrive and render, re-run immediately and confirm nothing is sent twice, add the 01:30 UTC cron entry (07:00 IST; the VPS is on UTC), and set up log rotation. Confirm the next morning's scheduled run from the log.

## Acceptance criteria

- [ ] At least 3 different days of dry-run digests were reviewed and feedback applied
- [x] A real send was made on the VPS (2026-10-14, exit 0, 2 papers + concept); the idempotence re-check (dry run on real state) re-sent neither paper. OWNER TO CONFIRM: it arrived and rendered correctly on the phone.
- [ ] Cron entry is installed (01:30 UTC) and verified in a bare cron-like environment; PENDING: confirm the first scheduled run (2026-10-15 07:00 IST) in agent.log
- [x] Log rotation is configured (/etc/logrotate.d/research-digest, weekly, 4 kept)
- [ ] Quotas and cap are reviewed (they currently sum to 7 while the cap is 8)

## Blocked by

- `docs/issues/03-*.md`
- `docs/issues/04-*.md`
- `docs/issues/07-*.md`
