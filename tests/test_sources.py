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

PUBMED_DOI = b"""<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>555</PMID><Article>
<Journal><Title>Nature</Title></Journal><ArticleTitle>A real finding</ArticleTitle>
<Abstract><AbstractText>Full abstract text.</AbstractText></Abstract></Article></MedlineCitation>
<PubmedData><ArticleIdList><ArticleId IdType="pubmed">555</ArticleId><ArticleId IdType="doi">10.1038/x1</ArticleId></ArticleIdList></PubmedData>
</PubmedArticle></PubmedArticleSet>"""

PUBMED = b"""<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>123</PMID><Article>
<Journal><Title>The Lancet</Title></Journal>
<ArticleTitle>Sleep and <i>BP</i></ArticleTitle>
<Abstract><AbstractText Label="A">Part one.</AbstractText><AbstractText>Part two.</AbstractText></Abstract>
</Article></MedlineCitation></PubmedArticle>
<PubmedArticle><MedlineCitation><PMID>124</PMID><Article><Journal><Title>JAMA</Title></Journal>
<ArticleTitle>Letter without abstract</ArticleTitle></Article></MedlineCitation></PubmedArticle></PubmedArticleSet>"""

RXIV = {"collection": [{"doi": "10.1101/2026.10.01.123", "title": "T", "abstract": "A",
                        "date": "2026-10-11", "version": "2"}]}

# The real feed carries no dates and tags links with #fromrss.
NBER = b"""<rss><channel><item><title>Rates and Risk -- by A B</title><link>https://www.nber.org/papers/w1#fromrss</link>
<description>Abstract here.</description></item></channel></rss>"""


def test_parse_arxiv():
    [p] = parse_arxiv(ARXIV, "finance")
    assert p.id == "arxiv:2610.01234"
    assert p.title == "Pricing Options with Rough Vol"
    assert p.abstract == "We study X. Results follow."
    assert p.kind == "preprint" and p.published == "2026-10-12"


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


def test_parse_rxiv_fields():
    [p] = parse_rxiv(RXIV, "medrxiv", "medical")
    assert p.id == "doi:10.1101/2026.10.01.123" and p.kind == "preprint"
    assert p.url == "https://doi.org/10.1101/2026.10.01.123" and p.published == "2026-10-11"
    assert p.journal == "medRxiv"


def test_parse_nber():
    [p] = parse_nber(NBER, date(2026, 10, 13))
    assert p.id == "nber:https://www.nber.org/papers/w1" and p.url == "https://www.nber.org/papers/w1"
    assert p.published == "2026-10-13" and p.area == "finance" and p.abstract == "Abstract here."


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


def test_fetch_arxiv_window_reaches_back_past_weekend_lag(monkeypatch):
    monkeypatch.setattr(sources.time, "sleep", lambda s: None)
    monkeypatch.setattr(sources, "get", lambda *a, **k: ARXIV)  # entry published 2026-10-12
    assert sources.fetch_arxiv("q", "finance", date(2026, 10, 15))  # 3 days older than since: kept
    assert not sources.fetch_arxiv("q", "finance", date(2026, 10, 17))  # 5 days older: dropped


def test_parse_pubmed_takes_the_area_given_and_uses_the_doi_as_id_when_there_is_one():
    [p] = parse_pubmed(PUBMED_DOI, date(2026, 10, 13), area="science")
    assert p.area == "science" and p.id == "doi:10.1038/x1" and p.abstract == "Full abstract text."
    [q] = list(parse_pubmed(PUBMED, date(2026, 10, 13)))[:1]
    assert q.id == "pmid:123" and q.area == "medical"


def _fetch_all_with(monkeypatch, crossref, pubmed_by_area):
    monkeypatch.setattr(sources, "fetch_arxiv", lambda *a, **k: [])
    monkeypatch.setattr(sources, "fetch_crossref", lambda *a, **k: crossref)
    monkeypatch.setattr(sources, "fetch_rxiv", lambda *a, **k: [])
    monkeypatch.setattr(sources, "fetch_nber", lambda *a, **k: [])
    seen = []

    def fake_pubmed(journals, since, today, area="medical"):
        seen.append((area, tuple(journals)))
        return pubmed_by_area.get(area, [])

    monkeypatch.setattr(sources, "fetch_pubmed", fake_pubmed)
    cfg = {"arxiv": [], "journal": [{"name": "N", "issn": "1", "area": "science"}],
           "pubmed": {"journals": ["Lancet"]}, "pubmed_extra": [{"area": "science", "journals": ["Nature", "Cell"]}]}
    papers, failed = sources.fetch_all(cfg, date(2026, 10, 12), date(2026, 10, 13))
    return papers, failed, seen


def _paper(id, abstract, area="science"):
    return Paper(id=id, title="t", abstract=abstract, source="s", area=area, journal="Nature",
                 url="u", published="2026-10-12", kind="peer")


def test_extra_pubmed_journal_groups_are_fetched_with_their_own_area(monkeypatch):
    _, failed, seen = _fetch_all_with(monkeypatch, [], {})
    assert failed == [] and ("medical", ("Lancet",)) in seen and ("science", ("Nature", "Cell")) in seen


def test_when_a_paper_comes_from_two_sources_the_copy_with_the_abstract_wins(monkeypatch):
    bare, full = _paper("doi:10.1/x", ""), _paper("doi:10.1/x", "A long recovered abstract.")
    papers, _, _ = _fetch_all_with(monkeypatch, [bare], {"science": [full]})
    assert [p.abstract for p in papers] == ["A long recovered abstract."]
    papers, _, _ = _fetch_all_with(monkeypatch, [full], {"science": [bare]})
    assert [p.abstract for p in papers] == ["A long recovered abstract."]


class _Resp:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return self.body


def _flaky_urlopen(monkeypatch, outcomes):
    import urllib.error
    sleeps = []

    def urlopen(req, timeout):
        out = outcomes.pop(0)
        if out == 429:
            raise urllib.error.HTTPError(req.full_url, 429, "Too Many Requests", {}, None)
        return _Resp(out)

    monkeypatch.setattr(sources.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(sources.time, "sleep", sleeps.append)
    return sleeps


def test_get_backs_off_exponentially_from_the_given_base_and_then_succeeds(monkeypatch):
    sleeps = _flaky_urlopen(monkeypatch, [429, 429, b"ok"])
    assert sources.get("http://x", tries=3, backoff=10) == b"ok"
    assert sleeps == [10, 20]


def test_get_gives_up_after_the_given_number_of_tries(monkeypatch):
    import urllib.error

    import pytest
    _flaky_urlopen(monkeypatch, [429, 429, 429])
    with pytest.raises(urllib.error.HTTPError):
        sources.get("http://x", tries=3, backoff=1)


def test_arxiv_asks_for_patient_retries_because_its_rate_limit_penalty_is_long(monkeypatch):
    seen = {}
    monkeypatch.setattr(sources.time, "sleep", lambda s: None)
    monkeypatch.setattr(sources, "get", lambda url, params=None, tries=3, backoff=1: seen.update(tries=tries, backoff=backoff) or ARXIV)
    sources.fetch_arxiv("q", "finance", date(2026, 10, 12))
    assert seen["backoff"] >= 10 and seen["tries"] >= 3
