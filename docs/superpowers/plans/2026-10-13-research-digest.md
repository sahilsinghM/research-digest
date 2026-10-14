# Research Digest Agent Implementation Plan

> **Superseded in part (2026-10-13):** Tasks 1-4 are done and stand. Tasks 5-8 are replaced by the issues derived from `docs/prd/2026-10-13-research-digest-prd.md` (subscription via headless Claude Code instead of the Anthropic API).

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A cron-run Python script that fetches new papers, triages them with Haiku, deep-reads the best with Sonnet against a personal profile, and sends a Telegram digest.

**Architecture:** Linear pipeline (fetch, dedupe, prefilter, triage, pick with quotas, deep read, compose, send). Small single-purpose modules; every network or model call is injected into `agent.run()` so the pipeline is testable with fakes. State in SQLite.

**Tech Stack:** Python 3.11+ (stdlib `urllib`, `sqlite3`, `tomllib`), `defusedxml` for untrusted feeds, `anthropic` SDK, `pytest`.

**Spec:** `docs/superpowers/specs/2026-10-13-research-digest-design.md`

## Global Constraints

- Models: triage `claude-haiku-5-5`, analysis `claude-sonnet-5-5` (set in `config.toml`, never hard-coded).
- Telegram message limit 4096 characters; parse mode HTML; all model/source text escaped.
- Only send to the configured `TELEGRAM_CHAT_ID`.
- Quotas: finance 2, science 2, medical 3; `max_papers` 8; a quiet day gives a shorter digest, never padding.
- First run looks back 2 days; `last_success` advances only when a run completes.
- Daily cost cap in `config.toml`; stop and notify when hit.
- Papers are marked sent only after Telegram accepts the message.
- `profile.md`, `.env`, `state.db` are gitignored. No personal details in the repo, tests, or commit messages.
- Model must not invent numbers; medical output never prescribes; finance output never says buy/sell.
- Schedule: 07:00 IST daily via cron (01:30 UTC).

## Spec deviations (decided while planning; spec updated to match)

- SSRN has no public API and RePEc has no simple recent-papers feed: v1 covers NBER (RSS) for working papers. SSRN/RePEc deferred.
- Open-access full text in v1 is arXiv, bioRxiv and medRxiv PDFs, sent to Claude as PDF document blocks. PubMed Central and Unpaywall are deferred; everything else is abstract only.
- Medical journals come from PubMed only (whitelist by journal abbreviation), not Crossref, to avoid duplicates.
- Files split by responsibility: `sources.py`, `store.py`, `rank.py`, `llm.py`, `digest.py`, `agent.py`.

## Review Focus

Failure modes the spec implies but a straight reading would miss, most likely first. Each has a pinning test in the named task.

1. Paper with no abstract (Crossref often omits it): must parse to `abstract == ""`, be triaged on title, never crash. (Task 3, Task 5)
2. Model reply wrapped in ```` ```json ```` fences or preceded by prose: must still parse. (Task 5)
3. Titles or model text containing `<`, `&`, quotes: must be escaped, not break HTML parse mode. (Task 6)
4. Model returns oversized fields: every Telegram message stays at or under 4096 characters. (Task 6)
5. Run fails midway after some papers were sent: sent ones are not resent next run, `last_success` is not advanced. (Task 7)

---

### Task 1: Scaffolding, config, Paper type

**Files:**
- Create: `.gitignore`, `requirements.txt`, `pytest.ini`, `config.toml`, `profile.example.md`
- Create: `sources.py` (only the `Paper` dataclass for now)
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `sources.Paper(id, title, abstract, source, area, journal, url, published, kind, fulltext_url="", score=0.0)`; `config.toml` keys used by later tasks: `run.{lookback_days_first_run,max_papers,min_score,daily_cost_cap_usd}`, `models.{triage,analyse}`, `prices.<model>.{in,out}`, `quota.<area>`, `keywords.medical`, `[[arxiv]] area,q`, `[[journal]] name,issn,area`, `pubmed.journals`.

- [ ] **Step 1: Check Python and create the venv**

Run: `python3 --version && python3 -m venv .venv`
Expected: version 3.11 or higher. If lower, stop and tell the user.

- [ ] **Step 2: Write scaffolding files**

`.gitignore`:
```
.env
profile.md
state.db
.lock
agent.log
.venv/
__pycache__/
.pytest_cache/
```

`requirements.txt`:
```
anthropic
defusedxml
pytest
```

`pytest.ini`:
```
[pytest]
pythonpath = .
testpaths = tests
```

`profile.example.md`:
```
# Reader profile (copy to profile.md, which is gitignored)

Age/location/currency: ...
Work and money: income, debts, trading plans, risk appetite
Health: conditions and habits you want the digest to watch
Life events and goals: what is coming up, what you want more of
What to avoid: topics you do not want
```

`config.toml`:
```toml
[run]
lookback_days_first_run = 2
max_papers = 8
min_score = 5
daily_cost_cap_usd = 3.0

[models]
triage = "claude-haiku-5-5"
analyse = "claude-sonnet-5-5"

# USD per million tokens. Verify against current Anthropic pricing before the first live run.
[prices.claude-haiku-5-5]
in = 1.0
out = 5.0

[prices.claude-sonnet-5-5]
in = 3.0
out = 15.0

[quota]
finance = 2
science = 2
medical = 3

# Only medical items are keyword-prefiltered (PubMed is broad); Haiku triage does the real filtering.
[keywords]
medical = [
  "sleep", "insomnia", "diet", "nutrition", "obes", "weight", "cardio", "heart", "blood pressure",
  "cholesterol", "statin", "erectile", "ejaculat", "sexual", "urolog", "prostate", "testosterone",
  "liver", "hepat", "kidney", "renal", "skin", "acne", "dermat", "hair", "alopecia", "minoxidil",
  "finasteride", "depress", "anxiety", "mental health", "smok", "nicotine", "alcohol", "tinnitus",
  "pharyng", "microbio", "inflamm", "exercise",
]

# ponytail: each arXiv query sees only the newest 100; cs.* alone has hundreds a day. Split queries if it matters.
[[arxiv]]
area = "finance"
q = "cat:q-fin.* OR cat:econ.*"

[[arxiv]]
area = "science"
q = "cat:math.* OR cat:physics.* OR cat:cond-mat.* OR cat:q-bio.*"

[[arxiv]]
area = "science"
q = "cat:cs.*"

[[journal]]
name = "Nature"
issn = "0028-0836"
area = "science"

[[journal]]
name = "Science"
issn = "0036-8075"
area = "science"

[[journal]]
name = "Cell"
issn = "0092-8674"
area = "science"

[[journal]]
name = "PNAS"
issn = "0027-8424"
area = "science"

[[journal]]
name = "American Economic Review"
issn = "0002-8282"
area = "finance"

[[journal]]
name = "Quarterly Journal of Economics"
issn = "0033-5533"
area = "finance"

[[journal]]
name = "Journal of Political Economy"
issn = "0022-3808"
area = "finance"

[[journal]]
name = "Econometrica"
issn = "0012-9682"
area = "finance"

[[journal]]
name = "Journal of Finance"
issn = "0022-1082"
area = "finance"

[[journal]]
name = "Journal of Financial Economics"
issn = "0304-405X"
area = "finance"

[[journal]]
name = "Review of Financial Studies"
issn = "0893-9454"
area = "finance"

