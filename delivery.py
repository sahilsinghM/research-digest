"""Send messages to the owner's Telegram chat. The bot token never appears in errors or logs."""
import json
import re
import time
import urllib.error
import urllib.request

LIMIT = 4096


class TelegramError(Exception):
    pass


def split(text, limit=LIMIT):
    """Chunks of at most `limit` chars, cutting at a line break when one is reasonably close."""
    parts = []
    while len(text) > limit:
        cut = text.rfind("\n", 0, limit)
        if cut < limit // 2:
            cut = limit
        parts.append(text[:cut])
        text = text[cut:].lstrip("\n")
    return parts + [text]


def _post(token, chat_id, text, mode):
    body = {"chat_id": chat_id, "text": text, "disable_web_page_preview": True}
    if mode:
        body["parse_mode"] = mode
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage",
                                 json.dumps(body).encode(), {"Content-Type": "application/json"})
    for _ in range(3):
        try:
            urllib.request.urlopen(req, timeout=30).read()
            return
        except urllib.error.HTTPError as e:
            data = json.loads(e.read() or b"{}")
            if e.code == 429:
                time.sleep(data.get("parameters", {}).get("retry_after", 5))
                continue
            # `from None`: the original exception carries the request URL, which contains the token.
            raise TelegramError(f"{e.code}: {data.get('description')}") from None
        except urllib.error.URLError:
            raise TelegramError("network error reaching Telegram") from None
    raise TelegramError("rate limited by Telegram")


def send(token, chat_id, text, post=_post):
    for chunk in split(text):
        try:
            post(token, chat_id, chunk, "HTML")
        except TelegramError:  # bad markup somewhere: deliver as plain text rather than lose it
            post(token, chat_id, re.sub(r"<[^>]+>", "", chunk), None)
