import json
import tomllib
from datetime import datetime, timedelta, timezone

from agent import run
from sources import Paper
from store import Store

NOW = datetime(2026, 10, 13, 1, 30, tzinfo=timezone.utc)
with open("config.toml", "rb") as f:
    CFG = tomllib.load(f)
ANALYSIS = json.dumps({"did": "d", "found": "f", "evidence": "e", "for_you": "y", "action": "a", "for_world": "w"})


class FakeRun:
    def __init__(self, *replies, default=ANALYSIS):
        self.replies, self.default, self.calls = list(replies), default, []

    def __call__(self, model, system, user):
        self.calls.append((model, system, user))
        return self.replies.pop(0) if self.replies else self.default


def P(id, area="finance", abstract="abs"):
    return Paper(id=id, title="Title " + id, abstract=abstract, source="s", area=area, journal="J",
                 url="https://e.com/" + id, published="2026-10-12", kind="peer")


def fetch_of(*papers, failed=()):
    return lambda cfg, since, today: (list(papers), list(failed))


def go(papers, fake=None, store=None, failed=()):
    sent, fake = [], fake or FakeRun()
    store = store or Store(":memory:")
    run(CFG, "profile", store, fake, fetch_of(*papers, failed=failed), sent.append, NOW)
    return sent, fake, store


def test_sends_header_then_one_message_per_paper_using_analyse_model():
    sent, fake, _ = go([P("a"), P("b", "science")])
    assert len(sent) == 3 and "Research digest" in sent[0]
    assert "Title a" in sent[1] and "Title b" in sent[2]
    assert all(model == CFG["models"]["analyse"] for model, _, _ in fake.calls)


def test_respects_per_area_quota():
    sent, fake, _ = go([P(f"f{i}") for i in range(5)])
    assert len(fake.calls) == CFG["quota"]["finance"] and len(sent) == 1 + CFG["quota"]["finance"]


def test_failed_sources_reported_in_header():
    sent, _, _ = go([P("a")], failed=["nber"])
    assert "sources failed: nber" in sent[0]


def test_unparseable_analysis_skips_that_paper_only():
    sent, _, _ = go([P("a"), P("b", "science")], fake=FakeRun("junk", "junk"))
    assert len(sent) == 2 and "Title b" in sent[1] and "Title a" not in sent[1]


def test_already_sent_papers_are_skipped():
    store = Store(":memory:")
    store.mark_sent(P("a"))
    sent, _, _ = go([P("a"), P("b", "science")], store=store)
    assert len(sent) == 2 and "Title b" in sent[1]


def test_medical_paper_without_keywords_is_dropped_before_any_model_call():
    sent, fake, _ = go([P("m", "medical", abstract="Unrelated surgery technique")])
    assert fake.calls == [] and len(sent) == 1 and "Nothing worth" in sent[0]


def test_empty_abstract_is_handled():
    sent, _, _ = go([P("a", abstract="")])
    assert len(sent) == 2


def test_dry_run_writes_no_state():
    store = Store(":memory:")
    papers = [P("a")]
    go(papers, store=store)
    assert store.new_only(papers) == papers
    assert store.since(2, NOW) == NOW - timedelta(days=2)
