import json
import tomllib
from datetime import datetime, timedelta, timezone

from agent import acquire_lock, guarded, run
from runner import RunnerError, UsageLimitReached
from sources import Paper
from store import Store

NOW = datetime(2026, 10, 13, 1, 30, tzinfo=timezone.utc)
with open("config.toml", "rb") as f:
    CFG = tomllib.load(f)
ANALYSIS = json.dumps({"did": "d", "found": "f", "evidence": "e", "for_you": "y", "action": "a", "for_world": "w"})
CONCEPT = json.dumps({"name": "Drawdown", "explain": "how far a portfolio falls", "example": "your F&O algo"})


class FakeRun:
    """Answers triage calls from `scores` (default 9) and deep-read calls with ANALYSIS (or queued replies)."""

    def __init__(self, *replies, scores=None, concept=CONCEPT, limit_on_call=None, error_on_call=None):
        self.replies, self.scores, self.concept, self.calls = list(replies), scores or {}, concept, []
        self.limit_on_call = limit_on_call  # 1-based index of the call that hits the usage limit
        self.error_on_call = error_on_call  # 1-based index of a call that fails some other way

    def __call__(self, model, system, user):
        self.calls.append((model, system, user))
        if self.limit_on_call == len(self.calls):
            raise UsageLimitReached("You've hit your session limit")
        if self.error_on_call == len(self.calls):
            raise RunnerError("claude timed out after 300s")
        if "triage" in system.lower():
            return json.dumps([{"id": r["id"], "score": self.scores.get(r["id"], 9)} for r in json.loads(user)])
        if "one concept" in system.lower():
            if isinstance(self.concept, Exception):
                raise self.concept
            return self.concept
        return self.replies.pop(0) if self.replies else ANALYSIS

    def deep_calls(self):
        return [c for c in self.calls if "triage" not in c[1].lower() and "one concept" not in c[1].lower()]


LONG = "The authors study the question with a stated design and report their main findings in detail. " * 2


def P(id, area="finance", abstract=LONG, published="2026-10-12"):
    return Paper(id=id, title="Title " + id, abstract=abstract, source="s", area=area, journal="J",
                 url="https://e.com/" + id, published=published, kind="peer")


def fetch_of(*papers, failed=()):
    return lambda cfg, since, today: (list(papers), list(failed))


def go(papers, fake=None, store=None, failed=(), dry_run=False):
    sent, fake = [], fake or FakeRun()
    store = store or Store(":memory:")
    run(CFG, "profile", store, fake, fetch_of(*papers, failed=failed), sent.append, NOW, dry_run=dry_run)
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


def test_a_cap_spent_on_triage_leaves_nothing_to_read_so_the_run_says_so_instead_of_crashing():
    cfg = dict(CFG, run=dict(CFG["run"], max_calls_per_run=1))
    sent, store = [], Store(":memory:")
    run(cfg, "profile", store, FakeRun(), fetch_of(P("a")), sent.append, NOW)
    assert len(sent) == 1 and "cut short" in sent[0] and "CallCapExceeded" in sent[0]
    assert store.since(2, NOW) == NOW - timedelta(days=2)


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
    sent, fake, _ = go([P("m", "medical", abstract="Unrelated surgery technique. " * 6)])
    assert fake.calls == [] and len(sent) == 1 and "Nothing worth" in sent[0]


def test_paper_without_a_real_abstract_is_dropped_before_any_model_call():
    sent, fake, _ = go([P("news", abstract=""), P("stub", abstract="Short teaser.")])
    assert fake.calls == [] and len(sent) == 1 and "Nothing worth" in sent[0]


def test_dry_run_writes_no_state():
    store = Store(":memory:")
    papers = [P("a")]
    go(papers, store=store, dry_run=True)
    assert store.new_only(papers) == papers
    assert store.since(2, NOW) == NOW - timedelta(days=2)


def test_main_stops_before_fetching_when_login_check_fails(monkeypatch, capsys):
    import agent
    import runner
    import sources

    def not_logged_in():
        raise runner.RunnerError("Claude Code is not logged in")

    def must_not_fetch(*a, **k):
        raise AssertionError("fetched despite failed login check")

    monkeypatch.setattr(runner, "check_login", not_logged_in)
    monkeypatch.setattr(sources, "fetch_all", must_not_fetch)
    assert agent.main(["--dry-run"]) == 1
    assert "not logged in" in capsys.readouterr().out


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


# ---- issue 06: idempotent, failure-safe runs ----

