# Research digest

Daily Telegram digest of new papers (finance and economics, sciences, medicine), personalised by a private
`profile.md`. Model work runs on the owner's Claude subscription through headless Claude Code, never an API key.

Design: `docs/prd/2026-10-13-research-digest-prd.md`. Work items: `docs/issues/`.

## Run locally (no Telegram, writes nothing)

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp profile.example.md profile.md        # fill it in; it is gitignored and sent only to your own Claude login
.venv/bin/python agent.py --dry-run     # prints the digest
.venv/bin/pytest -q
```

Needs Claude Code installed and logged in with a subscription (`claude auth status` shows `claude.ai` or `oauth_token`).

## VPS (`/home/digest/research-digest`, runs as the low-privilege `digest` user, UTC clock)

- The `digest` user has no password and no SSH keys. It logs in to Claude with a subscription token:
  run `claude setup-token` on a machine where you are logged in, and put `CLAUDE_CODE_OAUTH_TOKEN=...` in the
  server `.env`. The token lasts about a year; when a run fails with a "not logged in" notice, make a new one.
- `.env` (mode 600): `CLAUDE_CODE_OAUTH_TOKEN=`, `TELEGRAM_BOT_TOKEN=`, `TELEGRAM_CHAT_ID=`. Get the chat id with
  `python3 chat_id.py` after messaging the bot once.
- `profile.md` (mode 600) lives only on the VPS and the dev machine, never in git. Same for `state.db`.
- `claude` is a private copy in `/home/digest/.local/bin` (cron does not have it on its PATH by default).
- Cron (as `digest`), 01:30 UTC = 07:00 IST, logging to `agent.log` (rotated weekly by
  `/etc/logrotate.d/research-digest`):
  ```
  30 1 * * * cd /home/digest/research-digest && PATH=/home/digest/.local/bin:/usr/local/bin:/usr/bin:/bin && export PATH && set -a && . ./.env && set +a && .venv/bin/python agent.py >> /home/digest/research-digest/agent.log 2>&1
  ```
- Deploy (never plain `rsync -a`: it copies this machine's owner and permissions onto the server):
  ```bash
  rsync -rlt --no-perms --no-owner --no-group --chown=digest:digest --chmod=D700,F600 \
    --exclude=.git --exclude=.venv --exclude=.superpowers --exclude=__pycache__ --exclude=.pytest_cache \
    --exclude=state.db --exclude=.lock --exclude=agent.log --exclude=.env --exclude=profile.md \
    ./ root@HOST:/home/digest/research-digest/
  ```
- Pause: `crontab -u digest -e` (as root) and comment the line. A run is safe to repeat: papers already sent are
  never resent.
- Fallback: the old root copy in `/root/research-digest` is no longer scheduled. Delete it once the new setup has
  run well for a few days (it still holds a copy of the Telegram token and profile).

## Tuning (`config.toml`)

`quota` (papers per area), `max_papers`, `min_score` (the bar, 0-10), `min_abstract_chars`, `triage_batch`,
`max_calls_per_run` (hard cap on model calls per run), `keywords.medical`, the arXiv queries, journals, and the
PubMed journal lists.

## Things to know

- The subscription allowance is shared with everything else logged in to that account. If a limit is hit, the run
  delivers what it has, says so on Telegram, and retries the rest next run. The real limit wording is written to
  `agent.log` as `usage limit: ...`.
- Paper text is untrusted. The model runs with no tools, scores are clamped, and the paper travels as JSON data.
  Treat the digest as advice to verify, not instructions. Medical items never prescribe; finance items never say
  buy or sell.
- `state.db` holds sent papers, triage scores and taught concepts. Deleting it makes the next run re-triage the
  recent window and may resend recent papers.
