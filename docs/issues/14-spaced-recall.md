---
title: Spaced recall cards
type: AFK
label: ready-for-agent
status: done
---

# Spaced recall cards

## Parent

`docs/prd/2026-10-15-daily-10-foundations-prd.md`

## What to build

Store each lesson's recall question and answer. Each day show the cards that are 1, 3, 7 and 21 days old, at most two, with the answer hidden behind a spoiler. Fixed schedule, no adaptive scheduling. Nothing is due on day one.

## Acceptance criteria

- [x] A card appears exactly 1, 3, 7 and 21 days after it was created, and not on other days
- [x] At most two recall cards appear in a day; overflow waits for the next day without being lost
- [x] A card is shown once per due date even if the run is repeated the same day
- [x] The answer is hidden with spoiler formatting and the question reads fine without the answer
- [x] A dry run neither creates nor advances cards
- [x] Full test suite passes

## Blocked by

- `docs/issues/12-*.md`
