---
title: Idempotent, failure-safe runs
type: AFK
label: ready-for-agent
status: done
---

# Idempotent, failure-safe runs

## Parent

`docs/prd/2026-10-13-research-digest-prd.md`

## What to build

Make unattended runs safe to retry. Each paper is marked sent only after Telegram confirms its message; last-success is recorded last and only when the run completes, so a missed or failed run is caught up next time and sent papers are never resent. The first run looks back two days. A lock file prevents overlapping runs. A crash sends a short failure notice. A usage-limit stop sends a distinct "limit reached" notice, delivers whatever was already complete, and does not advance last-success. Dry run still writes nothing.

## Acceptance criteria

- [x] Happy path marks every sent paper and records last-success once
- [x] A send failure midway leaves earlier papers marked sent, later ones unmarked, and last-success not advanced (test: re-run sends only the remaining papers)
- [x] A usage-limit error during triage or reading sends the limit notice and does not advance last-success; already completed papers are still delivered and marked
- [x] A second concurrent run exits quietly without doing work
- [x] Any unexpected crash sends a failure notice containing the error type and a short message, never secrets
- [x] First run with no history uses the configured two-day lookback; later runs use last-success
- [x] Full test suite passes

## Blocked by

- `docs/issues/02-*.md`
- `docs/issues/05-*.md`
