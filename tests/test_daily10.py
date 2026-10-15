import json
from datetime import datetime, timezone

import daily10
from oa_fixtures import FakeOpenAlex, W
from store import Store

NOW = datetime(2026, 10, 15, 1, 30, tzinfo=timezone.utc)
SHARPE = W("W8", "Capital Asset Prices: A Theory of Market Equilibrium", 1964, 19365, authors=("William F. Sharpe",))
BS = W("W1", "The Pricing of Options and Corporate Liabilities", 1973, 28883, refs=("W8",),
       abstract="", authors=("Fischer Black", "Myron Scholes"), oa="https://x/bs.pdf")
HESTON = W("W21", "A Closed-Form Solution for Options with Stochastic Volatility", 1993, 8762, refs=("W1",))
PATH = '''name = "Finance: risk and pricing"

[[step]]
title = "The Pricing of Options and Corporate Liabilities"
authors = ["Black", "Scholes"]
year = 1973
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


def prepare(tmp_path, ask, api=None, known=()):
    (tmp_path / "p.toml").write_text(PATH)
    return daily10.prepare(CFG, "profile", Store(":memory:"), ask, api or FakeOpenAlex(BS, SHARPE, HESTON), list(known), NOW,
                           paths_dir=tmp_path)


def test_prepare_builds_the_message_with_facts_from_data_not_from_the_model(tmp_path):
    d = prepare(tmp_path, Ask(json.dumps(LESSON)))
    assert "A fair price for an option" in d.message
    assert "1973" in d.message and "28,883" in d.message and "1999" not in d.message  # the model's own numbers are ignored
    assert "Capital Asset Prices" in d.message and "1993" in d.message  # built on / led to come from the data
    assert "https://x/bs.pdf" in d.message


def test_prepare_sends_the_paper_as_data_with_the_known_terms_and_flags_missing_abstract(tmp_path):
    ask = Ask(json.dumps(LESSON))
    d = prepare(tmp_path, ask, known=["Spread"])
    model, system, user = ask.calls[0]
    data = json.loads(user)
    assert model == "sonnet" and data["title"].startswith("The Pricing") and data["year"] == 1973
    assert data["abstract"] == "(none available)" and data["already_known_terms"] == ["Spread"]
    assert [t["title"][:7] for t in data["built_on"]] == ["Capital"]
    assert "Background knowledge" in d.message
    assert d.terms == ["Option"]


def test_prepare_returns_none_when_the_model_gives_nothing_usable(tmp_path):
    assert prepare(tmp_path, Ask("junk")) is None


def test_prepare_returns_none_when_the_feature_is_off(tmp_path):
    (tmp_path / "p.toml").write_text(PATH)
    cfg = {**CFG, "foundations": {"enabled": False, "path": "p"}}
    assert daily10.prepare(cfg, "profile", Store(":memory:"), Ask("{}"), FakeOpenAlex(), [], NOW, paths_dir=tmp_path) is None
