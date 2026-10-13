import json

import pytest

from analyst import deep_read, parse_json
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
