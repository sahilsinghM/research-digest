# PRD: Daily 10, a ten-minute foundations track

Status: ready-for-agent once the owner approves. Extends `2026-10-13-research-digest-prd.md` (the daily digest stays;
this adds a new main item and changes what new papers must clear to appear).

## Problem Statement

The daily digest of brand-new papers is not useful to this reader. Frontier preprints assume knowledge the reader
does not have, and most are niche. The reader is a beginner who wants to rebuild a scientific way of thinking and,
over years, real research skill, with only about ten minutes a day, a full-time job, and a history of forgetting
what was read because nothing forced them to use it. They want to go to the source of ideas: the landmark papers,
their reviews, and the citation trail that shows what each idea was built on and what it led to.

## Solution

A "Daily 10" session replaces the new-paper feed as the main daily item. Each day delivers one step of a learning
path: a short recall question from an earlier day, the day's single foundational idea explained in plain beginner
language with a short pre-read, where it came from and what it led to (from real citation data), an optional peek at
the original paper, and one sentence the reader writes themselves. Earlier cards return on a fixed spaced schedule so
the material sticks. The first path is the foundations of finance: risk, pricing, volatility, behaviour and the
evidence on retail traders. New papers appear only when they are excellent.

## User Stories

1. As the reader, I want one short session a day that takes about ten minutes, so that I can keep the habit alive on a busy or low day.
2. As the reader, I want each day to cover exactly one idea, so that I am never overwhelmed.
3. As the reader, I want a learning path in a sensible order (what I must understand first comes first), so that each step builds on the last.
4. As the reader, I want the path to start with the foundations of finance and risk, so that I learn the base before the advanced material.
5. As the reader, I want each step to say which step of how many I am on, so that I can see progress.
6. As the reader, I want the landmark paper behind each idea named with its year and how many times it has been cited, so that I know why it matters.
7. As the reader, I want to see what the idea was built on and what it led to, so that I understand where ideas come from.
8. As the reader, I want those links to come from real citation data and not from the model's memory, so that I can trust them.
9. As the reader, I want a pre-read of the one or two terms I need first, so that the idea makes sense.
10. As the reader, I want the idea in a few short plain lines, so that I can follow it on a phone.
11. As the reader, I want a link to free full text of the original paper when one exists, so that I can read the source if I choose.
12. As the reader, I want one concrete thing to look for in the original, so that peeking at it is not intimidating.
13. As the reader, I want the peek at the source to be optional, so that the ten minutes stay achievable.
14. As the reader, I want a recall question from an earlier day with the answer hidden until I tap, so that I practise remembering instead of just reading.
15. As the reader, I want old cards to come back after 1, 3, 7 and 21 days, so that I do not forget again.
16. As the reader, I want no more than two recall questions in a day, so that the session stays short.
17. As the reader, I want to be prompted to write one sentence in my own words, so that I turn reading into understanding.
18. As the reader, I want it to be clear when an explanation comes from background knowledge and not from the paper's own text, so that I know what to double-check.
19. As the reader, I want years and citation counts to be clearly facts from the data, so that numbers are never invented.
20. As the reader, I want the reading list to be a short, editable file, so that I can add or remove papers and change the order.
21. As the reader, I want every paper on the list checked against the citation data, so that a wrong or mismatched paper is flagged instead of silently used.
22. As the reader, I want reprints and book-chapter copies of the same paper not to appear as separate steps, so that the path has no duplicates.
23. As the reader, I want a step to count as done only after it was actually sent to me, so that a failed day never skips a step.
24. As the reader, I want the same step not to be sent twice, so that nothing repeats.
25. As the reader, I want a day still to produce something useful when the citation service is down, so that the habit is not broken.
26. As the reader, I want new papers to appear only when they score very high, and at most one a day, so that I stop wading through weak ones.
27. As the reader, I want the Daily 10 to arrive in the same Telegram chat in the same short, scannable style, so that nothing is new to learn about the format.
28. As the reader, I want terms I have already learned not to be explained again, so that pre-reads stay short.
29. As the reader, I want my other topics (mind, body) to be able to queue as later paths, so that the system can grow without a redesign.

## Implementation Decisions

