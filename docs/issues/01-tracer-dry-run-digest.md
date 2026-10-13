---
title: Tracer bullet: a real dry-run digest
type: AFK
label: ready-for-agent
status: done
---

# Tracer bullet: a real dry-run digest

## Parent

`docs/prd/2026-10-13-research-digest-prd.md`

## What to build

Run the whole path once, thinly, so a real digest exists to judge. The existing sources are fetched (with failed sources noted), already-sent papers are dropped, and a naive selection takes the first few papers per area (no scoring yet). Each selected paper is read in depth by Claude through a basic headless `claude -p` runner (abstract only, small JSON analysis: what was done, found, evidence, for you, action, for the world). A header message and one message per paper are produced, each paper with a peer-reviewed/preprint badge and an abstract-only badge. `agent.py --dry-run` prints the digest and writes no state. The runner takes a model alias, a system prompt and a user message and returns text; callers know nothing about subprocesses. Tests use a fake runner function; nothing automated calls the real Claude.

## Acceptance criteria

- [x] `agent.py --dry-run` prints a header plus one message per selected paper using real fetched papers and the real `claude -p` on this machine
- [x] Each paper message shows title, journal, link, evidence badge, what was found, for you, do, for the world, and evidence line; fields are clipped so one message stays under 4096 characters
- [x] The header names the count per area and lists failed sources when there are any
- [x] Dry run writes nothing to the state store
- [x] Tests use a fake runner and cover: analysis JSON wrapped in code fences or prose still parses, unparseable output twice skips that paper without crashing, empty abstract is handled
- [x] Full test suite passes

## Blocked by

None - can start immediately
