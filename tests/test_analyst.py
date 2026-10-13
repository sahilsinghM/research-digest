import json

import pytest

from analyst import CallCap, CallCapExceeded, deep_read, parse_json, triage
from sources import Paper


class FakeRun:
    """Stands in for runner.claude: replays canned replies, records (model, system, user)."""

    def __init__(self, *replies):
        self.replies, self.calls = list(replies), []

    def __call__(self, model, system, user):
        self.calls.append((model, system, user))
        return self.replies.pop(0)


def P(abstract="An abstract."):
    return Paper(id="a", title="A title", abstract=abstract, source="s", area="medical", journal="The J",
                 url="u", published="2026-10-12", kind="preprint")


ANALYSIS = {"did": "d", "found": "f", "evidence": "e", "for_you": "y", "action": "a", "for_world": "w"}


def test_parse_json_plain_fenced_and_prose():
    assert parse_json('{"a": 1}') == {"a": 1}
    assert parse_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json('Here you go:\n{"a": 1}\nHope that helps') == {"a": 1}
    with pytest.raises(ValueError):
        parse_json("no json at all")


def test_deep_read_returns_analysis_and_sends_paper_and_profile():
    run = FakeRun(json.dumps(ANALYSIS))
    assert deep_read(run, "sonnet", P(), "I AM THE PROFILE") == ANALYSIS
    model, system, user = run.calls[0]
    assert model == "sonnet" and "I AM THE PROFILE" in system
    assert "A title" in user and "An abstract." in user and "The J" in user and "preprint" in user.lower()


def test_deep_read_handles_fenced_reply():
    assert deep_read(FakeRun("```json\n" + json.dumps(ANALYSIS) + "\n```"), "m", P(), "p") == ANALYSIS


def test_deep_read_retries_once_then_succeeds():
    run = FakeRun("sorry, no json", json.dumps(ANALYSIS))
    assert deep_read(run, "m", P(), "p") == ANALYSIS and len(run.calls) == 2


def test_deep_read_gives_up_after_two_unparseable_replies():
    run = FakeRun("junk", "more junk")
    assert deep_read(run, "m", P(), "p") is None and len(run.calls) == 2


def test_deep_read_handles_empty_abstract():
    run = FakeRun(json.dumps(ANALYSIS))
    assert deep_read(run, "m", P(abstract=""), "p") == ANALYSIS
    assert "none available" in run.calls[0][2].lower()


def test_prompt_tells_model_paper_text_is_data_and_not_to_invent_numbers():
    run = FakeRun(json.dumps(ANALYSIS))
    deep_read(run, "m", P(), "p")
    system = run.calls[0][1].lower()
    assert "data" in system and "do not state one" in system


def T(id, abstract=""):
    return Paper(id=id, title="T " + id, abstract=abstract, source="s", area="finance", journal="J",
                 url="u", published="2026-10-12", kind="peer")


def test_triage_scores_and_defaults_missing_to_zero_even_with_empty_abstracts():
    ps = [T("a"), T("b")]
    triage(FakeRun('```json\n[{"id": "a", "score": 8.5}]\n```'), "m", ps, "profile")
    assert (ps[0].score, ps[1].score) == (8.5, 0.0)


def test_triage_batches_by_size():
    ps = [T(str(i)) for i in range(7)]
    run = FakeRun("[]", "[]", "[]")
    triage(run, "m", ps, "profile", batch=3)
    assert len(run.calls) == 3
    assert [r["id"] for r in json.loads(run.calls[2][2])] == ["6"]


def test_triage_survives_garbage_twice_and_odd_rows():
    ps = [T("a"), T("b")]
    triage(FakeRun("nope", "still nope"), "m", ps, "profile")
    assert [p.score for p in ps] == [0.0, 0.0]
    triage(FakeRun('[{"id": "a"}, "junk", {"id": "b", "score": "x"}, {"id": "a", "score": 7}]'), "m", ps, "profile")
    assert (ps[0].score, ps[1].score) == (7.0, 0.0)


def test_triage_ignores_a_non_list_reply():
    ps = [T("a")]
    triage(FakeRun('{"id": "a", "score": 9}', '{"id": "a", "score": 9}'), "m", ps, "profile")
    assert ps[0].score == 0.0


def test_triage_puts_profile_in_system_prompt_and_makes_no_call_for_no_papers():
    run = FakeRun("[]")
    triage(run, "m", [T("a")], "I AM THE PROFILE")
    assert "I AM THE PROFILE" in run.calls[0][1]
    run2 = FakeRun()
    triage(run2, "m", [], "profile")
    assert run2.calls == []


def test_triage_truncates_very_long_abstracts():
    run = FakeRun("[]")
    triage(run, "m", [T("a", abstract="x" * 5000)], "profile")
    assert len(json.loads(run.calls[0][2])[0]["abstract"]) == 1200


def test_call_cap_allows_up_to_cap_then_raises_and_counts_retries():
    inner = FakeRun("a", "b", "c")
    capped = CallCap(inner, 2)
    assert capped("m", "s", "u") == "a" and capped("m", "s", "u") == "b"
    with pytest.raises(CallCapExceeded):
        capped("m", "s", "u")
    assert capped.calls == 2 and len(inner.calls) == 2