[pubmed]
journals = [
  "N Engl J Med", "Lancet", "JAMA", "BMJ", "Nat Med", "J Am Coll Cardiol", "Eur Heart J", "Circulation",
  "Gut", "Hepatology", "J Hepatol", "J Am Acad Dermatol", "Kidney Int", "Sleep", "JAMA Psychiatry",
  "Lancet Psychiatry", "Eur Urol", "J Urol", "J Sex Med", "Cochrane Database Syst Rev",
]
```

`sources.py`:
```python
"""Fetch new papers from free sources. fetch_* hit the network; parse_* are pure."""
from dataclasses import dataclass


@dataclass
class Paper:
    id: str
    title: str
    abstract: str
    source: str
    area: str  # "finance" | "science" | "medical"
    journal: str
    url: str
    published: str  # YYYY-MM-DD
    kind: str  # "peer" | "preprint"
    fulltext_url: str = ""
    score: float = 0.0
```

- [ ] **Step 3: Install and write the failing test**

Run: `.venv/bin/pip install -r requirements.txt`

`tests/test_config.py`:
```python
import tomllib


def load():
    with open("config.toml", "rb") as f:
        return tomllib.load(f)


def test_quota_areas():
    assert set(load()["quota"]) == {"finance", "science", "medical"}


def test_every_model_has_a_price():
    cfg = load()
    for model in cfg["models"].values():
        assert {"in", "out"} <= set(cfg["prices"][model])


def test_journals_well_formed():
    for j in load()["journal"]:
        assert j["area"] in {"finance", "science"} and len(j["issn"]) == 9
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/pytest -q`
Expected: 3 passed (config and Paper already exist, so these pass at once; the test guards later edits).

- [ ] **Step 5: Verify the ISSNs against Crossref**

Run:
```bash
for i in 0028-0836 0036-8075 0092-8674 0027-8424 0002-8282 0033-5533 0022-3808 0012-9682 0022-1082 0304-405X 0893-9454; do
  echo -n "$i  "; curl -s "https://api.crossref.org/journals/$i" | python3 -c "import sys,json; print(json.load(sys.stdin)['message']['title'])"; sleep 1; done
```
Expected: each line prints the matching journal title. Fix any wrong or erroring ISSN in `config.toml`.

- [ ] **Step 6: Commit**

```bash
git add .gitignore requirements.txt pytest.ini config.toml profile.example.md sources.py tests/test_config.py
git commit -m "feat: scaffolding, config and Paper type"
```

---

### Task 2: State store

**Files:**
- Create: `store.py`
- Test: `tests/test_store.py`

**Interfaces:**
- Consumes: `sources.Paper`.
- Produces: `Store(path)` with `since(lookback_days: int, now: datetime) -> datetime`, `record_success(ts: datetime) -> None`, `mark_sent(p: Paper) -> None`, `new_only(papers: list[Paper]) -> list[Paper]`. All datetimes are timezone-aware UTC.

- [ ] **Step 1: Write the failing test**

`tests/test_store.py`:
```python
from datetime import datetime, timedelta, timezone

from sources import Paper
from store import Store

NOW = datetime(2026, 10, 13, 1, 30, tzinfo=timezone.utc)


def P(id):
    return Paper(id=id, title="t", abstract="a", source="s", area="finance",
                 journal="j", url="u", published="2026-10-12", kind="peer")


def test_first_run_uses_lookback():
    assert Store(":memory:").since(2, NOW) == NOW - timedelta(days=2)


def test_since_is_last_success():
    s = Store(":memory:")
    s.record_success(NOW - timedelta(days=1))
    s.record_success(NOW)
    assert s.since(2, NOW + timedelta(days=5)) == NOW


def test_sent_papers_are_filtered():
    s = Store(":memory:")
    s.mark_sent(P("a"))
    assert [p.id for p in s.new_only([P("a"), P("b")])] == ["b"]


def test_mark_sent_twice_is_fine():
    s = Store(":memory:")
    s.mark_sent(P("a"))
    s.mark_sent(P("a"))
    assert s.new_only([P("a")]) == []
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/pytest tests/test_store.py -q`
Expected: FAIL, `ModuleNotFoundError: No module named 'store'`.

- [ ] **Step 3: Implement**

`store.py`:
```python
import sqlite3
from datetime import datetime, timedelta

SCHEMA = """
create table if not exists papers(id text primary key, title text, source text, score real, sent integer);
create table if not exists runs(ts text);
"""


class Store:
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.executescript(SCHEMA)

    def since(self, lookback_days, now):
        last = self.db.execute("select max(ts) from runs").fetchone()[0]
        return datetime.fromisoformat(last) if last else now - timedelta(days=lookback_days)

    def record_success(self, ts):
        self.db.execute("insert into runs values (?)", (ts.isoformat(),))
        self.db.commit()

    def mark_sent(self, p):
        self.db.execute("insert or replace into papers values (?,?,?,?,1)", (p.id, p.title, p.source, p.score))
        self.db.commit()

    # ponytail: the same paper under two ids (arXiv id vs later journal DOI) is not merged.
    def new_only(self, papers):
        sent = {r[0] for r in self.db.execute("select id from papers where sent=1")}
        return [p for p in papers if p.id not in sent]
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/pytest tests/test_store.py -q`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add store.py tests/test_store.py
git commit -m "feat: sqlite state store"
```

---

### Task 3: Sources

**Files:**
- Modify: `sources.py` (append below `Paper`; add imports at top)
- Test: `tests/test_sources.py`

**Interfaces:**
- Consumes: `Paper`; config keys from Task 1.
- Produces: `fetch_all(cfg: dict, since: date, today: date) -> tuple[list[Paper], list[str]]` (papers de-duplicated by id; second item is names of failed sources). Pure parsers: `parse_arxiv(xml, area)`, `parse_crossref(data, area)`, `parse_pubmed(xml, today)`, `parse_rxiv(data, server, area)`, `parse_nber(xml)`; each yields `Paper`.

- [ ] **Step 1: Write the failing tests**

