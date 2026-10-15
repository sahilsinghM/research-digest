import json
from datetime import datetime, timedelta, timezone

import daily10
from oa_fixtures import FakeOpenAlex, W
from store import Store

NOW = datetime(2026, 10, 15, 1, 30, tzinfo=timezone.utc)
SHARPE = W("W8", "Capital Asset Prices: A Theory of Market Equilibrium", 1964, 19365, authors=("William F. Sharpe",))
BS = W("W1", "The Pricing of Options and Corporate Liabilities", 1973, 28883, refs=("W8",),
       abstract="", authors=("Fischer Black", "Myron Scholes"), oa="https://x/bs.pdf")
HESTON = W("W21", "A Closed-Form Solution for Options with Stochastic Volatility", 1993, 8762, refs=("W1",), authors=("Steven L. Heston",))
PATH = '''name = "Finance: risk and pricing"

[[step]]
title = "Capital Asset Prices: A Theory of Market Equilibrium"
authors = ["Sharpe"]
year = 1964
note = "risk and return"

[[step]]
title = "The Pricing of Options and Corporate Liabilities"
authors = ["Black", "Scholes"]
year = 1973

[[step]]
title = "A Closed-Form Solution for Options with Stochastic Volatility"
authors = ["Heston"]
year = 1993
'''
CFG = {"models": {"analyse": "sonnet"}, "foundations": {"enabled": True, "path": "p"}}
LESSON = {"headline": "A fair price for an option", "idea": ["Line one.", "Line two."], "look_for": "the no-arbitrage argument",
          "your_sentence": "An option's price depends on ___ because ___.", "recall": [{"q": "Why hedge?", "a": "To remove risk."}],
          "prereads": [{"term": "Option", "plain": "a right, not a duty, to buy or sell", "example": ""}],
          "year": 1999, "cited_by_count": 5}


class Ask:
    def __init__(self, reply):
        self.reply, self.calls = reply, []

    def __call__(self, model, system, user):
        self.calls.append((model, system, user))
        return self.reply


def prepare(tmp_path, ask, api=None, known=(), store=None, path=PATH, now=NOW, dry_run=False, cfg=CFG):
    (tmp_path / "p.toml").write_text(path)
    return daily10.prepare(cfg, "profile", store or Store(":memory:"), ask, api or FakeOpenAlex(SHARPE, BS, HESTON),
                           list(known), now, paths_dir=tmp_path, dry_run=dry_run)


def day(n):
    return NOW + timedelta(days=n)


def test_the_first_day_is_the_first_step_with_facts_from_data_not_from_the_model(tmp_path):
    ask = Ask(json.dumps(LESSON))
    d = prepare(tmp_path, ask)
    data = json.loads(ask.calls[0][2])
    assert data["year"] == 1964 and data["why_here"] == "risk and return"
    assert "Day 1 of 3" in d.message and "1964" in d.message and "19,365" in d.message and "1999" not in d.message
    assert d.terms == ["Option"]


def test_a_step_counts_as_done_only_when_the_message_is_committed_after_delivery(tmp_path):
    store, ask = Store(":memory:"), Ask(json.dumps(LESSON))
    first = prepare(tmp_path, ask, store=store)
    again = prepare(tmp_path, ask, store=store)  # nothing was committed (e.g. the send failed)
    assert "Day 1 of 3" in again.message
    first.commit()
    second = prepare(tmp_path, ask, store=store, now=day(1))
    assert "Day 2 of 3" in second.message and "The Pricing of Options" in second.message
    assert "Background knowledge" in second.message  # BS has no abstract in this fixture
    second.commit()
    third = prepare(tmp_path, ask, store=store, now=day(2))
    assert "Day 3 of 3" in third.message
    third.commit()
    with pytest.raises(daily10.LessonUnavailable, match="path complete"):  # complete, but recall cards are still owed
        prepare(tmp_path, ask, store=store, now=day(40))


def test_later_days_make_no_outside_calls_once_the_path_is_cached(tmp_path):
    store, api, ask = Store(":memory:"), FakeOpenAlex(SHARPE, BS, HESTON), Ask(json.dumps(LESSON))
    prepare(tmp_path, ask, api, store=store).commit()
    calls = len(api.calls)
    prepare(tmp_path, ask, api, store=store, now=day(1))
    assert len(api.calls) == calls


def test_an_unverifiable_entry_is_skipped_with_a_visible_note(tmp_path):
    bad = PATH + '\n[[step]]\ntitle = "No Such Paper At All"\nauthors = ["Nobody"]\nyear = 1999\n'
    d = prepare(tmp_path, Ask(json.dumps(LESSON)), path=bad)
    assert "Day 1 of 3" in d.message and "No Such Paper At All" in d.message and "could not verify" in d.message.lower()


