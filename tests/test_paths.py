import pytest

import paths
from oa_fixtures import FakeOpenAlex, W
from store import Store

MARK = W("W5", "Portfolio Selection", 1952, 30000, authors=("Harry Markowitz",), abstract="x" * 80)
SHARPE = W("W8", "CAPITAL ASSET PRICES: A THEORY OF MARKET EQUILIBRIUM UNDER CONDITIONS OF RISK", 1964, 19365, refs=("W5",),
           authors=("William F. Sharpe",))
MM = W("W9", "The Cost of Capital, Corporation Finance and the Theory of Investment", 1958, 14488, authors=("Franco Modigliani",))
REPRINT = W("W30", "Theory of rational option pricing", 2005, 7161, type="book-chapter", authors=("Robert C. Merton",))
OFFTOPIC_REF = W("W31", "Management of Things", 1960, 99999, authors=("Pat Manager",), subfield="Management")
BS = W("W1", "The Pricing of Options and Corporate Liabilities", 1973, 28883, refs=("W8", "W9", "W30", "W31", "W5"),
       authors=("Fischer Black", "Myron Scholes"))
MERTON = W("W20", "Option pricing when underlying stock returns are discontinuous", 1976, 5953, refs=("W1",), authors=("Robert C. Merton",))
HESTON = W("W21", "A Closed-Form Solution for Options with Stochastic Volatility", 1993, 8762, refs=("W1",), authors=("Steven L. Heston",))
AGENCY = W("W32", "Theory of the firm: agency costs and ownership structure", 1976, 71095, refs=("W1",), authors=("Michael Jensen",),
           subfield="Management")
LATER = W("W33", "Some later on-topic article", 1985, 400, refs=("W1",), authors=("Lee Later",))

E = lambda w, authors=(): {"title": w["display_name"], "authors": list(authors), "year": w["publication_year"], "note": ""}  # noqa: E731
ENTRIES = [E(MARK, ["Markowitz"]), E(SHARPE, ["Sharpe"]), E(BS, ["Black"]), E(MERTON, ["Merton"]), E(HESTON, ["Heston"])]
ALL = [MARK, SHARPE, MM, REPRINT, OFFTOPIC_REF, BS, MERTON, HESTON, AGENCY, LATER]

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


def load(api=None, entries=ENTRIES, store=None):
    return paths.load_steps(api or FakeOpenAlex(*ALL), store or Store(":memory:"), "P", entries)


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
    'name = "x"\n[[step]]\ntitle = "T"\nyear = 1973\nauthors = "Black"\n',
])
def test_a_malformed_path_file_is_a_clear_error_not_a_crash(tmp_path, text):
    with pytest.raises(paths.PathError):
        paths.load_path(write(tmp_path, text))


def test_a_missing_path_file_is_a_clear_error(tmp_path):
    with pytest.raises(paths.PathError, match="not found"):
        paths.load_path(tmp_path / "nope.toml")


def test_every_entry_is_resolved_in_order_and_numbered_among_the_verified_steps():
    steps, flagged = load()
    assert [s.work.id for s in steps] == ["W5", "W8", "W1", "W20", "W21"]
    assert [(s.index, s.total) for s in steps] == [(i, 5) for i in range(5)] and flagged == []


def test_an_entry_that_cannot_be_verified_is_skipped_with_the_reason_not_silently_dropped():
    bogus = {"title": "A Paper That Does Not Exist", "authors": ["Nobody"], "year": 1999, "note": ""}
    steps, flagged = load(entries=[ENTRIES[0], bogus, ENTRIES[2]])
    assert [s.work.id for s in steps] == ["W5", "W1"] and [s.total for s in steps] == [2, 2]
    assert flagged[0][0] == bogus and "not found" in flagged[0][1].lower()


def test_built_on_and_led_to_prefer_members_of_the_path_and_are_shown_in_story_order():
    steps, _ = load()
    bs = steps[2]
    assert [w.id for w in bs.built_on][-2:] == ["W8", "W9"] or {"W8", "W5"} <= {w.id for w in bs.built_on}
    assert [w.year for w in bs.led_to] == sorted(w.year for w in bs.led_to)
    assert {"W20", "W21"} <= {w.id for w in bs.led_to}


