import argparse
import fcntl
import html
import logging
import os
import tomllib
from datetime import datetime, timezone
from pathlib import Path

import analyst
import delivery
import digest
import runner
import sources
from rank import pick, prefilter
from store import Store

log = logging.getLogger("agent")
HERE = Path(__file__).parent


def run(cfg, profile, store, ask_model, fetch, send, now, dry_run=False):
    """Fetch, score, read, format, send. Delivery state is written only when not a dry run, and
    last-success only when the whole run finished (a usage-limit stop or a crash leaves it behind)."""
    r, m = cfg["run"], cfg["models"]
    since = store.since(r["lookback_days_first_run"], now)
    papers, failed = fetch(cfg, since.date(), now.date())
    papers = prefilter(store.new_only(papers), cfg["keywords"]["medical"])
    notes = [f"sources failed: {', '.join(failed)}"] if failed else []

    ask = analyst.CallCap(ask_model, r["max_calls_per_run"])
    done, limit_hit = [], False
    try:
        analyst.triage(ask, m["triage"], papers, profile, r["triage_batch"])
        log.info("triage: %d papers scored, %d at or above the bar", len(papers),
                 sum(p.score >= r["min_score"] for p in papers))
        for p in pick(papers, cfg["quota"], r["max_papers"], r["min_score"]):
            a = analyst.deep_read(ask, m["analyse"], p, profile)
            if a:
                done.append((p, a))
            else:
                log.warning("skipping %s: model reply was not valid JSON", p.id)
    except runner.UsageLimitReached:
        limit_hit = True

    if done:
        send(digest.header_msg(done, len(papers), now.date().isoformat(), notes))
        for p, a in done:
            send(digest.paper_msg(p, a))
            if not dry_run:
                store.mark_sent(p)  # only after the message went out: a retry resends nothing already delivered
        if not limit_hit:
            try:
                concept = analyst.teach(ask, m["analyse"], done, profile)
            except runner.UsageLimitReached:
                limit_hit, concept = True, None
            except (runner.RunnerError, analyst.CallCapExceeded) as e:  # the concept is a bonus, never a blocker
                log.warning("no teach-me today: %s", e)
                concept = None
            if concept:
                send(digest.teach_msg(concept))
    elif not limit_hit:
        send("\n".join([f"Nothing worth your time today ({len(papers)} new papers scanned)."] + notes))

    if limit_hit:
        send(f"⚠ Claude usage limit reached: {len(done)} papers delivered. The rest will be retried on the next run.")
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
            dry_run=args.dry_run)

    return guarded(job, send)


if __name__ == "__main__":
    raise SystemExit(main())
