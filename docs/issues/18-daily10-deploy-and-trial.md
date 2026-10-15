---
title: Deploy the Daily 10 and run a trial
type: HITL
label: ready-for-agent
status: in-progress
---

# Deploy the Daily 10 and run a trial

## Parent

`docs/prd/2026-10-15-daily-10-foundations-prd.md`

## What to build

Deploy to the VPS with the safe deploy command, run a dry run there, then let the 07:00 IST run deliver the first Daily 10. The reader uses it for at least a week and says what is too long, too hard or not useful; tune accordingly.

## Acceptance criteria

- [ ] Deployed with correct ownership and permissions; dry run on the VPS prints a Daily 10
- [ ] The scheduled run delivers a Daily 10 in Telegram and the ten-minute budget feels right to the reader
- [ ] At least one week of feedback applied (length, difficulty, recall cadence)
- [ ] The changelog and CLAUDE.md describe the new track

## Blocked by

- `docs/issues/14-*.md`
- `docs/issues/15-*.md`
- `docs/issues/16-*.md`
- `docs/issues/17-*.md`
