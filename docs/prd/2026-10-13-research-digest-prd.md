# PRD: Personal Research Digest Agent

Status: ready-for-agent. Supersedes the LLM transport sections of
`docs/superpowers/specs/2026-10-13-research-digest-design.md` (that spec called the Anthropic API; this PRD
uses the owner's Claude subscription through headless Claude Code). Everything else in the spec still holds.

## Problem Statement

I want to keep up with the best new research in finance and economics, the hard sciences and engineering, and
medicine, but there are thousands of papers a day across dozens of journals and preprint servers. I cannot read
them, I cannot tell which ones matter to me, and when I do read one I do not know what it means for my own life:
my money, my health, my work. Existing paper-digest tools cover only arXiv, rank by topic instead of by me, do
not weigh evidence strength, and never teach. I also do not want to pay per-token API costs for a personal tool
when I already pay for a Claude subscription.

## Solution

A small agent on my VPS that runs every morning. It collects everything new from reputable sources since its last
successful run, throws away what I have already seen, scores the rest against a private profile of who I am and
what I care about, reads the best handful carefully, and sends me a short Telegram digest. Each item says what the
researchers found, how strong the evidence is, what it means for me and for the world, and one concrete thing to
do (or "nothing yet"). Each digest also teaches me one underlying concept in plain language. All model work runs
through my Claude subscription via headless Claude Code, never an API key.

## User Stories

1. As the owner, I want a digest to arrive on Telegram every morning at 07:00 IST, so that I start the day informed without opening anything.
2. As the owner, I want the agent to fetch only papers published since its last successful run, so that I never see stale material.
3. As the owner, I want a missed day to be caught up on the next run, so that a VPS outage does not silently lose papers.
4. As the owner, I want the first run to look back only two days, so that I am not flooded on day one.
5. As the owner, I want papers I was already sent never to be sent again, so that the digest stays fresh.
6. As the owner, I want a run that crashes halfway not to resend the papers it already delivered, so that retries are safe.
7. As the owner, I want finance and economics coverage (economics, behavioural economics and finance, game theory, econometrics, corporate finance, valuation, trading, derivatives, F&O, quant finance), so that my money decisions rest on evidence.
8. As the owner, I want mathematics, physics, chemistry, biology, engineering, materials, earth science, neuroscience and computer science coverage, so that I follow how the world is changing.
9. As the owner, I want medical coverage for sleep, nutrition, cardiology, urology, sexual health, liver, kidney, skin, hair, mental health and internal health, so that I learn what the evidence says about my own body.
10. As the owner, I want papers drawn from reputable journals and preprint servers only, so that I am not reading noise.
11. As the owner, I want each source to fail independently, so that one broken feed never cancels the whole digest.
12. As the owner, I want the digest to mention which sources failed that day, so that I know what I might have missed.
13. As the owner, I want a private profile file describing my situation, goals, habits and health concerns, so that "what this means for you" is specific instead of generic.
14. As the owner, I want my profile to stay on my VPS and out of git, so that my personal details are never published.
15. As the owner, I want papers scored 0 to 10 for fit, usefulness to me and evidence quality, so that the best rise to the top.
16. As the owner, I want a harsh scoring bar, so that a quiet day yields a short digest instead of padding.
17. As the owner, I want per-area quotas (finance, science, medical), so that one area cannot crowd out the others.
18. As the owner, I want medical papers prefiltered by my topic keywords, so that broad medical feeds do not waste scoring effort.
19. As the owner, I want a "nothing worth your time today" message on empty days, so that silence never means "the agent is broken".
20. As the owner, I want each selected paper read in depth, so that the summary reflects the paper and not just its title.
21. As the owner, I want each item to state what was done and what was found in plain language, so that I understand it without a degree.
22. As the owner, I want each item to state the study design, sample size, effect size and limitations, so that I can judge how far to trust it.
23. As the owner, I want a badge showing whether an item is peer-reviewed or a preprint, so that I weigh it accordingly.
24. As the owner, I want a badge showing whether the model had only the abstract, so that thin analyses are labelled as thin.
25. As the owner, I want "for you", "do", and "for the world" lines on every item, so that I get implications and a next step.
26. As the owner, I want "nothing to do yet" to be a valid action, so that I am not given busywork.
27. As the owner, I want the model never to invent numbers, so that I can trust every figure.
28. As the owner, I want medical items never to prescribe or diagnose and to say when to see a doctor, so that the digest informs without replacing care.
29. As the owner, I want finance items never to say buy or sell and to describe risks, so that I make my own decisions.
30. As the owner, I want one concept explained per digest with an example from my own situation, so that I steadily learn the ideas behind the papers.
31. As the owner, I want a header message with date, counts per area and the single most important item, so that I can triage in ten seconds.
32. As the owner, I want one message per paper, so that each is easy to read, forward or save.
33. As the owner, I want messages kept under Telegram's size limit, so that nothing is silently cut off.
34. As the owner, I want model and source text escaped, so that odd characters never break formatting.
35. As the owner, I want a plain-text fallback if formatting is rejected, so that a bad character never loses a message.
36. As the owner, I want the bot to send only to my chat, so that nobody else can receive or trigger anything.
37. As the owner, I want all model calls to use my Claude subscription and never an API key, so that I pay no per-token costs.
38. As the owner, I want the agent to guarantee no API key is in play even if one exists in the environment, so that I am never billed by accident.
39. As the owner, I want model calls run with all tools disabled and my other Claude configuration isolated, so that untrusted paper text can never make the model take actions or load unrelated plugins and hooks.
40. As the owner, I want a hard cap on model calls per run, so that a bug cannot burn my subscription allowance.
41. As the owner, I want the agent to stop gracefully and tell me on Telegram when my subscription session or weekly limit is hit, so that I know why a digest is short or missing.
42. As the owner, I want a run stopped by a usage limit not to advance its last-success marker, so that the next run picks the work up.
43. As the owner, I want a failure notice on Telegram when a run crashes, so that I never get silent failures.
44. As the owner, I want two runs never to overlap, so that a slow run and the next cron tick do not collide.
45. As the owner, I want a dry-run mode that prints the digest and writes no state, so that I can judge quality for several days before enabling delivery.
46. As the owner, I want logs written to a file and rotated, so that I can diagnose problems without the disk filling up.
47. As the owner, I want the agent to run under a dedicated low-privilege user on the VPS, so that a bug cannot touch the rest of the server.
48. As the owner, I want my Claude login token stored in a permission-restricted file, so that it is not readable by other users.
49. As the owner, I want a short setup guide covering the Telegram bot, the Claude token, the profile and the cron line, so that I can rebuild the setup on a new server.
50. As the owner, I want an automated check that the Claude login is valid before each run, so that an expired token produces a clear message instead of a mystery.
51. As the owner, I want the thresholds, quotas, journals, keywords and models in one config file, so that I can tune behaviour without editing code.
52. As the owner, I want a thin working digest end to end early, so that I can start judging real output before every feature exists.

## Implementation Decisions

**Already built and tested (Tasks 1-4 of the earlier plan), kept as is:**
- Config file as the single place for tunables (run limits, quotas, medical keywords, arXiv queries, journal list, PubMed whitelist).
- Paper record type shared by every module.
- Sources module: independent fetchers for arXiv, Crossref journals, PubMed, bioRxiv, medRxiv and NBER, each with a pure parser; a single `fetch_all` returning papers deduplicated by id plus the names of failed sources. Verified live: ~460 papers per two-day window across all three areas.
- Store module: SQLite with a sent-papers table and a runs table; answers "since when", records success, marks sent, filters out already-sent papers.
- Rank module: medical keyword prefilter and quota-based selection with a minimum score and a total cap.

**New and changed:**
- **Claude runner (deep module).** One narrow interface: given a model alias, a system prompt and a user message, return the model's text. It owns everything about talking to headless Claude Code: building the command, strict isolation, auth guarantee, timeout, error and usage-limit detection. Callers know nothing about subprocesses.
  - Uses the subscription only. Authentication comes from a long-lived OAuth token created once with the Claude token command and supplied through the environment. The runner removes any API-key or auth-token variables from the child environment so the subscription is always used, and it must not use the bare mode (which refuses subscription credentials).
  - Isolation: no tools at all, no MCP servers, project/local settings sources only, an empty working directory, a dedicated config directory, no session persistence, a turn limit of one, and a per-call timeout. Output is requested as JSON and the runner reads the result text field.
  - Usage-limit detection: because the documented exit code and error fields for a limit hit are not specified, the runner treats any non-zero exit, or a result containing the documented session-limit or weekly-limit phrases, as a stop signal and raises a dedicated usage-limit error. The exact behaviour must be confirmed once on the VPS and the detection tightened.
  - A login self-check (the auth status command) runs at the start of each run and fails fast with a readable message.
  - Calls are strictly serial.
- **Analyst module** replaces the old LLM module. It uses the runner for three jobs: batch triage on the small fast model, per-paper deep read on the stronger model, and one teach-me concept per digest. It keeps the shared pieces: tolerant JSON parsing (code fences, surrounding prose), one retry on unparseable output, then skip, and a call counter with a hard cap per run that raises when exceeded. It replaces the dollar budget, because a subscription has no per-token price.
  - Triage batch size is raised so a typical day needs about 15-20 triage calls rather than 25 or more. Total calls per run target well under 40.
  - Abstract only for all papers in this version. Full-text PDF reading is deferred (it needs a PDF tool on the server and its token cost is undocumented).
  - Prompts carry the profile, the rules (no invented numbers, no prescribing, no buy/sell, honest about weak or irrelevant work) and require JSON output.
  - Because paper text is untrusted, the no-tools isolation is the primary defense against prompt injection; the prompt also tells the model to treat paper text as data.
- **Digest module** (formatting and Telegram delivery): header, per-paper and teach-me messages; length-clipped fields so one paper never exceeds the 4096-character limit; HTML escaping; splitting as a safety net; plain-text fallback; retry on Telegram rate limiting.
- **Pipeline module**: fetch, drop already-sent, prefilter, triage, pick, deep read, compose, send, mark sent per paper after confirmed delivery, record success last. Dry run writes nothing. Lock file prevents overlap. Any crash sends a failure notice. A usage-limit error sends a distinct "limit reached" notice, sends whatever was already complete, and does not advance last-success.
- **Operations**: deploy to the VPS over SSH under a dedicated user; the owner creates the Claude token, the Telegram bot token and the profile file on the VPS themselves (no secrets pass through the development session); cron at 01:30 UTC (07:00 IST, VPS is on UTC); log file with rotation; a short README.
- **Delivery order**: the work is cut into end-to-end vertical slices so a real digest exists after the first slice, then quality, safety and operations are layered on. Slicing is done in the issues, not here.

## Testing Decisions

- A good test exercises external behaviour through the module's public interface and survives refactors: inputs in, observable outputs or state out. No tests of private helpers or call ordering inside a module.
- **Tested modules:** Sources (parsers, failure isolation, dedupe, live smoke check kept as a manual step), Store, Rank, Analyst, Digest, Pipeline, and the Claude runner.
- **Claude runner:** tested against a fake `claude` executable placed first on the path, so the real subprocess code runs. The fake lets tests assert that API-key variables are stripped, that the isolation flags are passed, that JSON output is parsed, that a non-zero exit and the limit phrases raise the usage-limit error, and that a hang is cut off by the timeout. The real Claude binary is never called in automated tests.
- **Analyst:** tested with a fake runner function: parsing of fenced or prose-wrapped JSON, missing scores defaulting to zero, batch boundaries, retry-once then skip, call-cap enforcement, empty abstracts.
- **Pipeline:** tested end to end with fake fetch, fake runner and fake send: happy path, dry run writes nothing, quiet day, failed source reported, usage limit mid-run, midway send failure keeps delivered papers marked and does not advance last-success.
- **Digest:** escaping, size limit with oversized input, splitting, plain-text fallback, badges, header counts.
- Prior art: the existing tests for Sources, Store and Rank use small inline fixtures and pure functions with monkeypatching; follow that style.
- Prompt and summary quality cannot be unit-tested; it is judged by reading real dry-run digests over several days before enabling delivery.

## Out of Scope

- Full-text PDF reading, PubMed Central and Unpaywall full text.
- SSRN and RePEc.
- A web interface, vector database, or multi-user support.
- Telegram replies, questions to the bot, feedback buttons, or learning from feedback.
- A weekly deep-dive digest.
- Sharing the tool with others or running it on behalf of others; the subscription terms cover personal use of one's own account with the unmodified Claude Code binary only.
- Medical advice, diagnosis, or financial buy/sell recommendations.

## Further Notes

- Terms of use: Anthropic's documentation says subscription limits assume ordinary individual use, and that signing in to the unmodified Claude Code binary with one's own subscription is allowed. Scheduled personal use is not explicitly addressed, and "ordinary" is undefined. This is the owner's call to accept; it is not legal advice. If the tool is ever shared or productised, it must move to an API key.
- The earlier quota values sum to 7 although the cap is 8, so the digest holds at most 7 papers until the quotas or cap change.
- Subscription allowances are shared with the owner's other Claude use (session and weekly windows). A heavy day elsewhere can leave less for the digest; the stop-gracefully behaviour exists for that reason.
- The VPS currently allows login only as root. The plan is to create a dedicated low-privilege user before installing anything.
- The owner's personal profile (finances, health, habits) lives only in the private profile file on the VPS and must never appear in the repository, tests, logs or commit messages.
- Prompt injection (untrusted paper text reaches the model): defenses are no tools and no network for the model, scores clamped to 0-10 with non-numbers and non-finite values rejected, each paper sent as a single JSON data object with a bounded abstract, links taken only from source metadata (never from model text), all output escaped, and a usage-limit stop that cannot be triggered by model text. Residual risk: a hostile abstract could still bias a score or a summary within those bounds, so the digest is advice to verify, not instruction to follow.
