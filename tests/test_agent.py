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
CONCEPT = json.dumps({"name": "Drawdown", "explain": "how far a portfolio falls", "example": "your F&O algo"})


class FakeRun:
    """Answers triage calls from `scores` (default 9) and deep-read calls with ANALYSIS (or queued replies)."""

    def __init__(self, *replies, scores=None, concept=CONCEPT):
        self.replies, self.scores, self.concept, self.calls = list(replies), scores or {}, concept, []

    def __call__(self, model, system, user):
        self.calls.append((model, system, user))
        if "triage" in system.lower():
            return json.dumps([{"id": r["id"], "score": self.scores.get(r["id"], 9)} for r in json.loads(user)])
        if "one concept" in system.lower():
            if isinstance(self.concept, Exception):
                raise self.concept
            return self.concept
        return self.replies.pop(0) if self.replies else ANALYSIS

    def deep_calls(self):
        return [c for c in self.calls if "triage" not in c[1].lower() and "one concept" not in c[1].lower()]


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
    assert len(sent) == 4 and "Research digest" in sent[0]
    assert "Title a" in sent[1] and "Title b" in sent[2] and "Drawdown" in sent[3]
    assert all(model == CFG["models"]["analyse"] for model, _, _ in fake.deep_calls())


def test_respects_per_area_quota():
    sent, fake, _ = go([P(f"f{i}") for i in range(5)])
    assert len(fake.deep_calls()) == CFG["quota"]["finance"] and len(sent) == 2 + CFG["quota"]["finance"]


def test_highest_scored_papers_are_chosen_and_sent_best_first():
    fake = FakeRun(scores={"a": 6, "b": 9, "c": 7})
    sent, _, _ = go([P("a"), P("b"), P("c")], fake=fake)
    assert "Title b" in sent[1] and "Title c" in sent[2] and len(sent) == 4  # quota 2 for finance, + teach


def test_papers_below_the_bar_are_never_read_deeply():
    sent, fake, _ = go([P("a"), P("b")], fake=FakeRun(scores={"a": 2, "b": 4}))
    assert fake.deep_calls() == [] and len(sent) == 1 and "Nothing worth" in sent[0]


def test_triage_uses_the_triage_model_and_deep_read_the_analyse_model():
    _, fake, _ = go([P("a")])
    models = {("triage" in s.lower()): m for m, s, _ in fake.calls}
    assert models[True] == CFG["models"]["triage"] and models[False] == CFG["models"]["analyse"]


def test_exceeding_the_call_cap_raises_the_dedicated_error():
    import pytest

    from analyst import CallCapExceeded
    cfg = dict(CFG, run=dict(CFG["run"], max_calls_per_run=1))
    with pytest.raises(CallCapExceeded):
        run(cfg, "profile", Store(":memory:"), FakeRun(), fetch_of(P("a")), lambda t: None, NOW)


def test_failed_sources_reported_in_header():
    sent, _, _ = go([P("a")], failed=["nber"])
    assert "sources failed: nber" in sent[0]


def test_unparseable_analysis_skips_that_paper_only():
    sent, _, _ = go([P("a"), P("b", "science")], fake=FakeRun("junk", "junk", scores={"a": 9, "b": 8}))
    assert len(sent) == 3 and "Title b" in sent[1] and "Title a" not in sent[1]


def test_already_sent_papers_are_skipped():
    store = Store(":memory:")
    store.mark_sent(P("a"))
    sent, _, _ = go([P("a"), P("b", "science")], store=store)
    assert len(sent) == 3 and "Title b" in sent[1]


def test_medical_paper_without_keywords_is_dropped_before_any_model_call():
    sent, fake, _ = go([P("m", "medical", abstract="Unrelated surgery technique")])
    assert fake.calls == [] and len(sent) == 1 and "Nothing worth" in sent[0]


def test_empty_abstract_is_handled():
    sent, _, _ = go([P("a", abstract="")])
    assert len(sent) == 3


def test_dry_run_writes_no_state():
    store = Store(":memory:")
    papers = [P("a")]
    go(papers, store=store)
    assert store.new_only(papers) == papers
    assert store.since(2, NOW) == NOW - timedelta(days=2)


def test_main_stops_before_fetching_when_login_check_fails(monkeypatch):
    import pytest

    import agent
    import runner
    import sources

    def not_logged_in():
        raise runner.RunnerError("Claude Code is not logged in")

    def must_not_fetch(*a, **k):
        raise AssertionError("fetched despite failed login check")

    monkeypatch.setattr(runner, "check_login", not_logged_in)
    monkeypatch.setattr(sources, "fetch_all", must_not_fetch)
    with pytest.raises(runner.RunnerError, match="not logged in"):
        agent.main(["--dry-run"])


def test_header_names_the_most_important_paper():
    sent, _, _ = go([P("a"), P("b")], fake=FakeRun(scores={"a": 6, "b": 9}))
    assert "Most important: Title b" in sent[0]


def test_unparseable_concept_still_delivers_the_papers():
    sent, _, _ = go([P("a")], fake=FakeRun(concept="junk"))
    assert len(sent) == 2 and "Title a" in sent[1]


def test_failing_concept_call_still_delivers_the_papers():
    from runner import RunnerError
    sent, _, _ = go([P("a")], fake=FakeRun(concept=RunnerError("boom")))
    assert len(sent) == 2 and "Title a" in sent[1]


def test_no_concept_call_on_a_quiet_day():
    sent, fake, _ = go([P("a")], fake=FakeRun(scores={"a": 1}))
    assert len(sent) == 1 and all("one concept" not in s.lower() for _, s, _ in fake.calls)