`tests/test_sources.py`:
```python
from datetime import date

import sources
from sources import Paper, parse_arxiv, parse_crossref, parse_nber, parse_pubmed, parse_rxiv

ARXIV = b"""<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
 <entry><id>http://arxiv.org/abs/2610.01234v2</id><published>2026-10-12T17:59:59Z</published>
 <title>Pricing  Options
 with Rough Vol</title><summary> We study X.
 Results follow. </summary></entry></feed>"""

CROSSREF = {"message": {"items": [
    {"DOI": "10.1/x", "title": ["Good <i>paper</i> &amp; more"], "abstract": "<jats:p>Abs text</jats:p>",
     "container-title": ["Nature"], "URL": "https://doi.org/10.1/x", "created": {"date-time": "2026-10-12T01:02:03Z"}},
    {"DOI": "10.1/noabs", "title": ["No abstract here"], "container-title": ["Nature"],
     "created": {"date-time": "2026-10-12T01:02:03Z"}},
    {"DOI": "10.1/y", "title": [], "URL": "u", "created": {"date-time": "2026-10-12T00:00:00Z"}},
]}}

PUBMED = b"""<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>123</PMID><Article>
<Journal><Title>The Lancet</Title></Journal>
<ArticleTitle>Sleep and <i>BP</i></ArticleTitle>
<Abstract><AbstractText Label="A">Part one.</AbstractText><AbstractText>Part two.</AbstractText></Abstract>
</Article></MedlineCitation></PubmedArticle>
<PubmedArticle><MedlineCitation><PMID>124</PMID><Article><Journal><Title>JAMA</Title></Journal>
<ArticleTitle>Letter without abstract</ArticleTitle></Article></MedlineCitation></PubmedArticle></PubmedArticleSet>"""

RXIV = {"collection": [{"doi": "10.1101/2026.10.01.123", "title": "T", "abstract": "A",
                        "date": "2026-10-11", "version": "2"}]}

NBER = b"""<rss><channel><item><title>Rates and Risk</title><link>https://www.nber.org/papers/w1</link>
<description>Abstract here.</description><pubDate>Mon, 12 Oct 2026 00:00:00 GMT</pubDate></item></channel></rss>"""


def test_parse_arxiv():
    [p] = parse_arxiv(ARXIV, "finance")
    assert p.id == "arxiv:2610.01234"
    assert p.title == "Pricing Options with Rough Vol"
    assert p.abstract == "We study X. Results follow."
    assert p.kind == "preprint" and p.published == "2026-10-12"
    assert p.fulltext_url == "https://arxiv.org/pdf/2610.01234"


def test_parse_crossref_strips_markup_skips_untitled_and_allows_missing_abstract():
    ps = list(parse_crossref(CROSSREF, "science"))
    assert [p.id for p in ps] == ["doi:10.1/x", "doi:10.1/noabs"]
    assert ps[0].title == "Good paper & more" and ps[0].abstract == "Abs text" and ps[0].journal == "Nature"
    assert ps[1].abstract == "" and ps[1].url == "https://doi.org/10.1/noabs"


def test_parse_pubmed_joins_abstract_sections_and_allows_missing():
    a, b = parse_pubmed(PUBMED, date(2026, 10, 13))
    assert a.id == "pmid:123" and a.title == "Sleep and BP" and a.abstract == "Part one. Part two."
    assert a.journal == "The Lancet" and a.area == "medical" and a.kind == "peer"
    assert b.abstract == ""


def test_parse_rxiv_builds_pdf_url():
    [p] = parse_rxiv(RXIV, "medrxiv", "medical")
    assert p.id == "doi:10.1101/2026.10.01.123" and p.kind == "preprint"
    assert p.fulltext_url == "https://www.medrxiv.org/content/10.1101/2026.10.01.123v2.full.pdf"
    assert p.journal == "medRxiv"


def test_parse_nber():
    [p] = parse_nber(NBER)
    assert p.id == "nber:https://www.nber.org/papers/w1" and p.published == "2026-10-12" and p.area == "finance"


def test_fetch_all_survives_one_failing_source_and_dedupes(monkeypatch):
    def boom(*a, **k):
        raise OSError("down")

    def P(id):
        return Paper(id=id, title="t", abstract="", source="s", area="science", journal="j",
                     url="u", published="2026-10-12", kind="peer")

    monkeypatch.setattr(sources, "fetch_arxiv", boom)
    monkeypatch.setattr(sources, "fetch_crossref", lambda *a, **k: [P("doi:1"), P("doi:1")])
    monkeypatch.setattr(sources, "fetch_pubmed", lambda *a, **k: [])
    monkeypatch.setattr(sources, "fetch_rxiv", lambda *a, **k: [])
    monkeypatch.setattr(sources, "fetch_nber", lambda *a, **k: [])
    cfg = {"arxiv": [{"area": "finance", "q": "x"}], "journal": [{"name": "N", "issn": "1", "area": "science"}],
           "pubmed": {"journals": ["a"]}}
    papers, failed = sources.fetch_all(cfg, date(2026, 10, 12), date(2026, 10, 13))
    assert [p.id for p in papers] == ["doi:1"] and failed == ["arxiv/finance"]
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/bin/pytest tests/test_sources.py -q`
Expected: FAIL, `ImportError: cannot import name 'parse_arxiv'`.

- [ ] **Step 3: Implement**

Replace the top of `sources.py` (imports) and append the rest. Final file:

```python
"""Fetch new papers from free sources. fetch_* hit the network; parse_* are pure."""
import html
import json
import logging
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import defusedxml.ElementTree as ET  # feeds are untrusted XML: no entity expansion
from dataclasses import dataclass
from email.utils import parsedate_to_datetime

log = logging.getLogger(__name__)
ATOM = "{http://www.w3.org/2005/Atom}"
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
RXIV_NAMES = {"biorxiv": "bioRxiv", "medrxiv": "medRxiv"}


@dataclass
class Paper:
    id: str
    title: str
    abstract: str
    source: str
    area: str  # "finance" | "science" | "medical"
    journal: str
    url: str
    published: str  # YYYY-MM-DD
    kind: str  # "peer" | "preprint"
    fulltext_url: str = ""
    score: float = 0.0


def get(url, params=None, tries=3):
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "research-digest/0.1"})
    for i in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read()
        except (urllib.error.URLError, TimeoutError):
            if i == tries - 1:
                raise
            time.sleep(2 ** i)


def _text(s):
    """Strip tags/entities and collapse whitespace."""
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", s or "")).split())


def parse_arxiv(xml, area):
    for e in ET.fromstring(xml).findall(ATOM + "entry"):
        aid = re.sub(r"v\d+$", "", e.findtext(ATOM + "id").rsplit("/abs/", 1)[-1])
        yield Paper(id=f"arxiv:{aid}", title=_text(e.findtext(ATOM + "title")),
                    abstract=_text(e.findtext(ATOM + "summary")), source="arxiv", area=area,
                    journal="arXiv", url=f"https://arxiv.org/abs/{aid}",
                    published=e.findtext(ATOM + "published")[:10], kind="preprint",
                    fulltext_url=f"https://arxiv.org/pdf/{aid}")


def fetch_arxiv(q, area, since, n=100):
    time.sleep(3)  # arXiv API etiquette
    xml = get("https://export.arxiv.org/api/query", {"search_query": q, "sortBy": "submittedDate",
                                                      "sortOrder": "descending", "max_results": n})
    return [p for p in parse_arxiv(xml, area) if p.published >= since.isoformat()]


def parse_crossref(data, area):
    for it in data["message"]["items"]:
        title = _text((it.get("title") or [""])[0])
        if not title:
            continue
        yield Paper(id="doi:" + it["DOI"], title=title, abstract=_text(it.get("abstract")),
                    source="crossref", area=area, journal=_text((it.get("container-title") or [""])[0]),
                    url=it.get("URL") or "https://doi.org/" + it["DOI"],
                    published=it["created"]["date-time"][:10], kind="peer")


def fetch_crossref(issn, area, since):
    data = json.loads(get(f"https://api.crossref.org/journals/{issn}/works", {
        "filter": f"from-created-date:{since.isoformat()}", "rows": 50,
        "select": "DOI,title,abstract,container-title,URL,created"}))
    return list(parse_crossref(data, area))


def parse_pubmed(xml, today):
    for a in ET.fromstring(xml).findall("PubmedArticle"):
        pmid = a.findtext(".//PMID")
        t = a.find(".//ArticleTitle")
        yield Paper(id=f"pmid:{pmid}", title=_text("".join(t.itertext())) if t is not None else "",
                    abstract=" ".join(_text("".join(x.itertext())) for x in a.findall(".//AbstractText")),
                    source="pubmed", area="medical", journal=a.findtext(".//Journal/Title") or "",
                    url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/", published=today.isoformat(), kind="peer")


def fetch_pubmed(journals, since, today):
    term = "(" + " OR ".join(f'"{j}"[ta]' for j in journals) + ")"
    ids = json.loads(get(EUTILS + "esearch.fcgi", {
        "db": "pubmed", "term": term, "datetype": "edat", "retmode": "json", "retmax": 300,
        "mindate": since.strftime("%Y/%m/%d"), "maxdate": today.strftime("%Y/%m/%d")}))["esearchresult"]["idlist"]
    if not ids:
        return []
    time.sleep(0.4)  # NCBI allows ~3 requests/second without a key
    xml = get(EUTILS + "efetch.fcgi", {"db": "pubmed", "id": ",".join(ids), "retmode": "xml"})
    return [p for p in parse_pubmed(xml, today) if p.title]


def parse_rxiv(data, server, area):
    for r in data.get("collection", []):
        yield Paper(id="doi:" + r["doi"], title=_text(r["title"]), abstract=_text(r.get("abstract")),
                    source=server, area=area, journal=RXIV_NAMES[server], url="https://doi.org/" + r["doi"],
                    published=r["date"], kind="preprint",
                    fulltext_url=f"https://www.{server}.org/content/{r['doi']}v{r.get('version', '1')}.full.pdf")


def fetch_rxiv(server, area, since, today, pages=3):
    out = []
    for i in range(pages):
        data = json.loads(get(f"https://api.biorxiv.org/details/{server}/{since}/{today}/{i * 100}"))
        out += parse_rxiv(data, server, area)
        if len(data.get("collection", [])) < 100:
            break
    return out


def parse_nber(xml):
    for it in ET.fromstring(xml).iter("item"):
        link = it.findtext("link")
        yield Paper(id="nber:" + link, title=_text(it.findtext("title")), abstract=_text(it.findtext("description")),
                    source="nber", area="finance", journal="NBER working paper", url=link,
                    published=parsedate_to_datetime(it.findtext("pubDate")).date().isoformat(), kind="preprint")


def fetch_nber(since):
    xml = get("https://www.nber.org/rss/new.xml")
    return [p for p in parse_nber(xml) if p.published >= since.isoformat()]


def fetch_all(cfg, since, today):
    """Run every source independently. Returns (papers deduped by id, names of failed sources)."""
    jobs = []
    for q in cfg["arxiv"]:
        jobs.append((f"arxiv/{q['area']}", lambda q=q: fetch_arxiv(q["q"], q["area"], since)))
    for j in cfg["journal"]:
        jobs.append((j["name"], lambda j=j: fetch_crossref(j["issn"], j["area"], since)))
    jobs.append(("pubmed", lambda: fetch_pubmed(cfg["pubmed"]["journals"], since, today)))
    for server, area in (("biorxiv", "science"), ("medrxiv", "medical")):
        jobs.append((server, lambda s=server, a=area: fetch_rxiv(s, a, since, today)))
    jobs.append(("nber", lambda: fetch_nber(since)))
    papers, failed = {}, []
    for name, fn in jobs:
        try:
            for p in fn():
                papers.setdefault(p.id, p)
        except Exception as e:
            log.warning("source %s failed: %s", name, e)
            failed.append(name)
    return list(papers.values()), failed
```

