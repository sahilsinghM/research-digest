---
title: Daily 10 tracer: one real step end to end
type: AFK
label: ready-for-agent
status: done
---

# Daily 10 tracer: one real step end to end

## Parent

`docs/prd/2026-10-15-daily-10-foundations-prd.md`

## What to build

Prove the whole path once with a single hard-coded landmark (the 1973 option-pricing paper). Look the paper up in the citation service for real (title, year, citation count, abstract if any, open-access link, a few built-on and led-to titles), have the model write the lesson (headline, up to two pre-read terms, the idea in at most five short lines, one thing to look for in the original, a one-sentence prompt, and one recall question with its answer), and print the formatted Daily 10 message in a dry run. No path file, progress, spaced recall or new-paper mixing yet. The citation client and the lesson writer take injected fakes so tests never touch the internet or the real model.

## Acceptance criteria

- [x] `agent.py --dry-run` prints a Daily 10 message for the one hard-coded landmark using the real citation service and the real model
- [x] Years, citation count and built-on/led-to titles in the message come only from the citation data (a test fails if the model's text is used for them)
- [x] A missing abstract makes the card say the explanation is background knowledge, not from the paper's text
- [x] The message is escaped, uses a spoiler for the hidden answer, stays under the Telegram size limit, and never cuts inside a tag
- [x] Tests use recorded fixture shapes from the 2026-10-15 spike and a fake model; nothing automated calls the internet
- [x] Full test suite passes

## Blocked by

None - can start immediately

## Result
Live check (2026-10-15): real OpenAlex + real model produced a ~2,000-character Daily 10 for Black-Scholes; citation count 28,883 came from data. Known flaws handed to issue 13: a 2005 reprint listed under 'built on', an off-topic paper under 'led to', ALL-CAPS titles.
