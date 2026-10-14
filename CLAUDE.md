# Research digest agent

A daily job that collects new papers (finance and economics, sciences, medicine), scores them against a private
reader profile, explains the best few in plain beginner language with a pre-read, and sends them to Telegram.
All model work runs through headless Claude Code on the owner's Claude **subscription**. Design and history:
`docs/prd/`, `docs/issues/` (vertical slices, 01-09 done), `CHANGELOG.md`, `README.md` (operations). Public repo: https://github.com/sahilsinghM/research-digest (the
repo is public, so never commit secrets, the profile, or real personal details).

## Commands

```bash
.venv/bin/pytest -q                  # whole suite; the exit code is what counts (see "Rules")
.venv/bin/python agent.py --dry-run  # real fetch + real claude, prints the digest, writes no state, sends nothing
.venv/bin/python chat_id.py          # prints the Telegram chat id(s) that messaged the bot (never the token)
```

## How it fits together

`agent.py run()` is the pipeline; every outside thing is injected so tests use fakes.
fetch (`sources.py`) -> drop already-sent (`store.py`) -> prefilter (`rank.py`: abstract length, medical keywords)
-> reuse cached scores / bound by call cap -> triage with the small model (`analyst.triage`) -> `rank.pick`
(quota per area, min score) -> deep read with the stronger model (`analyst.deep_read`, plain-language JSON with a
pre-read) -> `digest.py` cards -> `delivery.py` Telegram. `runner.py` is the only code that starts `claude`.

## Rules (each learned the hard way)

- **Subscription only, never an API key.** `runner.py` hands `claude` an allow-listed environment and checks
  `claude auth status` (must be `claude.ai` or `oauth_token`). Do not add env vars to `SAFE_ENV` lightly.
- **Isolation flags are load-bearing.** Without them one trivial call loaded ~243k tokens (all plugins/skills/MCP);
  with them ~575. Never pass `--bare` (it refuses subscription login). The system prompt (which contains the
  private profile) goes through a 0600 file, never argv.
- **Paper text is untrusted.** Model has no tools; papers travel as one JSON data object; scores are clamped; model
  text never becomes a link; everything is HTML-escaped. Model-written text (concept/term names) re-enters later
  prompts only as one-line, length-limited data.
- **Secrets and the profile never go in git** (`.env`, `profile.md`, `state.db` are gitignored). No personal
  details in code, tests, docs or commit messages. Fixtures use made-up data.
- **TDD.** Write the failing test, watch it fail for the right reason, then implement. When chaining commands, check
  pytest's own exit code (`pytest -q > out; rc=$?`), not `| tail`'s: a red test once got committed that way.
- **Delivery state is idempotent.** Mark a paper sent only after Telegram accepted it; record last-success last and
  only when the run finished; never advance it on a usage-limit stop or a total source outage.
- **Dry run writes nothing** (no sent flags, scores, concepts or last-success).

## Source quirks

- arXiv API trails real time by days over weekends (window is `since - 4 days`), answers 429 for long after a
  burst, and is slow: waits of 10/20/40 s and a 90 s timeout. Don't hammer it with repeated test runs.
- Crossref has no abstracts for Nature/Cell/JFE/JPE; Nature/Cell/Science/PNAS abstracts come from PubMed
  (`[[pubmed_extra]]` in config). JFE and JPE remain mostly invisible. Dedupe prefers the copy with an abstract.
- NBER's RSS (`back.nber.org`) has no dates; items count as new and the store dedupes. PubMed ids are the DOI when
  there is one.
- Papers under `min_abstract_chars` are dropped before any model call (news items, bare titles).

## The VPS

`root@178.104.65.133` (ssh as root for admin only). The app lives at `/home/digest/research-digest` and runs as the
low-privilege `digest` user (token login via `CLAUDE_CODE_OAUTH_TOKEN` in its `.env`, own copy of the `claude`
binary in `/home/digest/.local/bin`). Clock is UTC; cron `30 1 * * *` (= 07:00 IST) in `digest`'s crontab; log
`agent.log` (logrotate weekly). The box also runs the owner's other workloads (Docker apps, other cron jobs, other
`claude` processes sharing the same subscription allowance): do not touch anything outside the deploy folders, and
back up the crontab before editing it. Never copy root's `/root/.claude/.credentials.json` to another user (two
copies of an OAuth refresh token can invalidate each other and break the other apps). Deploy with the README's rsync
flags only: plain `rsync -a` once left the folder group-writable and files owned by an unknown uid. The old root copy
`/root/research-digest` is an unscheduled fallback; remove it once the new setup has proven itself.

## Parked / future work

- **Science coverage** (docs/issues/10): few science papers clear the bar for this reader. Owner is thinking about
  lowering the science bar, a daily wildcard slot, or leaving it. Decide after a few days of real digests.
- **Always-on bot** (docs/issues/11): a long-running Telegram bot with buttons ("explain simpler", thumbs up/down
  feeding the ranking, questions about a paper). Needs a service that stays up, not cron.
- The setup-token login lasts about a year: re-create it when runs report "not logged in".
- Usage-limit detection matches the wording found inside the Claude Code program; the exit code / JSON of a real
  hit is still unobserved and is logged (`usage limit: ...` in `agent.log`) when it happens.
- Per-source watermarks (a one-source outage can still lose that source's day); throwaway `CLAUDE_CONFIG_DIR`.
