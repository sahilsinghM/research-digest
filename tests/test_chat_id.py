import pytest

from chat_id import chat_ids, read_env


def test_collects_distinct_chat_ids_from_messages_and_channel_posts():
    data = {"ok": True, "result": [
        {"update_id": 1, "message": {"chat": {"id": 111, "type": "private"}}},
        {"update_id": 2, "message": {"chat": {"id": 111, "type": "private"}}},
        {"update_id": 3, "channel_post": {"chat": {"id": -100222, "type": "channel"}}},
        {"update_id": 4, "edited_message": {"chat": {"id": 333}}},
        {"update_id": 5},
    ]}
    assert chat_ids(data) == [111, -100222, 333]


def test_no_updates_asks_the_user_to_message_the_bot_first():
    with pytest.raises(SystemExit, match="Send any message to your bot"):
        chat_ids({"ok": True, "result": []})


def test_a_rejected_token_is_reported_without_echoing_anything_secret():
    with pytest.raises(SystemExit) as e:
        chat_ids({"ok": False, "error_code": 401, "description": "Unauthorized"})
    assert "401" in str(e.value) and "Unauthorized" in str(e.value)


def test_read_env_parses_plain_quoted_and_commented_lines(tmp_path):
    f = tmp_path / ".env"
    f.write_text('# comment\nA=1\nB="two"\nC=\'three\'\n\nD=\nBAD LINE\n')
    assert read_env(f) == {"A": "1", "B": "two", "C": "three", "D": ""}
