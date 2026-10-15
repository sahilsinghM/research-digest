import tomllib


def load():
    with open("config.toml", "rb") as f:
        return tomllib.load(f)


def test_quota_areas():
    assert set(load()["quota"]) == {"finance", "science", "medical"}


def test_models_configured_and_no_dollar_pricing():
    cfg = load()
    assert set(cfg["models"]) == {"triage", "analyse"}
    assert "prices" not in cfg and "daily_cost_cap_usd" not in cfg["run"]


def test_journals_well_formed():
    for j in load()["journal"]:
        assert j["area"] in {"finance", "science"} and len(j["issn"]) == 9


def test_call_cap_and_triage_batch_configured():
    run = load()["run"]
    assert run["max_calls_per_run"] >= 20 and run["triage_batch"] >= 10


def test_minimum_abstract_length_configured():
    assert load()["run"]["min_abstract_chars"] >= 50


def test_abstract_poor_journals_are_recovered_through_pubmed():
    groups = load()["pubmed_extra"]
    science = [g for g in groups if g["area"] == "science"]
    assert science and {"Nature", "Cell"} <= set(science[0]["journals"])


def test_new_papers_must_clear_a_high_bar_and_are_limited_when_the_daily10_is_on():
    f = load()["foundations"]
    assert f["new_paper_min_score"] >= 7 and 0 <= f["max_new_papers"] <= 2 and f["enabled"] is True
