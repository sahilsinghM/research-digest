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

## VPS (currently `/root/research-digest`, runs as root, UTC clock)

- `.env` (mode 600): `TELEGRAM_BOT_TOKEN=` and `TELEGRAM_CHAT_ID=`. Get the chat id with `python3 chat_id.py`
  after messaging the bot once.
- `profile.md` (mode 600) lives only on the VPS and this dev machine, never in git.
- Cron, 01:30 UTC = 07:00 IST, logging to `agent.log` (rotated weekly by `/etc/logrotate.d/research-digest`):
  ```
  30 1 * * * cd /root/research-digest && PATH=/root/.local/bin:/usr/local/bin:/usr/bin:/bin && export PATH && set -a && . ./.env && set +a && .venv/bin/python agent.py >> /root/research-digest/agent.log 2>&1
  ```
  `claude` lives in `/root/.local/bin`, which cron does not have on its PATH, hence the explicit PATH.
- Deploy (never `rsync -a`: it copies this machine's owner and permissions onto the server):
  ```bash
  rsync -rlt --no-perms --no-owner --no-group --chmod=D700,F600 \
    --exclude=.git --exclude=.venv --exclude=.superpowers --exclude=__pycache__ --exclude=.pytest_cache \
    --exclude=state.db --exclude=.lock --exclude=agent.log --exclude=.env --exclude=profile.md \
    ./ root@HOST:/root/research-digest/
  ```
- Pause: `crontab -e` and comment the line. A run is safe to repeat: papers already sent are never resent.

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
