"""OpenAlex client: look up landmark papers and their citation links. Free, no key.
Every function takes `get_json(path, params) -> dict` so tests inject a fake and never touch the internet."""
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from difflib import SequenceMatcher

BASE = "https://api.openalex.org"
FIELDS = ("id,display_name,publication_year,cited_by_count,type,referenced_works,abstract_inverted_index,"
          "open_access,authorships,doi,primary_topic")


class OpenAlexError(Exception):
    pass


@dataclass
class Work:
    id: str
    title: str
    year: int
    cited_by: int
    type: str
    abstract: str = ""
    oa_url: str = ""
    doi_url: str = ""
    authors: list = field(default_factory=list)
    references: list = field(default_factory=list)
    topic: str = ""


def reconstruct_abstract(inv):
    """OpenAlex stores abstracts as word -> positions; rebuild the text (empty when the work has none)."""
    if not inv:
        return ""
    words = {i: w for w, idxs in inv.items() for i in idxs}
    return " ".join(words[i] for i in sorted(words))


def tidy_title(t):
    """Old records are often SHOUTED in capitals; show those in title case."""
    letters = [c for c in t if c.isalpha()]
    return t.title() if letters and sum(c.isupper() for c in letters) / len(letters) > 0.8 else t


def parse_work(w):
    oa = w.get("open_access") or {}
    return Work(id=str(w.get("id", "")).rsplit("/", 1)[-1], title=tidy_title(w.get("display_name") or ""),
                year=w.get("publication_year") or 0, cited_by=w.get("cited_by_count") or 0,
                type=w.get("type") or "", abstract=reconstruct_abstract(w.get("abstract_inverted_index")),
                oa_url=(oa.get("oa_url") or "") if oa.get("is_oa") else "", doi_url=w.get("doi") or "",
                authors=[(a.get("author") or {}).get("display_name", "") for a in (w.get("authorships") or [])][:3],
                references=[str(x).rsplit("/", 1)[-1] for x in (w.get("referenced_works") or [])],
                topic=(((w.get("primary_topic") or {}).get("subfield")) or {}).get("display_name", ""))


def _norm(s):
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", s.lower()).split())


def _surname_match(work, surnames):
    last = {a.split()[-1].casefold() for a in work.authors if a.split()}
    return any(s.casefold() in last for s in surnames)


def resolve(get_json, entry):
    """Find the original landmark paper for a reading-list entry. Returns (Work, "") or (None, why-not).
    Only a confident match is accepted; reprints and book-chapter copies lose to the original article."""
    title, year, surnames = entry["title"], entry.get("year"), entry.get("authors") or []
    params = {"search": title, "per_page": 25, "sort": "cited_by_count:desc", "select": FIELDS}
    if year:
        params["filter"] = f"publication_year:{year - 1}-{year + 1}"
    works = [parse_work(w) for w in get_json("/works", params).get("results", [])]
    good = [w for w in works if SequenceMatcher(None, _norm(w.title), _norm(title)).ratio() >= 0.85]
    if not good:
        return None, f"not found in the citation data: {title!r}"
    if year:
        good = [w for w in good if abs(w.year - year) <= 1]
        if not good:
            return None, f"no match near {year}: {title!r}"
    if surnames:
        matching = [w for w in good if _surname_match(w, surnames)]
        if not matching:
            return None, f"author mismatch for {title!r}: expected {', '.join(surnames)}, found {', '.join(good[0].authors)}"
        good = matching
    good.sort(key=lambda w: (w.type != "article", -w.cited_by))
    return good[0], ""


def get_works(get_json, ids):
    out = []
    for i in range(0, len(ids), 50):
        chunk = ids[i:i + 50]
        r = get_json("/works", {"filter": "openalex:" + "|".join(chunk), "per_page": len(chunk), "select": FIELDS})
        out += [parse_work(w) for w in r.get("results", [])]
    return out


def citing(get_json, work_id, n=10):
    """The most-cited works that cite `work_id`."""
    r = get_json("/works", {"filter": f"cites:{work_id}", "sort": "cited_by_count:desc", "per_page": n, "select": FIELDS})
    return [parse_work(w) for w in r.get("results", [])]


def http_get_json(path, params, tries=3):
    url = BASE + path + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "research-digest/0.1"})
    err = "unknown"
    for i in range(tries):
        time.sleep(0.15)  # be polite to a free service
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code < 500 and e.code != 429:
                raise OpenAlexError(f"OpenAlex rejected the request: HTTP {e.code}") from None
            err = f"HTTP {e.code}"
        except (OSError, ValueError) as e:  # network trouble, timeouts, a broken reply
            err = type(e).__name__
        if i < tries - 1:
            time.sleep(2 ** (i + 1))
    raise OpenAlexError(f"OpenAlex unavailable after {tries} tries ({err})")
