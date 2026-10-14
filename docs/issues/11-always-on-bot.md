---
title: Long-running Telegram bot with buttons
type: HITL
label: parked
status: parked
---

# Long-running Telegram bot with buttons

## What to build

Today the agent is a once-a-day cron job, so Telegram messages cannot react to taps. A future always-on service
would add inline buttons on each card ("explain simpler", "go deeper", thumbs up/down that feed the ranking) and
let the owner ask a question about a paper and get an answer. It needs a process that stays up (a service, not
cron), its own state for feedback, and the same safety rules as the digest (subscription only, model with no
tools, untrusted text as data, only the owner's chat id may talk to it). Out of scope of the PRD for v1; parked
until the owner has used the digest for a while.

## Acceptance criteria

- [ ] Design agreed with the owner (which buttons, how feedback changes ranking, how questions are answered)
- [ ] Service survives restarts and only answers the owner's chat
- [ ] Feedback visibly changes later digests

## Blocked by

- Owner's go-ahead after living with the daily digest
