import io
import json
import urllib.error

import pytest

import delivery
from delivery import TelegramError, send, split

TOKEN = "123456:SECRET-TOKEN"


def test_split_short_text_unchanged():
    assert split("hello") == ["hello"]


def test_split_long_text_prefers_line_breaks_and_respects_limit():
    text = "\n".join("line %d" % i * 3 for i in range(2000))
    parts = split(text)
    assert len(parts) > 1 and all(len(p) <= 4096 for p in parts)
    assert "".join(parts).replace("\n", "") == text.replace("\n", "")


def test_split_text_without_line_breaks_hard_splits():
    assert [len(p) for p in split("y" * 10000)] == [4096, 4096, 1808]


def test_send_goes_through_each_chunk_to_the_given_chat_as_html():
    calls = []
    send(TOKEN, "chat-1", "z" * 9000, post=lambda t, c, text, mode: calls.append((t, c, len(text), mode)))
    assert [(c, n, m) for _, c, n, m in calls] == [("chat-1", 4096, "HTML"), ("chat-1", 4096, "HTML"),
                                                    ("chat-1", 808, "HTML")]


def test_send_falls_back_to_plain_text_when_html_is_rejected():
    calls = []

    def post(token, chat, text, mode):
        calls.append((text, mode))
        if mode == "HTML":
            raise TelegramError("400: can't parse entities")

    send(TOKEN, "chat", "<b>Hi</b> <a href=\"x\">there</a>", post=post)
    assert calls == [('<b>Hi</b> <a href="x">there</a>', "HTML"), ("Hi there", None)]


# ---- the real transport, with urlopen faked ----

class Resp:
    def read(self):
        return b"{}"


def http_error(code, body):
    return urllib.error.HTTPError(f"https://api.telegram.org/bot{TOKEN}/sendMessage", code, "x", {},
                                  io.BytesIO(json.dumps(body).encode()))


@pytest.fixture
def net(monkeypatch):
    class Net:
        outcomes, requests, sleeps = [], [], []
    n = Net()

    def urlopen(req, timeout):
        n.requests.append(req)
        out = n.outcomes.pop(0)
        if isinstance(out, Exception):
            raise out
        return Resp()

    monkeypatch.setattr(delivery.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(delivery.time, "sleep", n.sleeps.append)
    return n


def test_post_sends_chat_id_html_mode_and_no_link_preview(net):
    net.outcomes[:] = [None]
    delivery._post(TOKEN, "chat-9", "hello", "HTML")
    body = json.loads(net.requests[0].data)
    assert body == {"chat_id": "chat-9", "text": "hello", "disable_web_page_preview": True, "parse_mode": "HTML"}
    assert net.requests[0].full_url.endswith("/sendMessage")


def test_post_without_mode_omits_parse_mode(net):
    net.outcomes[:] = [None]
    delivery._post(TOKEN, "c", "hello", None)
    assert "parse_mode" not in json.loads(net.requests[0].data)


def test_rate_limit_waits_the_advised_time_then_retries(net):
    net.outcomes[:] = [http_error(429, {"parameters": {"retry_after": 7}}), None]
    delivery._post(TOKEN, "c", "t", "HTML")
    assert net.sleeps == [7] and len(net.requests) == 2


def test_rate_limit_gives_up_after_three_attempts(net):
    net.outcomes[:] = [http_error(429, {"parameters": {"retry_after": 1}})] * 3
    with pytest.raises(TelegramError, match="rate limited"):
        delivery._post(TOKEN, "c", "t", "HTML")
    assert len(net.requests) == 3


def test_other_http_errors_become_telegram_errors_with_the_description_but_never_the_token(net):
    net.outcomes[:] = [http_error(400, {"description": "Bad Request: can't parse entities"})]
    with pytest.raises(TelegramError) as e:
        delivery._post(TOKEN, "c", "t", "HTML")
    assert "can't parse entities" in str(e.value) and "SECRET-TOKEN" not in str(e.value)
    assert e.value.__cause__ is None and e.value.__suppress_context__


def test_network_failures_become_telegram_errors_without_the_token(net):
    net.outcomes[:] = [urllib.error.URLError(f"cannot reach https://api.telegram.org/bot{TOKEN}/sendMessage")]
    with pytest.raises(TelegramError) as e:
        delivery._post(TOKEN, "c", "t", "HTML")
    assert "SECRET-TOKEN" not in str(e.value)
