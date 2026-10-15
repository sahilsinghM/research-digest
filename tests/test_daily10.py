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


def prepare(tmp_path, ask, api=None, known=(), store=None, path=PATH):
    (tmp_path / "p.toml").write_text(path)
    return daily10.prepare(CFG, "profile", store or Store(":memory:"), ask, api or FakeOpenAlex(SHARPE, BS, HESTON),
                           list(known), NOW, paths_dir=tmp_path)


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
    second = prepare(tmp_path, ask, store=store)
    assert "Day 2 of 3" in second.message and "The Pricing of Options" in second.message
    assert "Background knowledge" in second.message  # BS has no abstract in this fixture
    second.commit()
    third = prepare(tmp_path, ask, store=store)
    assert "Day 3 of 3" in third.message
    third.commit()
    assert prepare(tmp_path, ask, store=store) is None  # the path is complete


def test_later_days_make_no_outside_calls_once_the_path_is_cached(tmp_path):
    store, api, ask = Store(":memory:"), FakeOpenAlex(SHARPE, BS, HESTON), Ask(json.dumps(LESSON))
    prepare(tmp_path, ask, api, store=store).commit()
    calls = len(api.calls)
    prepare(tmp_path, ask, api, store=store)
    assert len(api.calls) == calls


def test_an_unverifiable_entry_is_skipped_with_a_visible_note(tmp_path):
    bad = PATH + '\n[[step]]\ntitle = "No Such Paper At All"\nauthors = ["Nobody"]\nyear = 1999\n'
    d = prepare(tmp_path, Ask(json.dumps(LESSON)), path=bad)
    assert "Day 1 of 3" in d.message and "No Such Paper At All" in d.message and "could not verify" in d.message.lower()


def test_prepare_returns_none_when_the_model_gives_nothing_usable_or_the_feature_is_off(tmp_path):
    assert prepare(tmp_path, Ask("junk")) is None
    (tmp_path / "p.toml").write_text(PATH)
    cfg = {**CFG, "foundations": {"enabled": False, "path": "p"}}
    assert daily10.prepare(cfg, "profile", Store(":memory:"), Ask("{}"), FakeOpenAlex(), [], NOW, paths_dir=tmp_path) is None
