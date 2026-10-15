---
title: Reading path file, verification and edges
type: AFK
label: ready-for-agent
status: open
---

# Reading path file, verification and edges

## Parent

`docs/prd/2026-10-15-daily-10-foundations-prd.md`

## What to build

Replace the hard-coded landmark with a human-editable reading-path file (first path: finance, about fifteen landmark works ordered by what must be understood first). A resolver finds each work in the citation data by title, authors and year, accepts it only on a confident match, prefers the original over reprints and book-chapter copies, flags anything uncertain for the reader, and caches results. Built-on and led-to links are computed from real data and restricted to on-topic works. A step advances only after it was delivered; an unresolvable or unwritable step is skipped with a note and retried tomorrow.

## Acceptance criteria

- [ ] The path file loads, and a malformed or empty file produces a clear error, not a crash mid-run
- [ ] A confident match is accepted; an ambiguous or mismatched one is flagged in the run output and not used
- [ ] Reprints and chapter copies of the same paper collapse into the original; the path has no duplicates
- [ ] Off-topic highly cited works are dropped from built-on/led-to; shown counts come from data
- [ ] Cached steps need no outside call on later days
- [ ] Progress advances only after a delivered message; a failed send leaves the step to retry
- [ ] Full test suite passes

## Blocked by

- `docs/issues/12-*.md`
