"""Reading paths: a short, human-editable list of landmark papers, checked and connected with citation data."""
import tomllib
from dataclasses import asdict, dataclass

import openalex


class PathError(Exception):
    """The reading-path file is missing or malformed."""


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


def entry_key(entry):
    """The identity of a lesson (done or not). Editing authors does not change it."""
    return f"{entry['title']}|{entry['year']}"


def resolution_key(entry):
    """The identity of a match in the cache. Authors are part of it, so fixing them re-resolves the entry."""
    return f"{entry_key(entry)}|{','.join(sorted(a.casefold() for a in entry['authors']))}"


def _edges(get_json, w, members):
    """What `w` was built on and what it led to, at most three each, shown in story order (oldest first).
    Papers on the reading path come first; the rest are filled from the data, but only same-topic articles on the
    right side of time, so reprints, later copies and off-topic giants never appear."""
    seen = {openalex._norm(w.title)}

    def take(candidates, out):
        for c in candidates:
            norm = openalex._norm(c.title)
            if norm and norm not in seen and len(out) < 3:
                seen.add(norm)
                out.append(c)

    on_topic = lambda c: c.type == "article" and (not w.topic or c.topic == w.topic)  # noqa: E731
    built, led = [], []
    take(sorted((members[r] for r in w.references if r in members and members[r].year <= w.year),
                key=lambda x: -x.cited_by), built)
    if len(built) < 3:
        refs = openalex.get_works(get_json, [r for r in w.references[:40] if r not in members])
        take(sorted((r for r in refs if r.year <= w.year and on_topic(r)), key=lambda x: -x.cited_by), built)
    take(sorted((m for m in members.values() if w.id in m.references and m.year >= w.year and m.id != w.id),
                key=lambda x: -x.cited_by), led)
    if len(led) < 3:
        cites = openalex.citing(get_json, w.id, 10)
        take(sorted((c for c in cites if c.year >= w.year and on_topic(c) and c.id not in members),
                    key=lambda x: -x.cited_by), led)
    return sorted(built, key=lambda x: x.year), sorted(led, key=lambda x: x.year)


def load_steps(get_json, store, name, entries, persist=True):
    """Verify every entry against the citation data and connect them. Returns (steps, flagged): the verified steps
    in order, and (entry, reason) for each entry that could not be verified. Results are cached in the store, so
    later days need no outside calls. `persist=False` (a dry run) reads the cache but never writes it."""
    cache = store.get_path_cache(name)
    members, flagged = {}, []
    for e in entries:
        k = resolution_key(e)
        if k in cache:
            members[k] = openalex.Work(**cache[k]["work"])
            continue
        work, reason = openalex.resolve(get_json, e)
        if work is None:
            flagged.append((e, reason))
        else:
            members[k] = work
    by_id = {w.id: w for w in members.values()}
    steps = []
    for e in entries:
        k = resolution_key(e)
        if k not in members:
            continue
        if k in cache:
            built = [openalex.Work(**x) for x in cache[k]["built_on"]]
            led = [openalex.Work(**x) for x in cache[k]["led_to"]]
        else:
            built, led = _edges(get_json, members[k], by_id)
            if persist:
                store.put_path_cache(name, k, {"work": asdict(members[k]), "built_on": [asdict(x) for x in built],
                                               "led_to": [asdict(x) for x in led]})
        steps.append(Step(len(steps), 0, e, members[k], built, led))
    for s in steps:
        s.total = len(steps)
    return steps, flagged
