---
title: VPS deployment and first dry run
type: HITL
label: ready-for-agent
status: partly-done
---

# VPS deployment and first dry run

## Parent

`docs/prd/2026-10-13-research-digest-prd.md`

## What to build

Deploy to the VPS safely. Human steps (secrets never pass through the development session): the owner creates the Claude token with the setup-token command, the Telegram bot via BotFather, and writes the profile file, all on the VPS. Agent steps, shown to the owner before running: create a dedicated low-privilege user, install Claude Code and Python venv support if missing, rsync the code over SSH, set file permissions on the secrets, run the login self-check, and run a dry run on the server. Also observe and record what a real usage-limit stop looks like (exit code and output) and tighten the runner's detection to match.

## Acceptance criteria

- [ ] A dedicated non-root user owns the deploy directory (NOT DONE by decision: Claude is logged in only as root via a credentials file; copying it would duplicate an OAuth refresh token and could break the other apps on the VPS. Deployed as root with folder 700 and secrets 600. Revisit with `claude setup-token` for a dedicated user.)
- [x] The login self-check passes on the VPS (max plan, claude.ai login; no API key variables set there). The bogus-key-is-ignored proof was done on the dev machine.
- [x] `agent.py --dry-run` completes on the VPS and prints a real digest (2m31s, exit 0)
- [ ] The real usage-limit behavior is documented and detection adjusted (wording now matched from strings inside the Claude Code program, 13 variants tested; the exit code / JSON of a real hit is still unobserved and is logged to agent.log when it happens)
- [x] No secrets or personal profile content appear in the repository, logs or commit history (.env and profile.md are gitignored, mode 600; Telegram send test OK)

## Blocked by

- `docs/issues/01-*.md`
- `docs/issues/02-*.md`
- `docs/issues/03-*.md`
- `docs/issues/04-*.md`
- `docs/issues/05-*.md`
- `docs/issues/06-*.md`