- [ ] **Step 4: Run to verify they pass**

Run: `.venv/bin/pytest tests/test_sources.py -q`
Expected: 6 passed.

- [ ] **Step 5: Smoke-test the real sources (network)**

Run:
```bash
.venv/bin/python - <<'EOF'
import tomllib, logging
from datetime import date, timedelta
import sources
logging.basicConfig(level=logging.WARNING)
cfg = tomllib.load(open("config.toml", "rb"))
today = date.today()
papers, failed = sources.fetch_all(cfg, today - timedelta(days=2), today)
print(len(papers), "papers; failed:", failed)
for a in ("finance", "science", "medical"):
    print(a, sum(p.area == a for p in papers))
EOF
```
Expected: papers in all three areas. If a source is in `failed` repeatedly (most likely NBER, whose RSS URL is unverified), read the warning, fix the URL or parser, and re-run. If NBER cannot be fixed in a few minutes, remove its job from `fetch_all` and note it in the commit message.

- [ ] **Step 6: Commit**

```bash
git add sources.py tests/test_sources.py
git commit -m "feat: paper sources (arXiv, Crossref, PubMed, bioRxiv/medRxiv, NBER)"
```

---

### Task 4: Prefilter and quota selection

**Files:**
- Create: `rank.py`
- Test: `tests/test_rank.py`

**Interfaces:**
- Consumes: `Paper`.
- Produces: `prefilter(papers, keywords) -> list[Paper]` (only `area == "medical"` papers are keyword-filtered); `pick(papers, quota: dict[str,int], max_papers: int, min_score: float) -> list[Paper]` (highest score first).

- [ ] **Step 1: Write the failing test**

`tests/test_rank.py`:
```python
from rank import pick, prefilter
from sources import Paper


def P(id, area="finance", score=0.0, title="t", abstract=""):
    return Paper(id=id, title=title, abstract=abstract, source="s", area=area, journal="j",
                 url="u", published="2026-10-12", kind="peer", score=score)


def test_prefilter_only_filters_medical():
    ps = [P("a", "finance", title="Rates"), P("b", "medical", title="Sleep apnoea trial"),
          P("c", "medical", title="Unrelated surgery study")]
    assert [p.id for p in prefilter(ps, ["sleep"])] == ["a", "b"]


def test_prefilter_matches_abstract_case_insensitively():
    assert prefilter([P("b", "medical", abstract="Effects on SLEEP")], ["sleep"])


def test_pick_respects_quota_min_score_and_order():
    ps = [P("f1", "finance", 9), P("f2", "finance", 8), P("f3", "finance", 7),
          P("s1", "science", 4), P("m1", "medical", 6)]
    got = pick(ps, {"finance": 2, "science": 2, "medical": 3}, max_papers=8, min_score=5)
    assert [p.id for p in got] == ["f1", "f2", "m1"]


def test_pick_caps_total():
    ps = [P(f"f{i}", "finance", 9 - i * 0.1) for i in range(5)] + [P("m", "medical", 7)]
    got = pick(ps, {"finance": 5, "medical": 3}, max_papers=3, min_score=5)
    assert [p.id for p in got] == ["f0", "f1", "f2"]


def test_pick_nothing_when_all_below_min():
    assert pick([P("a", score=2)], {"finance": 2}, 8, 5) == []
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/pytest tests/test_rank.py -q`
Expected: FAIL, `ModuleNotFoundError: No module named 'rank'`.

- [ ] **Step 3: Implement**

