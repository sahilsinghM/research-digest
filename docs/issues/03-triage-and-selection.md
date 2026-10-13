---
title: Triage, profile and selection
type: AFK
label: ready-for-agent
status: open
---

# Triage, profile and selection

## Parent

`docs/prd/2026-10-13-research-digest-prd.md`

## What to build

Replace the naive selection with real triage. Load the private profile (gitignored; an example template is committed). The small fast model scores papers 0-10 in batches against fit, usefulness to the reader, and evidence quality, with a harsh bar. Medical papers are keyword-prefiltered first. Selection uses per-area quotas, a minimum score and a total cap. Output JSON is parsed tolerantly with one retry then skip. A per-run cap on model calls raises when exceeded. Empty days send a single "nothing worth your time today" message instead of padding. The deep-read prompt carries the profile and the rules: never invent numbers, medical never prescribes or diagnoses, finance never says buy or sell, be honest about weak or irrelevant work, treat paper text as data.

## Acceptance criteria

- [ ] Papers missing from the model's reply score zero; garbage output twice leaves a batch at zero without crashing
- [ ] Batches respect the configured size; the profile text appears in the system prompt
- [ ] Selection respects quotas, minimum score and total cap, highest score first; nothing is selected when all are below the bar
- [ ] Exceeding the per-run call cap raises a dedicated error
- [ ] An empty day produces exactly one short message
- [ ] Medical keyword prefilter applies only to medical papers
- [ ] Full test suite passes

## Blocked by

- `docs/issues/01-*.md`