def test_prepare_returns_none_when_the_feature_is_off(tmp_path):
    (tmp_path / "p.toml").write_text(PATH)
    cfg = {**CFG, "foundations": {"enabled": False, "path": "p"}}
    assert daily10.prepare(cfg, "profile", Store(":memory:"), Ask("{}"), FakeOpenAlex(), [], NOW, paths_dir=tmp_path) is None


# ---- spaced recall inside the Daily 10 ----

def test_day_one_has_no_recall_and_the_next_day_shows_yesterdays_question_hidden_behind_a_spoiler(tmp_path):
    store, ask = Store(":memory:"), Ask(json.dumps(LESSON))
    d1 = prepare(tmp_path, ask, store=store)
    assert "Recall" not in d1.message
    d1.commit()
    (tmp_path / "p.toml").write_text(PATH)
    d2 = daily10.prepare(CFG, "profile", store, ask, FakeOpenAlex(SHARPE, BS, HESTON), [], NOW + timedelta(days=1), paths_dir=tmp_path)
    assert "Recall" in d2.message and "Why hedge?" in d2.message and "<tg-spoiler>To remove risk.</tg-spoiler>" in d2.message


def test_a_recall_card_is_marked_shown_only_after_the_day_is_delivered(tmp_path):
    store, ask = Store(":memory:"), Ask(json.dumps(LESSON))
    prepare(tmp_path, ask, store=store).commit()
    nxt = NOW + timedelta(days=1)

    def day2():
        return daily10.prepare(CFG, "profile", store, ask, FakeOpenAlex(SHARPE, BS, HESTON), [], nxt, paths_dir=tmp_path)

    first = day2()
    assert "Why hedge?" in first.message
    assert "Why hedge?" in day2().message  # the send failed, nothing committed: it is still due
    first.commit()
    assert day2() is None  # delivered: nothing more the same day (neither a second lesson nor the card again)


def test_recall_days_and_the_daily_cap_come_from_config(tmp_path):
    ask = Ask(json.dumps({**LESSON, "recall": [{"q": f"Q{i}", "a": "A"} for i in range(2)]}))
    cfg = {**CFG, "foundations": {**CFG["foundations"], "recall_days": [2], "max_recall_per_day": 1}}
    (tmp_path / "p.toml").write_text(PATH)
    api = FakeOpenAlex(SHARPE, BS, HESTON)
    store = Store(":memory:")
    prepare(tmp_path, ask, store=store, cfg=cfg).commit()

    def day(n):
        return daily10.prepare(cfg, "profile", store, ask, api, [], NOW + timedelta(days=n), paths_dir=tmp_path)

    assert "Recall" not in day(1).message
    two = day(2)
    assert two.message.count("<tg-spoiler>") == 1


# ---- issue 16: bad days ----

import pytest  # noqa: E402

import openalex  # noqa: E402


def _seed_a_card_for_tomorrow(tmp_path, store):
    prepare(tmp_path, Ask(json.dumps(LESSON)), store=store).commit()
    return NOW + timedelta(days=1)


def _tomorrow(tmp_path, store, api, ask, day):
    (tmp_path / "p.toml").write_text(PATH)
    return daily10.prepare(CFG, "profile", store, ask, api, [], day, paths_dir=tmp_path)


def test_when_the_citation_service_is_down_the_day_still_delivers_the_recall_cards_and_retries_the_step_tomorrow(tmp_path):
    store = Store(":memory:")  # a card from an earlier day, but the path is not cached yet
    store.add_cards("Finance: risk and pricing", "old|1960", [{"q": "Why hedge?", "a": "To remove risk."}], NOW.date())
    day2 = NOW + timedelta(days=1)
    api = FakeOpenAlex()
    api.fail = openalex.OpenAlexError("OpenAlex unavailable after 3 tries (HTTP 503)")
    with pytest.raises(daily10.LessonUnavailable) as e:
        _tomorrow(tmp_path, store, api, Ask(json.dumps(LESSON)), day2)
    assert "OpenAlexError" in e.value.reason
    fallback = e.value.fallback
    assert "recall only" in fallback.message.lower() and "Why hedge?" in fallback.message
    assert "<tg-spoiler>To remove risk.</tg-spoiler>" in fallback.message
    fallback.commit()
    assert store.done_steps("p") == set()  # no step was consumed by the outage
    again = _tomorrow(tmp_path, store, FakeOpenAlex(SHARPE, BS, HESTON), Ask(json.dumps(LESSON)), day2 + timedelta(days=1))
    assert "Day 1 of 3" in again.message  # the lesson that failed is simply still the next one: the place was not lost
    assert "Why hedge?" not in again.message  # and the card shown during the outage is not shown twice


