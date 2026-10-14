# Personal Research Digest Agent: Design

> **Superseded in part (2026-10-13):** model calls now go through headless Claude Code on the owner's subscription, not the Anthropic API; there is no dollar cost cap (a per-run call cap replaces it) and no PDF full text in v1. See `docs/prd/2026-10-13-research-digest-prd.md`.

Date: 2026-10-13

## Goal

A personal agent that runs daily on the owner's VPS (cron). It finds new papers
from reputable journals and preprint servers since the last successful run,
reads and analyses the best ones, explains what each means for the owner and
for the world, suggests actions, teaches one concept per digest, and sends the
result to Telegram.

Success: a short daily digest (5-8 papers) arrives on Telegram, never repeats
a paper, is honest about evidence strength, and is specific to the owner's
situation (via `profile.md`).

## Topics

1. Finance and economics: economics, micro/macro, behavioral economics and
   finance, game theory, econometrics, finance, corporate finance, valuation,
   equity, trading, derivatives, F&O, quant finance.
2. Science and engineering: mathematics, physics, chemistry, biology, chemical,
   civil and bio engineering, materials science, earth science, geology,
   neuroscience, computer science.
3. Medical: nutrition, diet, sleep, cardiology, urology, sexual health,
   liver, kidney, skin, hair, mental health, internal health.

## Non-goals (v1)

Web UI, vector database, multi-user, paywalled-PDF scraping, Telegram
conversation (replies/questions), ranking feedback buttons, weekly deep dive.

## Personalization

`profile.md` (gitignored, never committed) holds the owner's personal context:
location, income and debt situation, trading plans and risk appetite, health
concerns and habits, life events and goals. It is passed to the model as
context in triage and deep-read prompts. This spec intentionally contains no
personal details.

## Pipeline

```
fetch -> dedupe -> triage (Haiku) -> deep-read (Sonnet) -> compose -> Telegram
           ^                                                   |
        SQLite  <---------- mark sent after confirmed ---------+
```

One script, run from cron once daily (default 07:00 IST).

### Sources (all free)

| Area | Sources |
|---|---|
| Finance/econ | arXiv (q-fin, econ), NBER working papers (RSS), Crossref feeds for AER, QJE, JPE, Econometrica, JF, JFE, RFS |
| Science/eng | arXiv (math, physics, cs, q-bio), bioRxiv, Crossref feeds for Nature, Science, Cell, PNAS, Nature-family |
| Medical | PubMed filtered to a journal whitelist (NEJM, Lancet, JAMA, BMJ, Nature Medicine, JACC, Gut, Hepatology, JAAD, similar) plus Cochrane; medRxiv flagged as preprint |

Full text is used for arXiv, bioRxiv and medRxiv (PDF sent to the model as a
document block); everything else is abstract only, and the digest says so.
Deferred: SSRN and RePEc (no usable public feed), PubMed Central and Unpaywall
full text. Medical journals come from PubMed only (journal whitelist).

"Since last run": each source is queried for items newer than the last
successful run timestamp. The timestamp advances only when the run completes,
so missed days catch up. First run looks back 2 days.

### Triage (Haiku)

Cheap keyword/topic pre-filter, then Haiku scores title+abstract 0-10 on:
topic relevance, relevance to the owner (from profile), evidence quality
(journal tier, study type, preprint). JSON output, ~20 papers per call.
Top 5-8 selected with per-category quotas (about 2 finance, 2 science, 2-3
medical). Quiet days produce a shorter digest; never pad.

### Deep read (Sonnet)

Per selected paper, with full text or abstract plus profile, produce one
structured record:

- what they did, what they found (plain language)
- evidence strength: design, sample size, effect size, limitations, conflicts
- why it matters: for the owner, for the world, suggested action (or "nothing yet")
- confidence flag: peer-reviewed / preprint / abstract only / animal-lab study

Plus one teach-me concept per digest (not per paper), with an example tied to
the owner's situation.

Guardrails: no invented numbers (every figure from supplied text); medical
items never prescribe and point to a doctor where relevant; finance items never
give buy/sell calls.

### Digest and Telegram delivery

Telegram limit is 4096 chars per message, so the digest is a series:

1. Header: date, counts by area, one-line "most important today".
2. One message per paper: title, journal, link, evidence badge, finding in 2-3
   lines, "For you" (impact + action), "For the world" (one line).
3. Teach-me message.

HTML parse mode; all model output escaped; failed send retries as plain text.
Sends only to the configured chat ID. Papers are marked sent only after
Telegram confirms delivery.

## Files

```
agent.py        orchestration, cron entry point, lock, failure notice
sources.py      one fetch + one pure parse function per source
store.py        SQLite state
rank.py         medical keyword prefilter, quota selection
llm.py          triage, deep read, teach, cost budget
digest.py       message formatting, Telegram send
profile.md      personal profile (gitignored)
config.toml     topics, journal whitelist, quotas, model names, cost cap
.env            ANTHROPIC_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID (gitignored)
state.db        SQLite (gitignored): papers(id,title,source,score,sent), runs(last_success)
tests/
```

## Errors and operations

- Sources fetched independently; one failure does not abort the run.
- Retry with backoff on API/source calls.
- Model JSON that fails to parse: retry once, then skip paper and log.
- Daily cost cap in config; run stops and notifies the owner if hit.
- Lock file prevents overlapping runs.
- Fatal errors send a short Telegram message instead of failing silently.
- File logging, rotated via logrotate.

## Testing

Small pytest files for logic that can break: dedupe and since-last-run,
quota selection, message splitting under 4096 chars with HTML escaping.
`--dry-run` prints the digest to the terminal instead of sending. Model output
quality is judged by reading real dry-run digests, not by mocks.

## Cost

Estimated $0.50-$2/day (Haiku triage, Sonnet deep read of 6-8 papers),
about $15-60/month.

## Setup (post-build)

Create the Telegram bot via BotFather and get the chat ID; add the Anthropic
key; write `profile.md`; add the cron entry; run `--dry-run` for several days
before enabling sending.
