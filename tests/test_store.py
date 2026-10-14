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


def test_recorded_scores_are_remembered_without_marking_papers_sent():
    s = Store(":memory:")
    a, b = P("a"), P("b")
    a.score, b.score = 4.0, 7.5
    s.record_scores([a, b])
    assert s.cached_scores([P("a"), P("b"), P("c")]) == {"a": 4.0, "b": 7.5}
    assert [p.id for p in s.new_only([P("a"), P("b")])] == ["a", "b"]


def test_recording_a_score_never_unsends_a_paper_and_sending_keeps_it_scored():
    s = Store(":memory:")
    a = P("a")
    a.score = 8.0
    s.mark_sent(a)
    a.score = 3.0
    s.record_scores([a])
    assert s.new_only([P("a")]) == [] and s.cached_scores([P("a")]) == {"a": 3.0}
