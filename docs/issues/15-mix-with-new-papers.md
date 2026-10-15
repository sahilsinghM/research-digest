---
title: Daily 10 first; new papers only when excellent
type: AFK
label: ready-for-agent
status: done
---

# Daily 10 first; new papers only when excellent

## Parent

`docs/prd/2026-10-15-daily-10-foundations-prd.md`

## What to build

Make the Daily 10 the first and main item of each day. New papers are triaged as today but must clear a much higher minimum score, at most one a day, and appear as an optional bonus after the Daily 10. The old idea-of-the-day message is retired. The header lists today's items. Configuration for the new bar and maximum is added.

## Acceptance criteria

- [x] The Daily 10 is always the first message when the path has a next step
- [x] A new paper below the new bar is never sent; at most one above it is sent as a bonus
- [x] With no new paper and no path step left, the quiet-day message still appears
- [x] The idea-of-the-day step no longer runs
- [x] Usage-limit and failure notices still work and still do not advance unsent items
- [x] Full test suite passes

## Blocked by

- `docs/issues/12-*.md`
