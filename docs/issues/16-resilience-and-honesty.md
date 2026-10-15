---
title: Citation service failures and honest labelling
type: AFK
label: ready-for-agent
status: done
---

# Citation service failures and honest labelling

## Parent

`docs/prd/2026-10-15-daily-10-foundations-prd.md`

## What to build

Make a bad day harmless and make the card honest. If the citation service is down and the step is not cached, deliver the recall cards and a note, and retry the step tomorrow without losing the place. Rate-limit politely. Make every number about years and citations visibly data, and every explanation from background visibly labelled. A model reply that tries to state citation numbers is ignored for those fields.

## Acceptance criteria

- [x] Citation service down: recall cards and a note are delivered, the step is retried the next day
- [x] Rate-limit or timeout responses are retried with backoff and then reported, never crashing the run
- [x] Citation numbers in the message come only from data even if the model's reply includes its own
- [x] Background-knowledge labelling appears whenever the abstract is missing
- [x] The failure appears in the digest header like other source failures
- [x] Full test suite passes

## Blocked by

- `docs/issues/12-*.md`
- `docs/issues/13-*.md`
- `docs/issues/14-*.md`
