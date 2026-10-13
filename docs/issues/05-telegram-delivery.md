---
title: Telegram delivery
type: AFK
label: ready-for-agent
status: open
---

# Telegram delivery

## Parent

`docs/prd/2026-10-13-research-digest-prd.md`

## What to build

Send the digest to the owner's Telegram chat only. Messages use HTML formatting with all dynamic text escaped; any message over the 4096-character limit is split at a line break; if Telegram rejects the formatting the same message is resent as plain text; rate limiting (HTTP 429) waits the advised time and retries. Token and chat id come from the environment. Tested with an injected transport; no real network in automated tests.

## Acceptance criteria

- [ ] Messages go only to the configured chat id
- [ ] Titles and model text containing angle brackets, ampersands and quotes are escaped and do not break formatting
- [ ] Text over the limit is split at line breaks (hard split when there are none) and every chunk is within the limit
- [ ] A formatting rejection triggers a plain-text resend of the same content with tags stripped
- [ ] A rate-limit response waits and retries, and gives up with a clear error after a few attempts
- [ ] Error messages never contain the bot token
- [ ] Full test suite passes

## Blocked by

- `docs/issues/01-*.md`
