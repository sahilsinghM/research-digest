import argparse
import logging
import tomllib
from datetime import datetime, timezone
from pathlib import Path

import analyst
import digest
import runner
import sources
from rank import pick, prefilter
from store import Store

log = logging.getLogger("agent")
HERE = Path(__file__).parent


def run(cfg, profile, store, ask_model, fetch, send, now):
    """Fetch, score, read, format, send. Reads state but never writes it (delivery state arrives in a later issue)."""
    since = store.since(cfg["run"]["lookback_days_first_run"], now)
    papers, failed = fetch(cfg, since.date(), now.date())
    papers = prefilter(store.new_only(papers), cfg["keywords"]["medical"])
    notes = [f"sources failed: {', '.join(failed)}"] if failed else []

    ask = analyst.CallCap(ask_model, cfg["run"]["max_calls_per_run"])
    analyst.triage(ask, cfg["models"]["triage"], papers, profile, cfg["run"]["triage_batch"])
    log.info("triage: %d papers scored, %d at or above the bar", len(papers),
             sum(p.score >= cfg["run"]["min_score"] for p in papers))
    chosen = pick(papers, cfg["quota"], cfg["run"]["max_papers"], cfg["run"]["min_score"])

    done = []
    for p in chosen:
        a = analyst.deep_read(ask, cfg["models"]["analyse"], p, profile)
        if a:
            done.append((p, a))
        else:
            log.warning("skipping %s: model reply was not valid JSON", p.id)

    if not done:
        send("\n".join([f"Nothing worth your time today ({len(papers)} new papers scanned)."] + notes))
        return
    send(digest.header_msg(done, len(papers), now.date().isoformat(), notes))
    for p, a in done:
        send(digest.paper_msg(p, a))
    try:
        concept = analyst.teach(ask, cfg["models"]["analyse"], done, profile)
    except (runner.RunnerError, analyst.CallCapExceeded) as e:  # the concept is a bonus, never a blocker
        log.warning("no teach-me today: %s", e)
        concept = None
    if concept:
        send(digest.teach_msg(concept))

    log.info("model calls used: %d of %d", ask.calls, ask.cap)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="print the digest instead of sending it")
    args = ap.parse_args(argv)
    if not args.dry_run:
        raise SystemExit("Sending to Telegram arrives with issue 05; run with --dry-run for now.")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    log.info("claude plan: %s", runner.check_login())  # fail fast, before any fetching or model calls
    with open(HERE / "config.toml", "rb") as f:
        cfg = tomllib.load(f)
    profile_file = HERE / "profile.md"
    profile = profile_file.read_text() if profile_file.exists() else ""
    db = HERE / "state.db"
    run(cfg, profile, Store(db if db.exists() else ":memory:"), runner.claude, sources.fetch_all, print,
        datetime.now(timezone.utc))


if __name__ == "__main__":
    main()
