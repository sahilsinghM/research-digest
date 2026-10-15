import pytest

import paths
from oa_fixtures import FakeOpenAlex, W

SHARPE = W("W8", "Capital Asset Prices: A Theory of Market Equilibrium", 1964, 19365, authors=("William F. Sharpe",))
MM = W("W9", "The Cost of Capital, Corporation Finance and the Theory of Investment", 1958, 14488, authors=("Franco Modigliani",))
BS = W("W1", "The Pricing of Options and Corporate Liabilities", 1973, 28883, refs=("W8", "W9"),
       abstract="", authors=("Fischer Black", "Myron Scholes"))
MERTON = W("W20", "Option pricing when underlying stock returns are discontinuous", 1976, 5953, refs=("W1",))
HESTON = W("W21", "A Closed-Form Solution for Options with Stochastic Volatility", 1993, 8762, refs=("W1",))
ENTRY = {"title": BS["display_name"], "authors": ["Black", "Scholes"], "year": 1973}

GOOD = '''name = "Finance: risk, pricing and behaviour"

[[step]]
title = "The Pricing of Options and Corporate Liabilities"
authors = ["Black", "Scholes"]
year = 1973
note = "the foundation of option pricing"

[[step]]
title = "Portfolio Selection"
year = 1952
'''


def write(tmp_path, text):
    f = tmp_path / "p.toml"
    f.write_text(text)
    return f


def test_load_path_returns_the_name_and_ordered_entries(tmp_path):
    name, steps = paths.load_path(write(tmp_path, GOOD))
    assert name == "Finance: risk, pricing and behaviour" and len(steps) == 2
    assert steps[0] == {"title": "The Pricing of Options and Corporate Liabilities", "authors": ["Black", "Scholes"],
                        "year": 1973, "note": "the foundation of option pricing"}
    assert steps[1]["authors"] == [] and steps[1]["year"] == 1952


@pytest.mark.parametrize("text", [
    "this is = not [valid toml",
    'name = "x"\n',
    'name = "x"\n[[step]]\nyear = 1973\n',
    'name = "x"\n[[step]]\ntitle = "T"\nyear = "1973"\n',
    '[[step]]\ntitle = "T"\nyear = 1973\n',
])
def test_a_malformed_path_file_is_a_clear_error_not_a_crash(tmp_path, text):
    with pytest.raises(paths.PathError):
        paths.load_path(write(tmp_path, text))


def test_a_missing_path_file_is_a_clear_error(tmp_path):
    with pytest.raises(paths.PathError, match="not found"):
        paths.load_path(tmp_path / "nope.toml")


def test_build_step_resolves_the_paper_and_finds_what_it_built_on_and_led_to_from_data():
    api = FakeOpenAlex(BS, SHARPE, MM, MERTON, HESTON)
    step = paths.build_step(api, [ENTRY], 0)
    assert step.work.id == "W1" and (step.index, step.total) == (0, 1)
    assert [w.title for w in step.built_on][0].startswith("Capital Asset Prices")  # most cited first
    assert [w.year for w in step.led_to] == [1993, 1976]
    assert step.background is True  # this work has no abstract


def test_build_step_without_an_abstract_vs_with_one():
    with_abs = W("W1", BS["display_name"], 1973, 1, abstract="An abstract.", authors=("Fischer Black",))
    assert paths.build_step(FakeOpenAlex(with_abs), [ENTRY], 0).background is False


def test_build_step_reports_an_unresolvable_entry_as_unavailable_with_the_reason():
    with pytest.raises(paths.StepUnavailable, match="not found"):
        paths.build_step(FakeOpenAlex(), [ENTRY], 0)
