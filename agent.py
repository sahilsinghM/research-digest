import argparse
import fcntl
import html
import logging
import os
import tomllib
from datetime import datetime, timezone
from pathlib import Path

import analyst
import daily10
import delivery
import digest
import openalex
import runner
import sources
from rank import pick, prefilter
from store import Store

log = logging.getLogger("agent")
HERE = Path(__file__).parent


def run(cfg, profile, store, ask_model, fetch, send, now, dry_run=False, get_json=None):
    """Fetch, score, read, format, send. With the foundations track on, the Daily 10 leads the day and new papers are
    an optional bonus above a high bar. Delivery state is written only when not a dry run, and last-success only
    when the whole run finished (a usage-limit stop, a mid-run failure or a crash leaves it behind so the next run
    picks the work up)."""
    r, m = cfg["run"], cfg["models"]
    f = cfg.get("foundations") or {}
    foundations = bool(get_json and f.get("enabled"))
    bar = f.get("new_paper_min_score", 8) if foundations else r["min_score"]
    cap = f.get("max_new_papers", 1) if foundations else r["max_papers"]

    since = store.since(r["lookback_days_first_run"], now)
    fetched, failed = fetch(cfg, since.date(), now.date())
    if failed and not fetched:  # total outage: advancing would lose that day's papers for good
        send(f"⚠ All sources failed ({', '.join(failed)}): nothing fetched. Will retry on the next run.")
        return
    papers = prefilter(store.new_only(fetched), cfg["keywords"]["medical"], r["min_abstract_chars"])
    notes = [f"sources failed: {', '.join(failed)}"] if failed else []

    # Papers scored on an earlier run (and not yet sent) keep their score instead of being triaged again.
    cached = store.cached_scores(papers)
    for p in papers:
        if p.id in cached:
            p.score = cached[p.id]
    fresh = [p for p in papers if p.id not in cached]

    # Triage must never eat the whole call cap (an outage backlog would then crash every day): keep the newest
    # papers that fit, leaving room for the deep reads and the concept, each of which may retry once.
    reserve = 2 * r["max_papers"] + 2
    room = max(1, (r["max_calls_per_run"] - reserve) // 2) * r["triage_batch"]
    if len(fresh) > room:
        notes.append(f"{len(fresh) - room} older papers not triaged (call cap)")
        fresh = sorted(fresh, key=lambda p: p.published, reverse=True)[:room]
        papers = [p for p in papers if p.id in cached or p in fresh]

    ask = analyst.CallCap(ask_model, r["max_calls_per_run"])
    known = store.recent_concepts(200)  # terms already taught (newest first): never explain them again
    d10, stop, delivered = None, None, 0
    if foundations:
        try:
            d10 = daily10.prepare(cfg, profile, store, ask, get_json, known, now, notes=notes)
        except daily10.LessonUnavailable as e:
            log.warning("Daily 10 lesson unavailable: %s", e.reason)
            d10 = e.fallback  # a recall-only day, already carrying the reason
            if d10 is None:
                notes.append(e.note)  # nothing to recall: the reason rides in the header or quiet message
        except runner.UsageLimitReached as e:
            log.warning("usage limit: %s", e)
            stop = "Claude usage limit reached"
        except (runner.RunnerError, analyst.CallCapExceeded) as e:
            log.warning("Daily 10 unavailable: %s", e)
            notes.append(f"Daily 10 unavailable today ({type(e).__name__})")
    if d10:
        send(d10.message)
        delivered += 1
        known = d10.terms + known
        if not dry_run:  # only after delivery: the step counts as done and its terms as taught
            d10.commit()
            for term in d10.terms:
                store.record_concept(term, now)

    done = []
    if not stop:
        try:
            scored = analyst.triage(ask, m["triage"], fresh, profile, r["triage_batch"])
            if not dry_run:
                store.record_scores([p for p in fresh if p.id in scored])
            log.info("triage: %d papers scored, %d at or above the bar", len(papers), sum(p.score >= bar for p in papers))
            for p in pick(papers, cfg["quota"], cap, bar):
                try:
                    a = analyst.deep_read(ask, m["analyse"], p, profile, known)
                except (runner.RunnerError, analyst.CallCapExceeded) as e:
                    if isinstance(e, runner.UsageLimitReached):
                        raise
                    stop = f"{type(e).__name__}"  # keep what was already read; the rest is retried next run
                    log.warning("deep read stopped: %s", e)
                    break
                if a:
                    done.append((p, a))
                    known = [x["term"] for x in a["prereads"]] + known  # so the next paper does not repeat them
                else:
                    log.warning("skipping %s: model reply was not valid JSON", p.id)
        except runner.UsageLimitReached as e:
            log.warning("usage limit: %s", e)  # keeps the real wording/exit behaviour for tightening the detection
            stop = "Claude usage limit reached"

    if done:
        if not d10:
            send(digest.header_msg(done, len(papers), now.date().isoformat(), notes))
        for p, a in done:
            send(digest.paper_msg(p, a, bonus=bool(d10)))
            delivered += 1
            if not dry_run:
                store.mark_sent(p)  # only after the message went out: a retry resends nothing already delivered
                for x in a["prereads"]:
                    store.record_concept(x["term"], now)
        if not stop and not foundations:
            try:
                concept = analyst.teach(ask, m["analyse"], done, profile, known[:100])
            except runner.UsageLimitReached as e:
                log.warning("usage limit: %s", e)
                stop, concept = "Claude usage limit reached", None
            except (runner.RunnerError, analyst.CallCapExceeded) as e:  # the concept is a bonus, never a blocker
                log.warning("no teach-me today: %s", e)
                concept = None
            if concept:
                send(digest.teach_msg(concept))
                if not dry_run:
                    store.record_concept(str(concept["name"]), now)  # only after it was really sent
    elif not stop and not d10:
        send("\n".join([f"Nothing worth your time today ({len(papers)} new papers scanned)."] + notes))

    if stop:
        send(f"⚠ Run cut short ({stop}): {delivered} item{'s' if delivered != 1 else ''} delivered. "
             "The rest will be retried on the next run.")
        return
    if not dry_run:
        store.record_success(now)
    log.info("model calls used: %d of %d", ask.calls, ask.cap)


def acquire_lock(path):
    """Return an open, exclusively locked file, or None if another run holds the lock."""
    f = open(path, "w")
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return f
    except BlockingIOError:
        f.close()
        return None


def guarded(job, send):
    """Run job(); on any crash tell the owner (error type and a short message) and return exit code 1."""
    try:
        job()
        return 0
    except Exception as e:
        log.exception("run failed")
        try:
            send(f"Digest run failed: {type(e).__name__}: {html.escape(str(e)[:200], quote=False)}")
        except Exception:
            log.exception("could not send the failure notice")
        return 1


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="print the digest instead of sending it; writes no state")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    if args.dry_run:
        send = print
    else:
        try:
            token, chat = os.environ["TELEGRAM_BOT_TOKEN"], os.environ["TELEGRAM_CHAT_ID"]
        except KeyError as e:
            raise SystemExit(f"{e.args[0]} is not set (see README)") from None
        send = lambda text: delivery.send(token, chat, text)  # noqa: E731

    lock = acquire_lock(HERE / ".lock")
    if lock is None:
        log.warning("another run is in progress, exiting")
        return 0

    def job():
        log.info("claude plan: %s", runner.check_login())  # fail fast, before any fetching or model calls
        with open(HERE / "config.toml", "rb") as f:
            cfg = tomllib.load(f)
        profile_file = HERE / "profile.md"
        profile = profile_file.read_text() if profile_file.exists() else ""
        db = HERE / "state.db"
        store = Store(db if db.exists() or not args.dry_run else ":memory:")
        run(cfg, profile, store, runner.claude, sources.fetch_all, send, datetime.now(timezone.utc),
            dry_run=args.dry_run, get_json=openalex.http_get_json)

    return guarded(job, send)


if __name__ == "__main__":
    raise SystemExit(main())
