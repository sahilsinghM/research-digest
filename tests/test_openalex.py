import io
import urllib.error

import pytest

import openalex
from oa_fixtures import FakeOpenAlex, W, inv

BS = W("W1", "The Pricing of Options and Corporate Liabilities", 1973, 28883, refs=("W9",),
       abstract="If options are correctly priced in the market, it should not be possible to make sure profits.",
       authors=("Fischer Black", "Myron Scholes"), doi="https://doi.org/10.1086/260062")
BS_CHAPTER = W("W2", "Theory of Rational Option Pricing", 1973, 7948, type="book-chapter", authors=("Robert C. Merton",))
BS_REPRINT = W("W3", "The Pricing of Options and Corporate Liabilities", 2005, 120, type="book-chapter",
               authors=("Fischer Black", "Myron Scholes"))
OTHER = W("W4", "Securities -- Insiders' Liability Under Section 16(b)", 1973, 0, authors=("Someone Else",))


def test_abstract_is_rebuilt_from_the_inverted_index_in_word_order_and_missing_is_empty():
    assert openalex.reconstruct_abstract(inv("the quick brown fox the end")) == "the quick brown fox the end"
    assert openalex.reconstruct_abstract(None) == "" and openalex.reconstruct_abstract({}) == ""


def test_parse_work_extracts_the_fields_the_track_needs():
    w = openalex.parse_work(W("W7", "A Title", 1993, 8762, refs=("W1", "W2"), abstract="An abstract.", oa="https://x/p.pdf",
                              authors=("Steven L. Heston",), subfield="Finance"))
    assert (w.id, w.title, w.year, w.cited_by, w.type) == ("W7", "A Title", 1993, 8762, "article")
    assert w.abstract == "An abstract." and w.oa_url == "https://x/p.pdf" and w.references == ["W1", "W2"]
    assert w.authors == ["Steven L. Heston"] and w.topic == "Finance" and w.doi_url.startswith("https://doi.org/")


def test_parse_work_tolerates_missing_everything():
    w = openalex.parse_work({"id": "https://openalex.org/W5"})
    assert (w.id, w.title, w.year, w.cited_by, w.abstract, w.oa_url, w.references, w.authors) == ("W5", "", 0, 0, "", "", [], [])


def test_resolve_picks_the_original_article_not_the_chapter_or_reprint():
    api = FakeOpenAlex(BS, BS_CHAPTER, BS_REPRINT, OTHER)
    entry = {"title": "The Pricing of Options and Corporate Liabilities", "authors": ["Black", "Scholes"], "year": 1973}
    work, reason = openalex.resolve(api, entry)
    assert work.id == "W1" and reason == ""


def test_resolve_prefers_the_article_when_a_chapter_copy_has_the_same_title_and_year():
    chapter_copy = W("W8", "The Pricing of Options and Corporate Liabilities", 1973, 999999, type="book-chapter",
                     authors=("Fischer Black",))
    work, _ = openalex.resolve(FakeOpenAlex(chapter_copy, BS), {"title": BS["display_name"], "authors": ["Black"], "year": 1973})
    assert work.id == "W1"


def test_resolve_flags_an_author_mismatch_instead_of_guessing():
    work, reason = openalex.resolve(FakeOpenAlex(BS), {"title": BS["display_name"], "authors": ["Nobody"], "year": 1973})
    assert work is None and "author" in reason.lower()


def test_resolve_flags_a_missing_paper_and_a_year_far_from_the_expected_one():
    work, reason = openalex.resolve(FakeOpenAlex(BS), {"title": "Totally Different Paper", "authors": [], "year": 1973})
    assert work is None and "not found" in reason.lower()
    work, reason = openalex.resolve(FakeOpenAlex(BS_REPRINT), {"title": BS_REPRINT["display_name"], "authors": [], "year": 1973})
    assert work is None


def test_resolve_accepts_minor_title_differences():
    work, _ = openalex.resolve(FakeOpenAlex(BS), {"title": "the pricing of options and corporate liabilities.", "authors": ["Black"], "year": 1974})
    assert work.id == "W1"  # a year off by one is allowed


def test_references_and_citing_come_back_most_cited_first():
    a, b, c = W("W10", "A", 1980, 5, refs=("W1",)), W("W11", "B", 1990, 50, refs=("W1",)), W("W12", "C", 1985, 500, refs=("W2",))
    api = FakeOpenAlex(BS, BS_CHAPTER, a, b, c)
    assert [w.id for w in openalex.citing(api, "W1", n=5)] == ["W11", "W10"]
    refs = openalex.get_works(api, ["W2", "W1"])
    assert sorted(w.id for w in refs) == ["W1", "W2"] and openalex.get_works(api, []) == []


def _err(code):
    return urllib.error.HTTPError("https://api.openalex.org/works", code, "x", {}, io.BytesIO(b""))


class _Resp:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return self.body


@pytest.fixture
def net(monkeypatch):
    class N:
        outcomes, sleeps, urls = [], [], []
    n = N()

    def urlopen(req, timeout):
        n.urls.append(req.full_url)
        out = n.outcomes.pop(0)
        if isinstance(out, Exception):
            raise out
        return _Resp(out)

    monkeypatch.setattr(openalex.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(openalex.time, "sleep", n.sleeps.append)
    return n


def test_http_get_json_builds_the_url_parses_json_and_retries_rate_limits_with_backoff(net):
    net.outcomes[:] = [_err(429), _err(503), b'{"results": [1]}']
    assert openalex.http_get_json("/works", {"search": "a b", "per_page": 3}) == {"results": [1]}
    assert net.urls[0].startswith("https://api.openalex.org/works?") and "search=a+b" in net.urls[0]
    assert len(net.sleeps) >= 3  # politeness pause + two backoffs


def test_http_get_json_gives_up_with_a_clear_error_and_does_not_retry_client_errors(net):
    net.outcomes[:] = [_err(500)] * 3
    with pytest.raises(openalex.OpenAlexError):
        openalex.http_get_json("/works", {})
    net.outcomes[:] = [_err(400)]
    net.urls.clear()
    with pytest.raises(openalex.OpenAlexError):
        openalex.http_get_json("/works", {})
    assert len(net.urls) == 1
    net.outcomes[:] = [TimeoutError("slow")] * 3
    with pytest.raises(openalex.OpenAlexError):
        openalex.http_get_json("/works", {})


def test_resolve_asks_for_the_most_cited_matches_first_so_generic_titles_find_the_canonical_record():
    api = FakeOpenAlex(BS)
    openalex.resolve(api, {"title": BS["display_name"], "authors": ["Black"], "year": 1973})
    params = api.calls[0][1]
    assert params["sort"] == "cited_by_count:desc" and params["per_page"] >= 20
