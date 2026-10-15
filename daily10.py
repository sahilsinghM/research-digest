"""Build today's Daily 10: the next step of the reading path as one short message."""
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import analyst
import digest
import paths

log = logging.getLogger("daily10")
PATHS_DIR = Path(__file__).parent / "paths"


@dataclass
class Daily10:
    message: str
    terms: list  # pre-read terms taught today, so they are never explained again
    commit: Callable  # call after the message was really delivered: marks the step done


def prepare(cfg, profile, store, ask, get_json, known_terms, now, paths_dir=None, notes=()):
    f = cfg.get("foundations") or {}
    if not f.get("enabled"):
        return None
    name, entries = paths.load_path((paths_dir or PATHS_DIR) / f"{f['path']}.toml")
    steps, flagged = paths.load_steps(get_json, store, name, entries)
    for e, reason in flagged:
        log.warning("path entry skipped: %s", reason)
    done = store.done_steps(name)
    todo = [s for s in steps if paths.entry_key(s.entry) not in done]
    if not todo:
        return None  # the path is complete
    step = todo[0]
    lesson = analyst.lesson(ask, cfg["models"]["analyse"], step, profile, known_terms)
    if lesson is None:
        return None
    notes = list(notes) + [f"Skipped, could not verify: {e['title']}" for e, _ in flagged]
    today = now.date()
    cards = store.due_cards(today, f.get("recall_days", [1, 3, 7, 21]), f.get("max_recall_per_day", 2))
    msg = digest.daily10_msg(step, lesson, cards, len(steps) - len(todo) + 1, len(steps), name, notes)
    key = paths.entry_key(step.entry)

    def commit():
        store.mark_step_done(name, key, now)
        store.add_cards(name, key, lesson["recall"], today)
        store.mark_cards_shown(cards, today)

    return Daily10(msg, [t["term"] for t in lesson["prereads"]], commit)
