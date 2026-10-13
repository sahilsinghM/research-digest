---
title: Recover missing abstracts for Nature, Cell and similar journals
type: AFK
label: ready-for-agent
status: open
---

# Recover missing abstracts for Nature, Cell and similar journals

## Parent

`docs/prd/2026-10-13-research-digest-prd.md`

## What to build

Crossref does not carry abstracts for some publishers, so the minimum-abstract rule silently drops them. Measured over 14 days: Nature 4 of 50 papers have an abstract, Cell 0 of 28, Journal of Financial Economics 0 of 5, Journal of Political Economy 0 of 2 (Science 34/50, PNAS 43/50 and the other finance journals are fine). Science coverage in the digest is starved as a result. Recover abstracts for those journals from a source that has them (PubMed indexes Nature, Cell and Science with abstracts; OpenAlex is the alternative, matched by DOI), so those papers reach triage with real text. The area of a paper must follow its journal (science or finance), not the source it came from. Papers that still have no usable abstract keep being dropped, and the digest header says how many papers were dropped for that reason.

## Acceptance criteria

- [ ] Papers from Nature and Cell (and any other journal configured as abstract-poor in Crossref) arrive with an abstract when the recovery source has one
- [ ] Recovered papers keep the area configured for their journal, not "medical"
- [ ] A paper present in both Crossref and the recovery source appears once (deduplicated by DOI)
- [ ] Failure of the recovery source is reported like any other failed source and does not stop the run
- [ ] Papers still without an abstract are dropped and the header reports how many
- [ ] Measured again over 14 days: the share of Nature and Cell papers reaching triage is stated in the issue when it is closed
- [ ] Full test suite passes

## Blocked by

None - can start immediately