def test_real_run_marks_every_sent_paper_and_records_success():
    store = Store(":memory:")
    papers = [P("a"), P("b", "science")]
    go(papers, store=store)
    assert store.new_only(papers) == []
    assert store.since(2, NOW + timedelta(days=9)) == NOW


def test_rerunning_after_success_sends_no_paper_twice():
    store = Store(":memory:")
    go([P("a")], store=store)
    sent, _, _ = go([P("a")], store=store)
    assert len(sent) == 1 and "Nothing worth" in sent[0]


def test_midway_send_failure_keeps_delivered_papers_marked_and_does_not_advance_last_success():
    import pytest
    store = Store(":memory:")
    papers = [P("a"), P("b", "science")]

    def flaky(text):
        if "Title b" in text:
            raise RuntimeError("telegram down")

    with pytest.raises(RuntimeError):
        run(CFG, "profile", store, FakeRun(scores={"a": 9, "b": 8}), fetch_of(*papers), flaky, NOW)
    assert [p.id for p in store.new_only(papers)] == ["b"]
    assert store.since(2, NOW) == NOW - timedelta(days=2)


def test_retry_after_midway_failure_sends_only_the_remaining_paper():
    store = Store(":memory:")
    papers = [P("a"), P("b", "science")]

    def flaky(text):
        if "Title b" in text:
            raise RuntimeError("telegram down")

    try:
        run(CFG, "profile", store, FakeRun(scores={"a": 9, "b": 8}), fetch_of(*papers), flaky, NOW)
    except RuntimeError:
        pass
    sent, _, _ = go(papers, store=store, fake=FakeRun(scores={"b": 8}))
    assert any("Title b" in m for m in sent) and not any("Title a" in m for m in sent)


def test_usage_limit_during_triage_sends_only_a_limit_notice_and_changes_no_state():
    store = Store(":memory:")
    papers = [P("a")]
    sent, _, _ = go(papers, store=store, fake=FakeRun(limit_on_call=1))
    assert len(sent) == 1 and "usage limit" in sent[0].lower() and "Nothing worth" not in sent[0]
    assert store.new_only(papers) == papers and store.since(2, NOW) == NOW - timedelta(days=2)


def test_usage_limit_during_deep_read_delivers_completed_papers_then_a_notice_without_advancing():
    store = Store(":memory:")
    papers = [P("a"), P("b", "science")]
    # calls: 1 triage, 2 read a, 3 read b (limit)
    sent, _, _ = go(papers, store=store, fake=FakeRun(scores={"a": 9, "b": 8}, limit_on_call=3))
    assert "Title a" in sent[1] and "usage limit" in sent[-1].lower()
    assert [p.id for p in store.new_only(papers)] == ["b"]
    assert store.since(2, NOW) == NOW - timedelta(days=2)


def test_usage_limit_during_teach_still_delivers_all_papers_then_a_notice_without_advancing():
    store = Store(":memory:")
    papers = [P("a")]
    sent, _, _ = go(papers, store=store, fake=FakeRun(limit_on_call=3))  # 1 triage, 2 read, 3 teach
    assert "Title a" in sent[1] and "usage limit" in sent[-1].lower()
    assert store.new_only(papers) == [] and store.since(2, NOW) == NOW - timedelta(days=2)


def test_first_run_fetches_from_the_lookback_then_from_last_success():
    seen = []

    def fetch(cfg, since, today):
        seen.append(since)
        return [], []

    store = Store(":memory:")
    run(CFG, "profile", store, FakeRun(), fetch, lambda t: None, NOW)
    run(CFG, "profile", store, FakeRun(), fetch, lambda t: None, NOW + timedelta(hours=1))
    assert seen == [(NOW - timedelta(days=2)).date(), NOW.date()]


def test_guarded_success_returns_zero_and_sends_nothing():
    sent = []
    assert guarded(lambda: None, sent.append) == 0 and sent == []


def test_guarded_crash_notifies_with_error_type_and_short_message_and_returns_one():
    sent = []

    def job():
        raise ValueError("boom " + "x" * 1000)

    assert guarded(job, sent.append) == 1
    assert len(sent) == 1 and "ValueError" in sent[0] and "boom" in sent[0] and len(sent[0]) < 400


def test_guarded_survives_a_failing_notifier():
    def job():
        raise ValueError("boom")

    def broken(text):
        raise OSError("telegram unreachable")

    assert guarded(job, broken) == 1


