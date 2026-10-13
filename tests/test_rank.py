from rank import pick, prefilter
from sources import Paper


def P(id, area="finance", score=0.0, title="t", abstract=""):
    return Paper(id=id, title=title, abstract=abstract, source="s", area=area, journal="j",
                 url="u", published="2026-10-12", kind="peer", score=score)


def test_prefilter_only_filters_medical():
    ps = [P("a", "finance", title="Rates"), P("b", "medical", title="Sleep apnoea trial"),
          P("c", "medical", title="Unrelated surgery study")]
    assert [p.id for p in prefilter(ps, ["sleep"])] == ["a", "b"]


def test_prefilter_matches_abstract_case_insensitively():
    assert prefilter([P("b", "medical", abstract="Effects on SLEEP")], ["sleep"])


def test_pick_respects_quota_min_score_and_order():
    ps = [P("f1", "finance", 9), P("f2", "finance", 8), P("f3", "finance", 7),
          P("s1", "science", 4), P("m1", "medical", 6)]
    got = pick(ps, {"finance": 2, "science": 2, "medical": 3}, max_papers=8, min_score=5)
    assert [p.id for p in got] == ["f1", "f2", "m1"]


def test_pick_caps_total():
    ps = [P(f"f{i}", "finance", 9 - i * 0.1) for i in range(5)] + [P("m", "medical", 7)]
    got = pick(ps, {"finance": 5, "medical": 3}, max_papers=3, min_score=5)
    assert [p.id for p in got] == ["f0", "f1", "f2"]


def test_pick_nothing_when_all_below_min():
    assert pick([P("a", score=2)], {"finance": 2}, 8, 5) == []



def test_pick_respects_quota_min_score_and_order():
    ps = [P("f1", "finance", 9), P("f2", "finance", 8), P("f3", "finance", 7),
          P("s1", "science", 4), P("m1", "medical", 6)]
    got = pick(ps, {"finance": 2, "science": 2, "medical": 3}, max_papers=8, min_score=5)
    assert [p.id for p in got] == ["f1", "f2", "m1"]


def test_pick_caps_total():
    ps = [P(f"f{i}", "finance", 9 - i * 0.1) for i in range(5)] + [P("m", "medical", 7)]
    got = pick(ps, {"finance": 5, "medical": 3}, max_papers=3, min_score=5)
    assert [p.id for p in got] == ["f0", "f1", "f2"]


def test_pick_nothing_when_all_below_min():
    assert pick([P("a", score=2)], {"finance": 2}, 8, 5) == []
