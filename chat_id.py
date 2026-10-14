"""Print the Telegram chat id(s) that have messaged your bot. Run once after writing the bot token to .env:
    python3 chat_id.py
Prints ids only; the token is never printed."""
import json
import urllib.error
import urllib.request
from pathlib import Path


def read_env(path):
    env = {}
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip("'\"")
    return env


def chat_ids(data):
    if not data.get("ok"):
        raise SystemExit(f"Telegram refused the request: {data.get('error_code')} {data.get('description')}")
    ids = []
    for u in data.get("result", []):
        for key in ("message", "edited_message", "channel_post"):
            if key in u and u[key]["chat"]["id"] not in ids:
                ids.append(u[key]["chat"]["id"])
    if not ids:
        raise SystemExit("No messages found. Send any message to your bot in Telegram, then run this again.")
    return ids


if __name__ == "__main__":
    token = read_env(Path(__file__).parent / ".env").get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit("TELEGRAM_BOT_TOKEN is empty in .env: save the token there first.")
    try:
        raw = urllib.request.urlopen(f"https://api.telegram.org/bot{token}/getUpdates", timeout=30).read()
    except urllib.error.HTTPError as e:  # e.g. 401 for a bad token; the error text never includes the token
        raw = e.read()
    print("chat id(s):", chat_ids(json.loads(raw)))
