"""Shapes taken from the 2026-10-15 OpenAlex spike, plus a fake `get_json` that behaves like the service."""


def inv(text):
    d = {}
    for i, w in enumerate(text.split()):
        d.setdefault(w, []).append(i)
    return d


def W(id, title, year, cited, type="article", refs=(), abstract="", oa=None, authors=("Ann Author",), doi=None,
      subfield="Finance"):
    return {"id": f"https://openalex.org/{id}", "display_name": title, "publication_year": year,
            "cited_by_count": cited, "type": type,
            "referenced_works": [f"https://openalex.org/{r}" for r in refs],
            "abstract_inverted_index": inv(abstract) if abstract else None,
            "open_access": {"is_oa": bool(oa), "oa_url": oa}, "doi": doi or f"https://doi.org/10.1/{id}",
            "authorships": [{"author": {"display_name": a}} for a in authors],
            "primary_topic": {"subfield": {"display_name": subfield}}}


class FakeOpenAlex:
    """Stand-in for openalex.http_get_json: answers title search, `openalex:` id lists and `cites:` queries."""

    def __init__(self, *works):
        self.works = {w["id"].rsplit("/", 1)[-1]: w for w in works}
        self.calls, self.fail = [], None

    def __call__(self, path, params):
        self.calls.append((path, dict(params)))
        if self.fail:
            raise self.fail
        flt = params.get("filter", "")
        n = params.get("per_page", 25)
        if "search" in params:
            q = params["search"].lower()
            res = [w for w in self.works.values()
                   if q in w["display_name"].lower() or w["display_name"].lower() in q]
            if flt.startswith("publication_year:"):
                lo, _, hi = flt.split(":")[1].partition("-")
                res = [w for w in res if int(lo) <= w["publication_year"] <= int(hi or lo)]
            return {"results": res[:n]}
        if flt.startswith("openalex:"):
            return {"results": [self.works[i] for i in flt[len("openalex:"):].split("|") if i in self.works]}
        if flt.startswith("cites:"):
            wid = flt[len("cites:"):]
            res = [w for w in self.works.values() if wid in [r.rsplit("/", 1)[-1] for r in w["referenced_works"]]]
            res.sort(key=lambda w: -w["cited_by_count"])
            return {"results": res[:n], "meta": {"count": len(res)}}
        raise AssertionError(f"unexpected query {path} {params}")


def make_step(work_json, built_on=(), led_to=(), index=0, total=1, entry=None):
    """A Step built directly from OpenAlex-shaped dicts (no service calls)."""
    import openalex
    import paths
    w = openalex.parse_work(work_json)
    return paths.Step(index, total, entry or {"title": w.title, "authors": [], "year": w.year, "note": ""},
                      w, [openalex.parse_work(x) for x in built_on], [openalex.parse_work(x) for x in led_to])
