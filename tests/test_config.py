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