`rank.py`:
```python
# ponytail: substring match is crude ("hair" hits "chair"); Haiku triage cleans up the false positives.
def prefilter(papers, keywords):
    kw = [k.lower() for k in keywords]
    return [p for p in papers
            if p.area != "medical" or any(k in f"{p.title} {p.abstract}".lower() for k in kw)]


def pick(papers, quota, max_papers, min_score):
    ranked = sorted((p for p in papers if p.score >= min_score), key=lambda p: -p.score)
    chosen = []
    for area, n in quota.items():
        chosen += [p for p in ranked if p.area == area][:n]
    chosen.sort(key=lambda p: -p.score)
    return chosen[:max_papers]
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/pytest tests/test_rank.py -q`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add rank.py tests/test_rank.py
git commit -m "feat: medical keyword prefilter and quota selection"
```

---

### Task 5: LLM triage, deep read, teach, budget

**Files:**
- Create: `llm.py`
- Test: `tests/test_llm.py`

**Interfaces:**
- Consumes: `Paper`; an Anthropic-like `client` exposing `client.messages.create(model=, max_tokens=, system=, messages=)` returning an object with `.content[0].text` and `.usage.input_tokens/.output_tokens`.
- Produces:
  - `class BudgetExceeded(Exception)`
  - `Budget(cap_usd: float, prices: dict)` with `.spent` and `.add(model: str, usage)`; raises `BudgetExceeded` once `spent > cap`. `prices[model]` has `"in"` and `"out"` (USD per million tokens).
  - `parse_json(text: str)` returns parsed JSON; raises `ValueError` if none.
  - `triage(client, model, papers, profile, budget, batch=20) -> None` sets `p.score` on every paper (0.0 if the model did not score it).
  - `deep_read(client, model, paper, profile, budget) -> dict | None` with string keys `did, found, evidence, for_you, action, for_world`; `None` if the model never returns valid JSON.
  - `teach(client, model, done: list[tuple[Paper, dict]], profile, budget) -> dict | None` with keys `name, explain, example`.

- [ ] **Step 1: Write the failing tests**

`tests/test_llm.py`:
```python
import json
import types

import anthropic
import httpx
import pytest

from llm import Budget, BudgetExceeded, deep_read, parse_json, teach, triage
from sources import Paper

PRICES = {"m": {"in": 1.0, "out": 5.0}}


class FakeClient:
    """Replays canned replies in order; an Exception instance is raised instead."""

    def __init__(self, *replies):
        self.replies, self.calls = list(replies), []
        self.messages = self

    def create(self, **kw):
        self.calls.append(kw)
        r = self.replies.pop(0)
        if isinstance(r, Exception):
            raise r
        return types.SimpleNamespace(content=[types.SimpleNamespace(text=r)],
                                     usage=types.SimpleNamespace(input_tokens=1000, output_tokens=500))


def P(id, fulltext=""):
    return Paper(id=id, title="T " + id, abstract="", source="s", area="finance", journal="J",
                 url="u", published="2026-10-12", kind="preprint", fulltext_url=fulltext)


def B(cap=10.0):
    return Budget(cap, PRICES)


def bad_request():
    resp = httpx.Response(400, request=httpx.Request("POST", "http://x"))
    return anthropic.BadRequestError("bad pdf", response=resp, body=None)


def test_parse_json_plain_fenced_and_prose():
    assert parse_json('[{"a": 1}]') == [{"a": 1}]
    assert parse_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json('Here you go:\n[{"a": 1}]\nHope that helps') == [{"a": 1}]
    with pytest.raises(ValueError):
        parse_json("no json at all")


def test_budget_raises_when_cap_exceeded():
    b = Budget(0.001, PRICES)
    usage = types.SimpleNamespace(input_tokens=1000, output_tokens=500)
    with pytest.raises(BudgetExceeded):
        b.add("m", usage)
    assert b.spent == pytest.approx(0.0035)


def test_triage_scores_and_defaults_missing_to_zero():
    ps = [P("a"), P("b")]  # abstracts are empty: must still work
    triage(FakeClient('```json\n[{"id": "a", "score": 8.5}]\n```'), "m", ps, "profile", B())
    assert (ps[0].score, ps[1].score) == (8.5, 0.0)


def test_triage_batches_of_20():
    ps = [P(str(i)) for i in range(25)]
    c = FakeClient("[]", "[]")
    triage(c, "m", ps, "profile", B())
    assert len(c.calls) == 2


def test_triage_survives_garbage_twice():
    ps = [P("a")]
    c = FakeClient("nope", "still nope")
    triage(c, "m", ps, "profile", B())
    assert ps[0].score == 0.0 and len(c.calls) == 2


def test_triage_puts_profile_in_system_prompt():
    c = FakeClient("[]")
    triage(c, "m", [P("a")], "I AM THE PROFILE", B())
    assert "I AM THE PROFILE" in c.calls[0]["system"]


ANALYSIS = {"did": "d", "found": "f", "evidence": "e", "for_you": "y", "action": "a", "for_world": "w"}


def test_deep_read_returns_dict_and_sends_pdf_when_available():
    c = FakeClient(json.dumps(ANALYSIS))
    assert deep_read(c, "m", P("a", "https://x/p.pdf"), "profile", B()) == ANALYSIS
    blocks = c.calls[0]["messages"][0]["content"]
    assert blocks[0]["type"] == "document" and blocks[0]["source"]["url"] == "https://x/p.pdf"


def test_deep_read_falls_back_to_abstract_when_pdf_rejected():
    p = P("a", "https://x/p.pdf")
    c = FakeClient(bad_request(), json.dumps(ANALYSIS))
    assert deep_read(c, "m", p, "profile", B()) == ANALYSIS
    assert p.fulltext_url == ""
    assert all(b["type"] == "text" for b in c.calls[1]["messages"][0]["content"])


def test_deep_read_none_when_json_never_parses():
    assert deep_read(FakeClient("x", "y"), "m", P("a"), "profile", B()) is None


def test_teach_returns_concept():
    t = {"name": "Drawdown", "explain": "e", "example": "x"}
    assert teach(FakeClient(json.dumps(t)), "m", [(P("a"), ANALYSIS)], "profile", B()) == t
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/bin/pytest tests/test_llm.py -q`
Expected: FAIL, `ModuleNotFoundError: No module named 'llm'`.

- [ ] **Step 3: Implement**

`llm.py`:
```python
import json

import anthropic


class BudgetExceeded(Exception):
    pass


class Budget:
    def __init__(self, cap_usd, prices):
        self.cap, self.prices, self.spent = cap_usd, prices, 0.0

    def add(self, model, usage):
        p = self.prices[model]
        self.spent += (usage.input_tokens * p["in"] + usage.output_tokens * p["out"]) / 1e6
        if self.spent > self.cap:
            raise BudgetExceeded(f"spent ${self.spent:.2f} > cap ${self.cap:.2f}")


def parse_json(text):
    """Parse JSON from a model reply that may carry code fences or prose around it."""
    s = text.strip()
    if "```" in s:
        s = s.split("```", 2)[1]
        s = s[4:] if s.startswith("json") else s
    starts = [i for i in (s.find("["), s.find("{")) if i != -1]
    if not starts:
        raise ValueError("no JSON in reply")
    start = min(starts)
    end = max(s.rfind("]"), s.rfind("}"))
    return json.loads(s[start:end + 1])


def ask(client, model, system, content, budget, max_tokens=3000):
    """One call, one retry if the reply is not valid JSON. Returns parsed JSON or None."""
    for _ in range(2):
        r = client.messages.create(model=model, max_tokens=max_tokens, system=system,
                                   messages=[{"role": "user", "content": content}])
        budget.add(model, r.usage)
        try:
            return parse_json(r.content[0].text)
        except ValueError:  # json.JSONDecodeError is a ValueError
            continue
    return None


