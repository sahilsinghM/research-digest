import tomllib


def load():
    with open("config.toml", "rb") as f:
        return tomllib.load(f)


def test_quota_areas():
    assert set(load()["quota"]) == {"finance", "science", "medical"}


def test_every_model_has_a_price():
    cfg = load()
    for model in cfg["models"].values():
        assert {"in", "out"} <= set(cfg["prices"][model])


def test_journals_well_formed():
    for j in load()["journal"]:
        assert j["area"] in {"finance", "science"} and len(j["issn"]) == 9
