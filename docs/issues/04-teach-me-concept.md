---
title: Teach-me concept and top item
type: AFK
label: ready-for-agent
status: open
---

# Teach-me concept and top item

## Parent

`docs/prd/2026-10-13-research-digest-prd.md`

## What to build

After the papers, one extra message teaches a single underlying concept the day's papers assume, in plain language with a worked example tied to the reader's profile. The header also names the single most important item of the day. Failure to produce a concept never blocks the rest of the digest.

## Acceptance criteria

- [ ] A teach-me message with name, explanation and example is produced from the day's analyses and the profile
- [ ] Model and source text in the message is HTML-escaped and clipped to fit the size limit
- [ ] If the concept call fails or is unparseable, the digest is still delivered without it
- [ ] The header names the highest-scoring paper as most important
- [ ] Full test suite passes

## Blocked by

- `docs/issues/01-*.md`