TRIAGE = """You triage new research papers for one specific reader.

READER PROFILE:
{profile}

Give each paper an overall score from 0 to 10 combining:
(1) fit with the reader's topics, (2) usefulness to THIS reader given the profile, (3) evidence quality
(peer-reviewed beats preprint; randomized trials and meta-analyses beat observational beat animal or lab work;
large samples beat small).
Be harsh: most papers should score below 5. Reserve 8 and above for clearly important, well-evidenced work.
Reply with ONLY a JSON array: [{{"id": "<id exactly as given>", "score": <number>}}]"""

DEEP = """You analyse one research paper for one specific reader and explain it plainly.

READER PROFILE:
{profile}

Rules:
- Use only facts and numbers present in the supplied text. If a number is not there, do not state one.
- If you only have the abstract, say what cannot be judged from it.
- Medical topics: never prescribe or diagnose. Say what the evidence suggests and when to ask a doctor.
- Finance topics: never recommend buying or selling. Describe implications and risks.
- Be honest when the paper is weak, preliminary, or irrelevant to this reader.
Reply with ONLY a JSON object whose values are short plain-text strings:
{{"did": what the researchers did, "found": what they found,
"evidence": study design, sample size, effect size, limitations,
"for_you": why it matters to this reader, "action": one concrete step or "Nothing to do yet",
"for_world": why it matters more broadly}}"""

TEACH = """You are a patient teacher for one specific reader.

READER PROFILE:
{profile}

From the papers below pick ONE concept they assume that this reader would benefit from understanding.
Explain it simply in at most 150 words, then give one worked example tied to the reader's situation.
Reply with ONLY a JSON object: {{"name": ..., "explain": ..., "example": ...}}"""


def triage(client, model, papers, profile, budget, batch=20):
    scores = {}
    for i in range(0, len(papers), batch):
        rows = [{"id": p.id, "title": p.title, "journal": p.journal, "type": p.kind, "area": p.area,
                 "abstract": p.abstract[:1200]} for p in papers[i:i + batch]]
        out = ask(client, model, TRIAGE.format(profile=profile), json.dumps(rows), budget)
        for row in out or []:
            try:
                scores[row["id"]] = float(row["score"])
            except (KeyError, TypeError, ValueError):
                continue
    for p in papers:
        p.score = scores.get(p.id, 0.0)


def deep_read(client, model, p, profile, budget):
    text = (f"Title: {p.title}\nJournal: {p.journal}\nType: {p.kind}\n"
            f"Abstract: {p.abstract or '(none available)'}")
    system = DEEP.format(profile=profile)
    blocks = [{"type": "text", "text": text}]
    if p.fulltext_url:
        doc = {"type": "document", "source": {"type": "url", "url": p.fulltext_url}}
        try:
            return ask(client, model, system, [doc] + blocks, budget)
        except anthropic.BadRequestError:  # unreadable or oversized PDF: fall back to the abstract
            p.fulltext_url = ""
    return ask(client, model, system, blocks, budget)


def teach(client, model, done, profile, budget):
    papers = [{"title": p.title, "found": a.get("found", "")} for p, a in done]
    return ask(client, model, TEACH.format(profile=profile), json.dumps(papers), budget, max_tokens=1500)
```

- [ ] **Step 4: Run to verify they pass**

Run: `.venv/bin/pytest tests/test_llm.py -q`
Expected: 10 passed.

- [ ] **Step 5: Commit**

```bash
git add llm.py tests/test_llm.py
git commit -m "feat: LLM triage, deep read, teach, cost budget"
```

---

### Task 6: Digest formatting and Telegram

**Files:**
- Create: `digest.py`
- Test: `tests/test_digest.py`

**Interfaces:**
- Consumes: `Paper`, analysis dicts from Task 5.
- Produces: `clip(s, n)`, `split(text, limit=4096) -> list[str]`, `paper_msg(p, a) -> str`, `header_msg(done, n_scanned, day: str, notes=()) -> str`, `teach_msg(t) -> str`, `class TelegramError(Exception)`, `send(token, chat_id, text, post=_post) -> None` (splits to 4096, falls back to plain text if HTML is rejected). `post(token, chat_id, text, mode)` is the injectable transport.

- [ ] **Step 1: Write the failing tests**

`tests/test_digest.py`:
```python
from digest import TelegramError, header_msg, paper_msg, send, split, teach_msg
from sources import Paper


def P(title="T", kind="preprint", fulltext="", area="finance", score=7.0):
    return Paper(id="x", title=title, abstract="", source="s", area=area, journal="J & K",
                 url="https://e.com/?a=1&b=2", published="2026-10-12", kind=kind,
                 fulltext_url=fulltext, score=score)


A = {"did": "d", "found": "found it", "evidence": "n=10", "for_you": "mine", "action": "act", "for_world": "all"}


def test_paper_msg_escapes_html_in_title_model_text_and_url():
    a = dict(A, found="x < y & z")
    m = paper_msg(P(title="A < B & C"), a)
    assert "A &lt; B &amp; C" in m and "x &lt; y &amp; z" in m
    assert "A < B" not in m and 'href="https://e.com/?a=1&amp;b=2"' in m


def test_paper_msg_stays_under_limit_with_huge_fields():
    huge = {k: "x" * 5000 for k in A}
    assert len(paper_msg(P(title="t" * 5000), huge)) <= 4096


def test_badges():
    assert "Preprint · abstract only" in paper_msg(P(kind="preprint"), A)
    assert "Peer-reviewed · abstract only" in paper_msg(P(kind="peer"), A)
    assert "Preprint · full text" in paper_msg(P(kind="preprint", fulltext="https://x/p.pdf"), A)


def test_split_short_text_unchanged():
    assert split("hello") == ["hello"]


def test_split_long_text_prefers_newlines_and_respects_limit():
    text = "\n".join("line %d" % i * 3 for i in range(2000))
    parts = split(text)
    assert len(parts) > 1 and all(len(p) <= 4096 for p in parts)
    assert "".join(parts).replace("\n", "") == text.replace("\n", "")


def test_split_text_without_newlines_hard_splits():
    parts = split("y" * 10000)
    assert [len(p) for p in parts] == [4096, 4096, 1808]


def test_header_counts_areas_and_names_top_paper_and_notes():
    done = [(P(title="Top one", area="medical", score=9), A), (P(title="Other", area="finance", score=6), A)]
    h = header_msg(done, 120, "2026-10-13", ["sources failed: nber"])
    assert "2 papers" in h and "1 medical" in h and "1 finance" in h
    assert "Top one" in h and "120" in h and "sources failed: nber" in h


def test_teach_msg_escapes():
    m = teach_msg({"name": "P&L", "explain": "a<b", "example": "c"})
    assert "P&amp;L" in m and "a&lt;b" in m


def test_send_falls_back_to_plain_text_when_html_rejected():
    calls = []

    def post(token, chat, text, mode):
        calls.append((text, mode))
        if mode == "HTML":
            raise TelegramError("400: can't parse entities")

    send("tok", "chat", "<b>Hi</b> there", post=post)
    assert calls == [("<b>Hi</b> there", "HTML"), ("Hi there", None)]


def test_send_splits_long_messages():
    calls = []
    send("t", "c", "z" * 9000, post=lambda t, c, text, mode: calls.append(text))
    assert len(calls) == 3
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/bin/pytest tests/test_digest.py -q`
Expected: FAIL, `ModuleNotFoundError: No module named 'digest'`.

- [ ] **Step 3: Implement**

`digest.py`:
```python
import json
import re
import time
import urllib.error
import urllib.request
from collections import Counter
from html import escape