def test_edges_drop_reprints_off_topic_works_and_anything_from_the_wrong_side_of_time():
    steps, _ = load()
    bs = steps[2]
    built, led = {w.id for w in bs.built_on}, {w.id for w in bs.led_to}
    assert "W30" not in built       # a 2005 reprint cannot be something 1973 was built on
    assert "W31" not in built       # off-topic (different subfield), even though hugely cited
    assert "W32" not in led         # the agency-costs paper cites it but is off topic
    assert all(w.year <= 1973 for w in bs.built_on) and all(w.year >= 1973 for w in bs.led_to)


def test_edges_are_at_most_three_each_and_free_of_duplicate_titles():
    dup = W("W34", "Capital Asset Prices: A Theory of Market Equilibrium Under Conditions of Risk", 1964, 5, authors=("Reprint Co",))
    bs = W("W1", BS["display_name"], 1973, 28883, refs=("W8", "W34", "W9", "W5"), authors=("Fischer Black",))
    steps, _ = load(FakeOpenAlex(MARK, SHARPE, MM, dup, bs), entries=[ENTRIES[2]])
    titles = [w.title.lower() for w in steps[0].built_on]
    assert len(steps[0].built_on) <= 3 and len({t[:20] for t in titles}) == len(titles)


def test_all_caps_titles_are_tidied():
    steps, _ = load()
    assert steps[1].work.title == "Capital Asset Prices: A Theory Of Market Equilibrium Under Conditions Of Risk"


def test_fill_in_edges_when_no_path_member_connects():
    steps, _ = load(entries=[ENTRIES[2]])  # a path of one: the neighbours must come from the data
    assert {w.id for w in steps[0].led_to} == {"W20", "W21", "W33"} and "W32" not in {w.id for w in steps[0].led_to}
    assert "W9" in {w.id for w in steps[0].built_on}


def test_later_days_need_no_outside_calls_once_the_path_is_cached():
    store, api = Store(":memory:"), FakeOpenAlex(*ALL)
    first, _ = paths.load_steps(api, store, "P", ENTRIES)
    calls = len(api.calls)
    assert calls > 0
    second, _ = paths.load_steps(api, store, "P", ENTRIES)
    assert len(api.calls) == calls
    assert [(s.work.id, [w.id for w in s.built_on], [w.id for w in s.led_to]) for s in second] == \
           [(s.work.id, [w.id for w in s.built_on], [w.id for w in s.led_to]) for s in first]
    assert second[2].work.title == first[2].work.title


def test_a_new_entry_added_to_the_file_is_resolved_without_redoing_the_cached_ones():
    store, api = Store(":memory:"), FakeOpenAlex(*ALL)
    paths.load_steps(api, store, "P", ENTRIES[:2])
    api.calls.clear()
    steps, _ = paths.load_steps(api, store, "P", ENTRIES[:3])
    assert [s.work.id for s in steps] == ["W5", "W8", "W1"]
    assert not any(c[1].get("search", "").lower().startswith("portfolio") for c in api.calls)


def test_fixing_the_authors_of_a_wrongly_matched_entry_takes_effect_instead_of_being_ignored_forever():
    wrong = W("W40", "A Generic Title", 1990, 900, authors=("Wendy Wrong",))
    right = W("W41", "A Generic Title", 1990, 50, authors=("Rita Right",))
    api, store = FakeOpenAlex(wrong, right), Store(":memory:")
    loose = {"title": "A Generic Title", "authors": [], "year": 1990, "note": ""}
    steps, _ = paths.load_steps(api, store, "P", [loose])
    assert steps[0].work.id == "W40"          # no authors given: the most cited title match wins
    fixed = {**loose, "authors": ["Right"]}
    steps, _ = paths.load_steps(api, store, "P", [fixed])
    assert steps[0].work.id == "W41"          # the owner's correction is honoured, not shadowed by the old cache
    assert paths.entry_key(loose) == paths.entry_key(fixed)  # ...while the lesson's identity (done/not done) is unchanged


def test_load_steps_can_skip_writing_the_cache():
    store = Store(":memory:")
    paths.load_steps(FakeOpenAlex(*ALL), store, "P", ENTRIES, persist=False)
    assert store.get_path_cache("P") == {}
