---
title: Claude runner hardening
type: AFK
label: ready-for-agent
status: done
---

# Claude runner hardening

## Parent

`docs/prd/2026-10-13-research-digest-prd.md`

## What to build

Make the runner safe to leave unattended on a subscription. It must guarantee the subscription is used and never an API key, give the model no ability to act, and stop cleanly when the subscription limit is hit. Details are in the PRD's Claude runner section. Tested with a fake `claude` executable first on the path so the real subprocess code runs.

## Acceptance criteria

- [x] API-key and auth-token variables are removed from the child environment even when set in the parent (test asserts the child never sees them)
- [x] Every call runs with all tools disabled, no MCP servers, an empty working directory, a dedicated throwaway config directory, no session persistence, one turn, JSON output, and a timeout (test asserts the flags and environment the fake executable received)
- [x] A hang is cut off by the timeout and reported as an error
- [x] Non-zero exit or a result containing the session-limit or weekly-limit phrase raises a dedicated usage-limit error; other failures raise a distinct runner error
- [x] A login self-check using the auth status command runs at start and fails fast with a readable message when not logged in
- [x] Calls are serial; the bare mode is never used
- [x] Full test suite passes

## Blocked by

- `docs/issues/01-*.md`
