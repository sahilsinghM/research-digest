---
title: VPS deployment and first dry run
type: HITL
label: ready-for-agent
status: open
---

# VPS deployment and first dry run

## Parent

`docs/prd/2026-10-13-research-digest-prd.md`

## What to build

Deploy to the VPS safely. Human steps (secrets never pass through the development session): the owner creates the Claude token with the setup-token command, the Telegram bot via BotFather, and writes the profile file, all on the VPS. Agent steps, shown to the owner before running: create a dedicated low-privilege user, install Claude Code and Python venv support if missing, rsync the code over SSH, set file permissions on the secrets, run the login self-check, and run a dry run on the server. Also observe and record what a real usage-limit stop looks like (exit code and output) and tighten the runner's detection to match.

## Acceptance criteria

- [ ] A dedicated non-root user owns the deploy directory; secrets files are readable only by that user
- [ ] The login self-check passes on the VPS using the token, and an API key in the environment is shown to be ignored
- [ ] `agent.py --dry-run` completes on the VPS and prints a real digest
- [ ] The real usage-limit behavior is documented in the PRD notes and the detection is adjusted if it differs
- [ ] No secrets or personal profile content appear in the repository, logs or commit history

## Blocked by

- `docs/issues/01-*.md`
- `docs/issues/02-*.md`
- `docs/issues/03-*.md`
- `docs/issues/04-*.md`
- `docs/issues/05-*.md`
- `docs/issues/06-*.md`
