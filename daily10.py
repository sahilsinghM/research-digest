"""Build today's Daily 10: the next step of the reading path as one short message."""
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import analyst
import digest
import openalex
import paths

log = logging.getLogger("daily10")
PATHS_DIR = Path(__file__).parent / "paths"


@dataclass
class Daily10:
    message: str
    terms: list  # pre-read terms taught today, so they are never explained again
    commit: Callable  # call after the message was really delivered: marks the step done


class LessonUnavailable(Exception):
    """No lesson today. `note` says why (for the reader); `fallback` is a recall-only Daily10, or None when nothing is
    due. The step itself is untouched, so it is simply tomorrow's lesson."""

    def __init__(self, reason, note, fallback=None):
        super().__init__(reason)
        self.reason, self.note, self.fallback = reason, note, fallback


def prepare(cfg, profile, store, ask, get_json, known_terms, now, paths_dir=None, notes=(), dry_run=False):
    f = cfg.get("foundations") or {}
    if not f.get("enabled"):
        return None
    today, pid = now.date(), f["path"]  # state is keyed by the file's name, not the display name inside it
    last = store.last_step_done(pid)
    if last and last.date() == today:
        return None  # one idea a day: a rerun the same day (after a delivered lesson) must not deliver another
    intervals = tuple(f.get("recall_days", (1, 3, 7, 21)))

    def due():
        return store.due_cards(today, f.get("max_recall_per_day", 2))

    def unavailable(reason, note):
        cards = due()
        fallback = None
        if cards:
            fallback = Daily10(digest.recall_only_msg(cards, note, notes), [],
                               lambda: store.mark_cards_shown(cards, today, intervals))
        return LessonUnavailable(reason, note, fallback)

    try:
        name, entries = paths.load_path((paths_dir or PATHS_DIR) / f"{pid}.toml")
        steps, flagged = paths.load_steps(get_json, store, pid, entries, persist=not dry_run)
    except (paths.PathError, openalex.OpenAlexError) as e:
        log.warning("reading path unavailable: %s", e)
        raise unavailable(type(e).__name__, f"Daily 10 lesson unavailable today ({type(e).__name__}); it will be tried again tomorrow")
    for e, reason in flagged:
        log.warning("path entry skipped: %s", reason)
    done = store.done_steps(pid)
    todo = [s for s in steps if paths.entry_key(s.entry) not in done]
    if not todo:
        if not due():
            return None
        raise unavailable("path complete", "You have finished this reading path. Only recall cards remain.")
    step = todo[0]
    lesson = analyst.lesson(ask, cfg["models"]["analyse"], step, profile, known_terms)
    if lesson is None:
        raise unavailable("lesson not written", "Daily 10 lesson unavailable today (lesson not written); it will be tried again tomorrow")
    notes = list(notes) + [f"Skipped, could not verify: {e['title']}" for e, _ in flagged]
    cards = due()
    msg = digest.daily10_msg(step, lesson, cards, len(steps) - len(todo) + 1, len(steps), name, notes)
    key = paths.entry_key(step.entry)

    def commit():
        store.mark_step_done(pid, key, now)
        store.add_cards(pid, key, lesson["recall"], today, intervals)
        store.mark_cards_shown(cards, today, intervals)

    return Daily10(msg, [t["term"] for t in lesson["prereads"]], commit)