def test_lock_blocks_a_second_holder_until_released(tmp_path):
    path = tmp_path / ".lock"
    first = acquire_lock(path)
    assert first is not None and acquire_lock(path) is None
    first.close()
    assert acquire_lock(path) is not None


def test_a_non_limit_failure_mid_deep_read_still_delivers_the_papers_already_read():
    store = Store(":memory:")
    papers = [P("a"), P("b", "science")]
    # calls: 1 triage, 2 read a, 3 read b (times out)
    sent, _, _ = go(papers, store=store, fake=FakeRun(scores={"a": 9, "b": 8}, error_on_call=3))
    assert "Title a" in sent[1] and "cut short" in sent[-1] and "RunnerError" in sent[-1]
    assert [p.id for p in store.new_only(papers)] == ["b"]
    assert store.since(2, NOW) == NOW - timedelta(days=2)


def test_exhausting_the_call_cap_mid_deep_read_also_delivers_what_was_read():
    cfg = dict(CFG, run=dict(CFG["run"], max_calls_per_run=2))  # 1 triage + 1 read, then the cap
    sent = []
    store = Store(":memory:")
    run(cfg, "profile", store, FakeRun(scores={"a": 9, "b": 8}), fetch_of(P("a"), P("b", "science")), sent.append, NOW)
    assert "Title a" in sent[1] and "cut short" in sent[-1]
    assert store.since(2, NOW) == NOW - timedelta(days=2)


def test_a_backlog_bigger_than_the_call_cap_is_bounded_to_the_newest_papers_not_a_daily_crash():
    cfg = dict(CFG, run=dict(CFG["run"], max_calls_per_run=10, triage_batch=2, max_papers=1))
    papers = [P(f"p{i:02d}", published=f"2026-10-{i + 1:02d}") for i in range(20)]  # p19 is the newest
    sent, fake = [], FakeRun()
    store = Store(":memory:")
    run(cfg, "profile", store, fake, fetch_of(*papers), sent.append, NOW)  # must not raise CallCapExceeded
    triaged = [r["id"] for model, system, user in fake.calls if "triage" in system.lower() for r in json.loads(user)]
    assert len(triaged) == 6 and set(triaged) == {f"p{i:02d}" for i in range(14, 20)}
    assert "14 older papers not triaged" in sent[0]
    assert store.since(2, NOW) == NOW  # the run completed, so it advances


def test_when_every_source_fails_nothing_is_lost_and_last_success_does_not_advance():
    store, sent = Store(":memory:"), []
    fake = FakeRun()
    run(CFG, "profile", store, fake, fetch_of(failed=["arxiv/finance", "pubmed"]), sent.append, NOW)
    assert len(sent) == 1 and "All sources failed" in sent[0] and "pubmed" in sent[0]
    assert fake.calls == [] and store.since(2, NOW) == NOW - timedelta(days=2)


def test_a_partial_source_outage_still_completes_and_is_reported():
    store = Store(":memory:")
    sent, _, _ = go([P("a")], store=store, failed=["nber"])
    assert "sources failed: nber" in sent[0] and store.since(2, NOW + timedelta(days=9)) == NOW


def _triage_calls(fake):
    return [c for c in fake.calls if "triage" in c[1].lower()]


def test_a_paper_scored_yesterday_is_not_triaged_again_today():
    store = Store(":memory:")
    go([P("a")], store=store, fake=FakeRun(scores={"a": 2}))  # below the bar: never sent
    sent, fake, _ = go([P("a")], store=store, fake=FakeRun(scores={"a": 2}))
    assert _triage_calls(fake) == [] and "Nothing worth" in sent[0]


def test_a_cached_score_still_qualifies_a_paper_that_was_cut_off_by_a_usage_limit():
    store = Store(":memory:")
    papers = [P("a"), P("b", "science")]
    go(papers, store=store, fake=FakeRun(scores={"a": 9, "b": 8}, limit_on_call=3))  # b scored 8, never read
    sent, fake, _ = go(papers, store=store, fake=FakeRun())
    assert _triage_calls(fake) == [] and any("Title b" in m for m in sent)


def test_dry_run_records_no_scores():
    store = Store(":memory:")
    go([P("a")], store=store, dry_run=True)
    assert store.cached_scores([P("a")]) == {}


def test_the_real_usage_limit_message_is_logged_so_its_wording_can_be_observed(caplog):
    import logging
    with caplog.at_level(logging.WARNING, logger="agent"):
        go([P("a")], fake=FakeRun(limit_on_call=1))
    assert "You've hit your session limit" in caplog.text