LIMIT = 4096


class TelegramError(Exception):
    pass


def clip(s, n):
    s = str(s or "")
    return s if len(s) <= n else s[:n - 1] + "…"


def split(text, limit=LIMIT):
    """Chunks of at most `limit` chars, cutting at a newline when one is reasonably close."""
    parts = []
    while len(text) > limit:
        cut = text.rfind("\n", 0, limit)
        if cut < limit // 2:
            cut = limit
        parts.append(text[:cut])
        text = text[cut:].lstrip("\n")
    return parts + [text]


def _badge(p):
    kind = "Preprint" if p.kind == "preprint" else "Peer-reviewed"
    return f"{kind} · {'full text' if p.fulltext_url else 'abstract only'}"


def paper_msg(p, a):
    # Field clips keep one paper under 4096 even if the model rambles; split() is only the safety net.
    return (f"<b>{escape(clip(p.title, 250))}</b>\n"
            f"{escape(clip(p.journal, 100))} · {_badge(p)}\n"
            f'<a href="{escape(p.url, quote=True)}">Open paper</a>\n\n'
            f"{escape(clip(a.get('found'), 500))}\n\n"
            f"<b>For you:</b> {escape(clip(a.get('for_you'), 500))}\n"
            f"<b>Do:</b> {escape(clip(a.get('action'), 300))}\n"
            f"<b>World:</b> {escape(clip(a.get('for_world'), 300))}\n"
            f"<i>Evidence: {escape(clip(a.get('evidence'), 400))}</i>")


def header_msg(done, n_scanned, day, notes=()):
    counts = ", ".join(f"{n} {area}" for area, n in Counter(p.area for p, _ in done).items())
    top = max(done, key=lambda d: d[0].score)[0]
    lines = [f"<b>Research digest {escape(day)}</b>",
             f"{len(done)} papers ({counts}) from {n_scanned} new",
             f"Most important: {escape(clip(top.title, 200))}"]
    lines += [f"<i>{escape(n)}</i>" for n in notes]
    return "\n".join(lines)


def teach_msg(t):
    return (f"<b>Today's concept: {escape(clip(t.get('name'), 100))}</b>\n\n"
            f"{escape(clip(t.get('explain'), 1500))}\n\n"
            f"<i>Example:</i> {escape(clip(t.get('example'), 1000))}")


def _post(token, chat_id, text, mode):
    body = {"chat_id": chat_id, "text": text, "disable_web_page_preview": True}
    if mode:
        body["parse_mode"] = mode
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage",
                                 json.dumps(body).encode(), {"Content-Type": "application/json"})
    for _ in range(3):
        try:
            urllib.request.urlopen(req, timeout=30).read()
            return
        except urllib.error.HTTPError as e:
            data = json.loads(e.read() or b"{}")
            if e.code == 429:
                time.sleep(data.get("parameters", {}).get("retry_after", 5))
                continue
            raise TelegramError(f"{e.code}: {data.get('description')}") from None
    raise TelegramError("rate limited")


def send(token, chat_id, text, post=_post):
    for chunk in split(text):
        try:
            post(token, chat_id, chunk, "HTML")
        except TelegramError:  # bad markup somewhere: deliver as plain text rather than lose it
            post(token, chat_id, re.sub(r"<[^>]+>", "", chunk), None)
```

- [ ] **Step 4: Run to verify they pass**

Run: `.venv/bin/pytest tests/test_digest.py -q`
Expected: 10 passed.

- [ ] **Step 5: Commit**

```bash
git add digest.py tests/test_digest.py
git commit -m "feat: digest formatting and Telegram delivery"
```

---

### Task 7: Pipeline orchestration

**Files:**
- Create: `agent.py`
- Test: `tests/test_agent.py`

**Interfaces:**
- Consumes: everything above.
- Produces: `run(cfg, profile, store, client, fetch, send, now, dry_run=False) -> None` where `fetch(cfg, since: date, today: date) -> (papers, failed)` and `send(text: str) -> None`; `main(argv=None) -> int` (0 ok or lock held, 1 failure).

- [ ] **Step 1: Write the failing tests**

`tests/test_agent.py`:
```python
import json
import tomllib
import types
from datetime import datetime, timedelta, timezone

import pytest

from agent import run
from llm import BudgetExceeded
from sources import Paper
from store import Store

NOW = datetime(2026, 10, 13, 1, 30, tzinfo=timezone.utc)
CFG = tomllib.load(open("config.toml", "rb"))
ANALYSIS = json.dumps({"did": "d", "found": "f", "evidence": "e", "for_you": "y", "action": "a", "for_world": "w"})
TEACH = json.dumps({"name": "Drawdown", "explain": "e", "example": "x"})


class FakeClient:
    def __init__(self, *replies):
        self.replies, self.calls = list(replies), []
        self.messages = self

    def create(self, **kw):
        self.calls.append(kw)
        return types.SimpleNamespace(content=[types.SimpleNamespace(text=self.replies.pop(0))],
                                     usage=types.SimpleNamespace(input_tokens=100, output_tokens=100))


def P(id, area):
    return Paper(id=id, title="Title " + id, abstract="sleep study" if area == "medical" else "abs",
                 source="s", area=area, journal="J", url="https://e.com/" + id,
                 published="2026-10-12", kind="peer")


def fetch_of(*papers, failed=()):
    return lambda cfg, since, today: (list(papers), list(failed))


def triage(**scores):
    return json.dumps([{"id": k, "score": v} for k, v in scores.items()])


def test_happy_path_sends_header_papers_teach_and_records():
    store, sent = Store(":memory:"), []
    papers = [P("a", "finance"), P("b", "medical")]
    client = FakeClient(triage(a=9, b=8), ANALYSIS, ANALYSIS, TEACH)
    run(CFG, "profile", store, client, fetch_of(*papers), sent.append, NOW)
    assert len(sent) == 4
    assert "Research digest" in sent[0] and "Title a" in sent[1] and "Title b" in sent[2] and "Drawdown" in sent[3]
    assert store.new_only(papers) == []
    assert store.since(2, NOW + timedelta(days=9)) == NOW


def test_dry_run_writes_nothing():
    store, sent = Store(":memory:"), []
    papers = [P("a", "finance")]
    run(CFG, "profile", store, FakeClient(triage(a=9), ANALYSIS, TEACH), fetch_of(*papers), sent.append, NOW, dry_run=True)
    assert len(sent) == 3 and store.new_only(papers) == papers
    assert store.since(2, NOW) == NOW - timedelta(days=2)


def test_quiet_day_sends_one_short_message_and_records_success():
    store, sent = Store(":memory:"), []
    run(CFG, "profile", store, FakeClient(triage(a=2)), fetch_of(P("a", "finance")), sent.append, NOW)
    assert len(sent) == 1 and "Nothing worth" in sent[0]
    assert store.since(2, NOW + timedelta(days=9)) == NOW


def test_unparseable_deep_read_is_skipped_not_fatal():
    store, sent = Store(":memory:"), []
    client = FakeClient(triage(a=9, b=8), "junk", "junk", ANALYSIS, TEACH)
    run(CFG, "profile", store, client, fetch_of(P("a", "finance"), P("b", "medical")), sent.append, NOW)
    assert len(sent) == 3 and "Title b" in sent[1]


