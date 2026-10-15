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


def test_taught_concepts_come_back_newest_first_and_are_limited():
    s = Store(":memory:")
    for i, name in enumerate(["Overfitting", "Drawdown", "Sharpe ratio"]):
        s.record_concept(name, NOW + timedelta(days=i))
    assert s.recent_concepts(limit=2) == ["Sharpe ratio", "Drawdown"]
    assert s.recent_concepts() == ["Sharpe ratio", "Drawdown", "Overfitting"]


def test_recording_the_same_concept_twice_keeps_one_entry():
    s = Store(":memory:")
    s.record_concept("Drawdown", NOW)
    s.record_concept("Drawdown", NOW + timedelta(days=1))
    assert s.recent_concepts() == ["Drawdown"]


def test_path_cache_roundtrip_and_isolated_per_path():
    s = Store(":memory:")
    s.put_path_cache("P1", "k|1973", {"work": {"id": "W1"}, "built_on": [], "led_to": []})
    assert s.get_path_cache("P1") == {"k|1973": {"work": {"id": "W1"}, "built_on": [], "led_to": []}}
    assert s.get_path_cache("P2") == {}


def test_steps_marked_done_are_remembered_per_path_and_marking_twice_is_fine():
    s = Store(":memory:")
    s.mark_step_done("P1", "k|1973", NOW)
    s.mark_step_done("P1", "k|1973", NOW + timedelta(days=1))
    assert s.done_steps("P1") == {"k|1973"} and s.done_steps("P2") == set()


# ---- spaced recall cards ----

from datetime import date  # noqa: E402


def _simulate(store, days, intervals=(1, 3, 7, 21), limit=2):
    """Run the daily loop like the pipeline: ask what is due, then (after delivery) mark it shown."""
    shown = {}
    d0 = date(2026, 10, 1)
    for n in range(days + 1):
        today = d0 + timedelta(days=n)
        due = store.due_cards(today, list(intervals), limit)
        for c in due:
            shown.setdefault(c["q"], []).append(n)
        store.mark_cards_shown(due, today)
    return shown


def test_a_card_comes_back_exactly_on_days_1_3_7_and_21():
    s = Store(":memory:")
    s.add_cards("P", "k", [{"q": "Q1", "a": "A1"}], date(2026, 10, 1))
    assert _simulate(s, 40) == {"Q1": [1, 3, 7, 21]}


def test_nothing_is_due_on_the_day_a_card_is_created():
    s = Store(":memory:")
    s.add_cards("P", "k", [{"q": "Q1", "a": "A1"}], date(2026, 10, 1))
    assert s.due_cards(date(2026, 10, 1), [1, 3, 7, 21], 2) == []


def test_at_most_the_cap_per_day_and_overflow_waits_a_day_without_being_lost():
    s = Store(":memory:")
    s.add_cards("P", "k", [{"q": f"Q{i}", "a": "A"} for i in range(3)], date(2026, 10, 1))
    shown = _simulate(s, 3)
    assert sorted(d for ds in shown.values() for d in ds if d <= 2) == [1, 1, 2]  # two on day 1, the third on day 2
    assert len(shown) == 3


def test_a_card_is_not_repeated_after_it_was_shown_even_if_the_run_repeats_the_same_day():
    s = Store(":memory:")
    s.add_cards("P", "k", [{"q": "Q1", "a": "A1"}], date(2026, 10, 1))
    today = date(2026, 10, 2)
    due = s.due_cards(today, [1, 3, 7, 21], 2)
    assert len(due) == 1
    assert len(s.due_cards(today, [1, 3, 7, 21], 2)) == 1  # not marked yet (e.g. the send failed): still due
    s.mark_cards_shown(due, today)
    assert s.due_cards(today, [1, 3, 7, 21], 2) == []


def test_missed_days_catch_up_once_without_replaying_every_skipped_interval():
    s = Store(":memory:")
    s.add_cards("P", "k", [{"q": "Q1", "a": "A1"}], date(2026, 10, 1))
    today = date(2026, 10, 10)  # the job did not run for a week: intervals 1, 3 and 7 are all overdue
    due = s.due_cards(today, [1, 3, 7, 21], 2)
    assert len(due) == 1
    s.mark_cards_shown(due, today)
    assert s.due_cards(date(2026, 10, 11), [1, 3, 7, 21], 2) == []
    assert len(s.due_cards(date(2026, 10, 22), [1, 3, 7, 21], 2)) == 1  # 21 days after creation
