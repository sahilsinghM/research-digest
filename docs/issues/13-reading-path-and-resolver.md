---
title: Reading path file, verification and edges
type: AFK
label: ready-for-agent
status: done
---

# Reading path file, verification and edges

## Parent

`docs/prd/2026-10-15-daily-10-foundations-prd.md`

## What to build

Replace the hard-coded landmark with a human-editable reading-path file (first path: finance, about fifteen landmark works ordered by what must be understood first). A resolver finds each work in the citation data by title, authors and year, accepts it only on a confident match, prefers the original over reprints and book-chapter copies, flags anything uncertain for the reader, and caches results. Built-on and led-to links are computed from real data and restricted to on-topic works. A step advances only after it was delivered; an unresolvable or unwritable step is skipped with a note and retried tomorrow.

## Acceptance criteria

- [x] The path file loads, and a malformed or empty file produces a clear error, not a crash mid-run
- [x] A confident match is accepted; an ambiguous or mismatched one is flagged in the run output and not used
- [x] Reprints and chapter copies of the same paper collapse into the original; the path has no duplicates
- [x] Off-topic highly cited works are dropped from built-on/led-to; shown counts come from data
- [x] Cached steps need no outside call on later days
- [x] Progress advances only after a delivered message; a failed send leaves the step to retry
- [x] Full test suite passes

## Blocked by

- `docs/issues/12-*.md`

## Result
Live check (2026-10-15): all 15 landmark papers verified against OpenAlex (0 flagged) in 42 s; a second load made 0 outside calls. Built-on/led-to links are sensible (e.g. Black-Scholes built on Sharpe 1964, the 1968 random-walk paper and 1972 portfolio theory; led to Merton 1976, Cox-Ross-Rubinstein 1979, Heston 1993). Limit of the data: OpenAlex splits Markowitz 1952 across records, so its largest shows 5,641 citations; the card should say the count is OpenAlex's (issue 16). Several classics (Markowitz, Fama, CRR, Merton 1976, Bollerslev) have no abstract in the data, so they will carry the background-knowledge label.