def test_failed_sources_are_reported_in_header():
    sent = []
    run(CFG, "profile", Store(":memory:"), FakeClient(triage(a=9), ANALYSIS, TEACH),
        fetch_of(P("a", "finance"), failed=["nber"]), sent.append, NOW)
    assert "sources failed: nber" in sent[0]


def test_budget_exceeded_during_triage_propagates_and_records_nothing():
    cfg = dict(CFG, run=dict(CFG["run"], daily_cost_cap_usd=1e-9))
    store = Store(":memory:")
    with pytest.raises(BudgetExceeded):
        run(cfg, "profile", store, FakeClient(triage(a=9)), fetch_of(P("a", "finance")), lambda t: None, NOW)
    assert store.since(2, NOW) == NOW - timedelta(days=2)


def test_midway_send_failure_keeps_sent_papers_marked_and_does_not_advance_last_success():
    store = Store(":memory:")
    papers = [P("a", "finance"), P("b", "medical")]
    sent = []

    def flaky(text):
        if "Title b" in text:
            raise RuntimeError("telegram down")
        sent.append(text)

    client = FakeClient(triage(a=9, b=8), ANALYSIS, ANALYSIS, TEACH)
    with pytest.raises(RuntimeError):
        run(CFG, "profile", store, client, fetch_of(*papers), flaky, NOW)
    assert [p.id for p in store.new_only(papers)] == ["b"]
    assert store.since(2, NOW) == NOW - timedelta(days=2)
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/bin/pytest tests/test_agent.py -q`
Expected: FAIL, `ModuleNotFoundError: No module named 'agent'`.

- [ ] **Step 3: Implement**

`agent.py`:
```python
import argparse
import fcntl
import logging
import os
import tomllib
from datetime import datetime, timezone
from pathlib import Path

import anthropic

import digest
import sources
from llm import Budget, BudgetExceeded, deep_read, teach, triage
from rank import pick, prefilter
from store import Store

log = logging.getLogger("agent")
HERE = Path(__file__).parent


def run(cfg, profile, store, client, fetch, send, now, dry_run=False):
    r, m = cfg["run"], cfg["models"]
    since = store.since(r["lookback_days_first_run"], now)
    papers, failed = fetch(cfg, since.date(), now.date())
    papers = prefilter(store.new_only(papers), cfg["keywords"]["medical"])
    budget = Budget(r["daily_cost_cap_usd"], cfg["prices"])
    triage(client, m["triage"], papers, profile, budget)  # BudgetExceeded here aborts the whole run
    notes = [f"sources failed: {', '.join(failed)}"] if failed else []

    done = []
    for p in pick(papers, cfg["quota"], r["max_papers"], r["min_score"]):
        try:
            a = deep_read(client, m["analyse"], p, profile, budget)
        except BudgetExceeded:
            notes.append("cost cap hit, digest cut short")
            break
        if a:
            done.append((p, a))

    if not done:
        send("\n".join([f"Nothing worth your time today ({len(papers)} new papers scanned)."] + notes))
    else:
        send(digest.header_msg(done, len(papers), now.date().isoformat(), notes))
        for p, a in done:
            send(digest.paper_msg(p, a))
            if not dry_run:
                store.mark_sent(p)
        try:
            t = teach(client, m["analyse"], done, profile, budget)
        except BudgetExceeded:
            t = None
        if t:
            send(digest.teach_msg(t))
    if not dry_run:
        store.record_success(now)
    log.info("done: %d scanned, %d sent, spent $%.3f", len(papers), len(done), budget.spent)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="print the digest instead of sending it")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    lock = open(HERE / ".lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        log.warning("another run is in progress, exiting")
        return 0

    if args.dry_run:
        send = print
    else:
        token, chat = os.environ["TELEGRAM_BOT_TOKEN"], os.environ["TELEGRAM_CHAT_ID"]
        send = lambda text: digest.send(token, chat, text)  # noqa: E731
    try:
        with open(HERE / "config.toml", "rb") as f:
            cfg = tomllib.load(f)
        profile = (HERE / "profile.md").read_text()
        run(cfg, profile, Store(HERE / "state.db"), anthropic.Anthropic(), sources.fetch_all, send,
            datetime.now(timezone.utc), dry_run=args.dry_run)
    except Exception as e:
        log.exception("run failed")
        try:
            send(f"Digest run failed: {type(e).__name__}: {str(e)[:200]}")
        except Exception:
            log.exception("could not send the failure notice")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run to verify they pass**

Run: `.venv/bin/pytest -q`
Expected: all tests across the project pass.

- [ ] **Step 5: Commit**

```bash
git add agent.py tests/test_agent.py
git commit -m "feat: pipeline orchestration, dry-run, lock, failure notice"
```

---

### Task 8: Setup, live dry runs, cron

**Files:**
- Create: `README.md`

**Interfaces:** none (operations only).

- [ ] **Step 1: Write the README**

`README.md`:
````markdown
# Research digest

Daily Telegram digest of new papers, personalised by `profile.md`.
Design: `docs/superpowers/specs/2026-10-13-research-digest-design.md`.

## Setup (on the VPS)

```bash
git clone <repo> research-digest && cd research-digest
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp profile.example.md profile.md      # then fill it in
cat > .env <<'EOF'
ANTHROPIC_API_KEY=...
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
EOF
chmod 600 .env profile.md
```

Telegram: message @BotFather, `/newbot`, copy the token. Send any message to your new bot, then open
`https://api.telegram.org/bot<TOKEN>/getUpdates` and copy `message.chat.id`.

## Run

```bash
set -a; . ./.env; set +a
.venv/bin/python agent.py --dry-run   # prints the digest, writes no state
.venv/bin/python agent.py             # sends for real
```

## Cron (07:00 IST = 01:30 UTC; check `date` on the VPS)

```
30 1 * * * cd /home/USER/research-digest && set -a && . ./.env && set +a && .venv/bin/python agent.py >> agent.log 2>&1
```

Rotate `agent.log` with logrotate (weekly, rotate 4, compress).

## Cost

Each run logs `spent $X`. Prices live in `config.toml`; `daily_cost_cap_usd` stops the run if exceeded.
````

- [ ] **Step 2: Check current model prices**

Look up current Anthropic pricing for `claude-haiku-5-5` and `claude-sonnet-5-5` (the `claude-api` skill or the pricing page) and correct the `[prices.*]` values in `config.toml` if they differ.

- [ ] **Step 3: Get the user's real setup values**

Ask the user for: the VPS login/path to deploy to, whether `profile.md` is filled in, the Anthropic key and Telegram bot token in `.env` (never printed or committed). Do not proceed without them.

- [ ] **Step 4: Live dry runs**

On the machine with the values: `.venv/bin/python agent.py --dry-run`. Read the full output as the user would. Check: items are sensible for the profile, no invented numbers, medical items do not prescribe, finance items do not say buy/sell, evidence badges are right, the log line shows a plausible `spent $`. Fix prompts in `llm.py` if quality is off and re-run. Repeat on at least 3 different days before enabling sending.

- [ ] **Step 5: Live send and cron**

Run once without `--dry-run`, confirm the messages arrive on Telegram and render correctly, then re-run immediately and confirm nothing is sent twice. Add the cron line and confirm the next morning's run via `agent.log`.

- [ ] **Step 6: Commit**

```bash
git add README.md config.toml
git commit -m "docs: setup README and verified prices"
```
