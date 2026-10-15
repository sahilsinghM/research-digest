"""Build today's Daily 10: the next step of the reading path as one short message."""
from dataclasses import dataclass
from pathlib import Path

import analyst
import digest
import paths

PATHS_DIR = Path(__file__).parent / "paths"


@dataclass
class Daily10:
    message: str
    terms: list  # pre-read terms taught today, so they are never explained again


def prepare(cfg, profile, store, ask, get_json, known_terms, now, paths_dir=None):
    f = cfg.get("foundations") or {}
    if not f.get("enabled"):
        return None
    name, entries = paths.load_path((paths_dir or PATHS_DIR) / f"{f['path']}.toml")
    step = paths.build_step(get_json, entries, 0)  # progress through the path arrives with the next slice
    lesson = analyst.lesson(ask, cfg["models"]["analyse"], step, profile, known_terms)
    if lesson is None:
        return None
    msg = digest.daily10_msg(step, lesson, [], step.index + 1, step.total, name)
    return Daily10(msg, [t["term"] for t in lesson["prereads"]])