- **Citation data source: OpenAlex**, a free service that needs no key. A spike (2026-10-15) confirmed it returns citation counts, references backward, citing works forward, open-access links and, for many but not all works, an abstract. Findings that shape the design: roughly half of the classics have no abstract; "most cited citing work" is often off-topic; reprints and book-chapter copies duplicate the same paper; automatic "best review" search is unreliable in finance. Hence the path is a curated list that the citation data verifies and connects, not a fully automatic crawl.
- **Reading path definition.** A small human-editable file per path: a name, an ordered list of landmark works (title, authors, year, and an optional note on why it is there). The first path is "finance: risk, pricing and behaviour", about fifteen works ordered by what must be understood first (risk and return, CAPM, market efficiency, option pricing and its extensions, volatility, stochastic volatility, behavioural finance, evidence on retail traders, bet sizing). The reader reviews and may edit the list.
- **Path resolver (deep module).** Given the list, it finds each work in the citation data by title, authors and year, accepts it only if the match is confident, prefers the original over reprints and chapter copies, and flags anything uncertain for the reader instead of guessing. It caches what it finds so daily runs make few or no outside calls.
- **Edges.** For a step, "built on" are references of that work that are on the path or are very highly cited and on topic; "led to" are highly cited works that cite it and are on topic. Anything off-topic is dropped. Years and citation counts shown are data only.
- **Lesson writer (analyst job).** Given a step's data (title, year, citation count, abstract if any, open-access link, built-on and led-to titles), the already-known terms, and the reader profile, the model returns: a headline, up to two pre-read terms, the idea in at most five short lines, one thing to look for in the original, a one-sentence prompt for the reader, and one or two recall question/answer pairs. Where the abstract is missing it may use well-established background and must say so; every number about citations and years is supplied by the data and never written by the model. Same safety rules as the digest: no tools, paper text and titles as data, scores and lengths bounded, output escaped.
- **Spaced recall.** Recall cards are stored with the date they were created. Due cards are those 1, 3, 7 and 21 days old; at most two appear per day. The schedule is fixed, not adaptive, because there is no way to answer yet; an always-on bot with buttons would allow adaptive scheduling later (parked, issue 11).
- **Progress.** Each path keeps the current step. A step advances only after its message was delivered. A step that cannot be resolved or written is skipped with a note and retried the next day, never silently dropped.
- **Daily message.** The Daily 10 is the first and main item of the day: recall, today's idea (headline, pre-read, lines, built-on/led-to), optional source peek with link, and the reader's sentence prompt. Hidden answers use Telegram's spoiler formatting. It follows the existing rules: HTML escaped, shrunk to fit under the message limit, never cut inside a tag.
- **Mix with new papers.** New papers are triaged as today but must clear a much higher score to appear, at most one a day, shown as an optional bonus after the Daily 10. The old "idea of the day" is replaced by the Daily 10. The quiet-day message is no longer needed because the Daily 10 always exists unless the path is complete.
- **Failure behaviour.** If the citation service is down and the step is not cached, the day delivers the recall cards and a note, and the step is retried tomorrow. A usage-limit stop behaves as today: deliver what is complete, say so, do not advance what was not sent.
- **Config.** One new section: whether the track is on, which path, the recall intervals, and the minimum score and maximum count for new papers.
- **State.** New tables: resolved path steps (cache), path progress, and recall cards. Existing tables are unchanged.
- **Privacy and safety.** The path file and tests contain no personal details. The reader profile is used as in the digest. The repo is public.

## Testing Decisions

- A good test checks behaviour through a module's public interface with injected fakes, never the real internet or the real model. Prior art: the existing tests use small inline fixtures, injected fetchers and fake model callables.
- **Tested modules:** the citation client (parsing, abstract reconstruction, duplicate handling, rate-limit and failure behaviour, using fixture shapes taken from the 2026-10-15 spike), the path resolver (confident match, ambiguous match flagged, reprints deduplicated, caching), edge building (off-topic dropped, counts from data), the lesson writer (bounded output, never trusting model-written numbers, background labelled when the abstract is missing, known terms respected), spaced recall (exact due days, cap of two, no card before its time), progress (advances only after delivery, survives a failed send), the message formatter (escaping, spoilers, size, well-formed tags), and the pipeline (Daily 10 first, new papers gated, citation service down, usage-limit stop, dry run writes nothing).
- Real-service behaviour is checked by a recorded manual live check at the end of the slices, not in automated tests.

## Out of Scope

- An always-on bot, buttons, answering recall questions, adaptive spacing, or capturing the reader's own sentence (issue 11).
- Automatic suggestion of extra papers for the list.
- Paths other than finance (the mind and body paths are queued for later).
- Reading full PDFs; features for finding people or communities; grading answers.

## Further Notes

- The retention check of what the reader still remembers from prior study and the "find a wedge" work are separate, later efforts.
- Explanations of classics from background knowledge can contain errors; every card links to the source and labels what is background.
