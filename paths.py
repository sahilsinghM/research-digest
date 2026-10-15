"""Reading paths: a short, human-editable list of landmark papers, checked and connected with citation data."""
import tomllib
from dataclasses import dataclass

import openalex


class PathError(Exception):
    """The reading-path file is missing or malformed."""


class StepUnavailable(Exception):
    """A step could not be matched confidently in the citation data."""


@dataclass
class Step:
    index: int
    total: int
    entry: dict
    work: openalex.Work
    built_on: list
    led_to: list

    @property
    def background(self):
        return not self.work.abstract  # no abstract: the explanation can only come from background knowledge


def load_path(file):
    try:
        with open(file, "rb") as f:
            data = tomllib.load(f)
    except FileNotFoundError:
        raise PathError(f"path file not found: {file}") from None
    except tomllib.TOMLDecodeError as e:
        raise PathError(f"path file is not valid TOML: {e}") from None
    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        raise PathError("path file needs a name")
    raw = data.get("step")
    if not isinstance(raw, list) or not raw:
        raise PathError("path file needs at least one [[step]]")
    steps = []
    for i, s in enumerate(raw, 1):
        title, year = s.get("title"), s.get("year")
        if not isinstance(title, str) or not title.strip():
            raise PathError(f"step {i} needs a title")
        if not isinstance(year, int) or isinstance(year, bool):
            raise PathError(f"step {i} ({title!r}) needs a year as a number")
        authors = s.get("authors") or []
        if not isinstance(authors, list) or not all(isinstance(a, str) for a in authors):
            raise PathError(f"step {i} ({title!r}): authors must be a list of surnames")
        steps.append({"title": title.strip(), "authors": authors, "year": year, "note": str(s.get("note", ""))})
    return name.strip(), steps


def build_step(get_json, entries, index):
    entry = entries[index]
    work, reason = openalex.resolve(get_json, entry)
    if work is None:
        raise StepUnavailable(reason)
    refs = openalex.get_works(get_json, work.references[:40])
    built_on = sorted(refs, key=lambda w: -w.cited_by)[:3]
    led_to = openalex.citing(get_json, work.id, 3)
    return Step(index, len(entries), entry, work, built_on, led_to)
