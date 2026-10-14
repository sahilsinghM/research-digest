# Changelog

Format follows Keep a Changelog. Dates are when the work landed.

## [Unreleased]

### Changed
- Runs on the VPS as the low-privilege `digest` user with its own subscription token (`claude setup-token`) and its
  own copy of the `claude` binary instead of as root; root's crontab entry removed, root copy kept as an unscheduled
  fallback.

## [0.1.0] - 2026-10-14

First working version, deployed to the VPS and scheduled for 07:00 IST.

### Added
- Daily pipeline: fetch from arXiv, Crossref journals (Nature, Science, Cell, PNAS, major economics and finance
  journals), PubMed (medical whitelist plus Nature/Cell/Science/PNAS for their abstracts), bioRxiv, medRxiv, NBER.
- Haiku triage against a private reader profile; Sonnet deep read; per-area quotas and a minimum score.
- Plain-language cards for a beginner: headline, trust light (green/yellow/red), a pre-read of up to three
  concepts to learn first, takeaway, what it means for the reader, an action, and folded details with the link.
- Memory of taught terms and concepts so nothing is explained twice; a short "idea of the day".
- Telegram delivery with HTML escaping, shrink-to-fit under 4096 characters, plain-text fallback, rate-limit retry.
- Idempotent runs: sent papers never resent, cached triage scores, last-success only on a finished run, lock file,
  failure notices, graceful stop with a notice on a usage limit.
- `--dry-run`, `chat_id.py`, README operations guide, cron and logrotate setup on the VPS.
- Usage-limit detection built from the real message wording found inside the Claude Code program (session, weekly,
  Opus/Sonnet/Fable/fast, monthly spend, team budget, out of credits, credit balance), each covered by a test.

### Changed
- Model transport is headless Claude Code on the owner's subscription (no API key anywhere); a per-run call cap
  replaces a dollar budget.

### Fixed
- arXiv returned nothing (weekend lag) and NBER failed (feed moved, no dates); arXiv now retries patiently.
- Triage scored far too harshly; rubric recalibrated with anchors.
- A non-limit failure mid-run no longer discards papers already read; an outage backlog no longer exceeds the
  call cap every day; a total source outage no longer advances last-success.
- Messages could exceed Telegram's limit once escaped; Telegram timeouts and non-JSON errors handled.
- Deploy permissions: folder group-writable and files owned by an unknown uid after `rsync -a` (README fixed).

### Security
- Private profile passed via a 0600 file, not the command line; allow-listed child environment; login must be a
  subscription login; model text imitating a usage-limit message cannot stop a run; scores clamped; papers sent as
  JSON data; Telegram token never appears in errors or logs.

### Known gaps
- Limit wording is known, but the exit code / JSON of a real limit hit has not been observed (it is logged when it
  happens); JFE/JPE abstracts unavailable; science
  coverage thin; merged to `master` locally; no git remote configured yet.
