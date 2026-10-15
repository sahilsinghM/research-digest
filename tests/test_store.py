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


# ---- spaced recall cards (each review is scheduled from when the card was ACTUALLY shown) ----

from datetime import date  # noqa: E402

D0 = date(2026, 10, 1)


def _run_days(store, days, limit=2, intervals=(1, 3, 7, 21), start=D0):
    """The daily loop like the pipeline: ask what is due, then (after delivery) mark it shown."""
    shown = {}
    for n in range(days + 1):
        today = start + timedelta(days=n)
        due = store.due_cards(today, limit)
        for c in due:
            shown.setdefault(c["q"], []).append(n)
        store.mark_cards_shown(due, today, intervals)
    return shown


def test_a_card_comes_back_exactly_on_days_1_3_7_and_21():
    s = Store(":memory:")
    s.add_cards("P", "k", [{"q": "Q1", "a": "A1"}], D0)
    assert _run_days(s, 40) == {"Q1": [1, 3, 7, 21]}


def test_nothing_is_due_on_the_day_a_card_is_created():
    s = Store(":memory:")
    s.add_cards("P", "k", [{"q": "Q1", "a": "A1"}], D0)
    assert s.due_cards(D0, 2) == []


def test_at_most_the_cap_per_day_and_the_overflow_waits_without_being_lost():
    s = Store(":memory:")
    s.add_cards("P", "k", [{"q": f"Q{i}", "a": "A"} for i in range(3)], D0)
    shown = _run_days(s, 2)
    assert sorted(d for ds in shown.values() for d in ds) == [1, 1, 2] and len(shown) == 3


def test_a_card_is_not_repeated_after_it_was_shown_even_if_the_run_repeats_the_same_day():
    s = Store(":memory:")
    s.add_cards("P", "k", [{"q": "Q1", "a": "A1"}], D0)
    today = D0 + timedelta(days=1)
    due = s.due_cards(today, 2)
    assert len(due) == 1 and len(s.due_cards(today, 2)) == 1  # not marked yet (the send failed): still due
    s.mark_cards_shown(due, today)
    assert s.due_cards(today, 2) == []


def test_a_late_card_shifts_its_whole_schedule_instead_of_replaying_missed_intervals():
    s = Store(":memory:")
    s.add_cards("P", "k", [{"q": "Q1", "a": "A1"}], D0)
    late = D0 + timedelta(days=10)  # the job did not run for a week
    due = s.due_cards(late, 2)
    assert len(due) == 1
    s.mark_cards_shown(due, late)
    assert s.due_cards(late + timedelta(days=1), 2) == []          # no replay the very next day
    assert len(s.due_cards(late + timedelta(days=2), 2)) == 1       # the next gap (3 - 1 days) counts from NOW
    shown = _run_days(s, 60, start=D0)
    assert len(shown["Q1"]) == 3                                    # the remaining three reviews still happen


def test_a_backlog_beyond_the_daily_cap_never_costs_a_card_a_repetition():
    s = Store(":memory:")
    for lesson in range(15):  # one lesson a day, two recall cards each, a cap of two reviews per day
        s.add_cards("P", f"k{lesson}", [{"q": f"L{lesson}Q{i}", "a": "A"} for i in range(2)], D0 + timedelta(days=lesson))
    shown = _run_days(s, 200, limit=2)
    assert len(shown) == 30 and all(len(days) == 4 for days in shown.values())


def test_the_same_day_gap_never_makes_a_card_due_twice_in_one_day():
    s = Store(":memory:")
    s.add_cards("P", "k", [{"q": "Q1", "a": "A1"}], D0, intervals=(1, 1, 5))
    day1 = D0 + timedelta(days=1)
    s.mark_cards_shown(s.due_cards(day1, 2), day1, (1, 1, 5))
    assert s.due_cards(day1, 2) == []


def test_the_last_study_day_of_a_path_is_remembered():
    s = Store(":memory:")
    assert s.last_step_done("P") is None
    s.mark_step_done("P", "a|1", NOW)
    s.mark_step_done("P", "b|2", NOW + timedelta(days=1))
    assert s.last_step_done("P").date() == (NOW + timedelta(days=1)).date() and s.last_step_done("Q") is None
