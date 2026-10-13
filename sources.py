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
from datetime import timedelta

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
    # The API trails real time by days (weekends); the window is wide and the store dedupes.
    cutoff = (since - timedelta(days=4)).isoformat()
    return [p for p in parse_arxiv(xml, area) if p.published >= cutoff]


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


def parse_nber(xml, today):
    for it in ET.fromstring(xml).iter("item"):
        link = it.findtext("link").split("#")[0]
        yield Paper(id="nber:" + link, title=_text(it.findtext("title")), abstract=_text(it.findtext("description")),
                    source="nber", area="finance", journal="NBER working paper", url=link,
                    published=today.isoformat(), kind="preprint")


# The feed has no dates (it lists the latest ~20 papers); the store's sent-dedupe prevents repeats.
def fetch_nber(today):
    return list(parse_nber(get("https://back.nber.org/rss/new.xml"), today))


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
    jobs.append(("nber", lambda: fetch_nber(today)))
    papers, failed = {}, []
    for name, fn in jobs:
        try:
            for p in fn():
                papers.setdefault(p.id, p)
        except Exception as e:
            log.warning("source %s failed: %s", name, e)
            failed.append(name)
    return list(papers.values()), failed