def test_with_nothing_to_recall_a_service_outage_gives_no_fallback_message(tmp_path):
    api = FakeOpenAlex()
    api.fail = openalex.OpenAlexError("down")
    with pytest.raises(daily10.LessonUnavailable) as e:
        prepare(tmp_path, Ask("{}"), api=api)
    assert e.value.fallback is None


def test_a_broken_path_file_is_reported_not_a_crash(tmp_path):
    with pytest.raises(daily10.LessonUnavailable) as e:
        prepare(tmp_path, Ask("{}"), path="this is = not [valid toml")
    assert "PathError" in e.value.reason


def test_a_lesson_the_model_could_not_write_is_reported_with_the_recall_fallback(tmp_path):
    store = Store(":memory:")
    day2 = _seed_a_card_for_tomorrow(tmp_path, store)
    with pytest.raises(daily10.LessonUnavailable) as e:
        _tomorrow(tmp_path, store, FakeOpenAlex(SHARPE, BS, HESTON), Ask("junk"), day2)
    assert "lesson" in e.value.reason.lower() and "Why hedge?" in e.value.fallback.message


def test_a_finished_path_still_offers_recall_and_then_goes_quiet(tmp_path):
    store, ask = Store(":memory:"), Ask(json.dumps(LESSON))
    day = NOW
    for _ in range(3):
        (tmp_path / "p.toml").write_text(PATH)
        daily10.prepare(CFG, "profile", store, ask, FakeOpenAlex(SHARPE, BS, HESTON), [], day, paths_dir=tmp_path).commit()
        day += timedelta(days=1)
    with pytest.raises(daily10.LessonUnavailable) as e:
        _tomorrow(tmp_path, store, FakeOpenAlex(SHARPE, BS, HESTON), ask, day)
    assert "complete" in e.value.reason.lower() and "recall only" in e.value.fallback.message.lower()
    far = NOW + timedelta(days=200)  # overdue cards are offered (capped per day) until each has been shown once
    for _ in range(5):
        try:
            result = _tomorrow(tmp_path, store, FakeOpenAlex(SHARPE, BS, HESTON), ask, far)
        except daily10.LessonUnavailable as again:
            again.fallback.commit()
            continue
        assert result is None  # then it goes quiet
        break
    else:
        raise AssertionError("recall cards kept coming back forever")


def test_citation_counts_are_labelled_as_openalexs_own(tmp_path):
    assert "cited 19,365 times in OpenAlex" in prepare(tmp_path, Ask(json.dumps(LESSON))).message


def test_a_cached_path_survives_a_service_outage_untouched(tmp_path):
    store, ask = Store(":memory:"), Ask(json.dumps(LESSON))
    prepare(tmp_path, ask, store=store).commit()
    down = FakeOpenAlex()
    down.fail = openalex.OpenAlexError("down")
    d = _tomorrow(tmp_path, store, down, ask, NOW + timedelta(days=1))
    assert "Day 2 of 3" in d.message and down.calls == []


# ---- review fixes ----

def test_a_second_run_the_same_day_gets_no_second_lesson_but_tomorrow_does(tmp_path):
    store, ask = Store(":memory:"), Ask(json.dumps(LESSON))
    prepare(tmp_path, ask, store=store).commit()
    assert prepare(tmp_path, ask, store=store, now=NOW + timedelta(hours=5)) is None
    assert "Day 2 of 3" in prepare(tmp_path, ask, store=store, now=day(1)).message


def test_renaming_the_path_in_the_file_does_not_reset_progress(tmp_path):
    store, ask = Store(":memory:"), Ask(json.dumps(LESSON))
    prepare(tmp_path, ask, store=store).commit()
    renamed = PATH.replace("Finance: risk and pricing", "Finance: a better name")
    assert "Day 2 of 3" in prepare(tmp_path, ask, store=store, path=renamed, now=day(1)).message


def test_a_dry_run_does_not_cache_the_path_but_does_not_break_later_real_runs(tmp_path):
    store, ask = Store(":memory:"), Ask(json.dumps(LESSON))
    d = prepare(tmp_path, ask, store=store, dry_run=True)
    assert "Day 1 of 3" in d.message and store.get_path_cache("p") == {}
    assert "Day 1 of 3" in prepare(tmp_path, ask, store=store).message and store.get_path_cache("p") != {}
