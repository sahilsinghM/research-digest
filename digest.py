"""Format the digest as Telegram-HTML messages. Sending lives elsewhere."""
from collections import Counter
from html import escape


def esc(s):
    return escape(s, quote=False)


def clip(s, n):
    s = str(s or "")
    return s if len(s) <= n else s[:n - 1] + "…"


def _badge(p):
    kind = "Preprint" if p.kind == "preprint" else "Peer-reviewed"
    return f"{kind} · abstract only"  # full-text reading is out of scope for now


def paper_msg(p, a):
    # Field clips keep one paper under 4096 characters even if the model rambles.
    return (f"<b>{esc(clip(p.title, 250))}</b>\n"
            f"{esc(clip(p.journal, 100))} · {_badge(p)}\n"
            f'<a href="{escape(p.url)}">Open paper</a>\n\n'
            f"{esc(clip(a.get('found'), 500))}\n\n"
            f"<b>For you:</b> {esc(clip(a.get('for_you'), 500))}\n"
            f"<b>Do:</b> {esc(clip(a.get('action'), 300))}\n"
            f"<b>World:</b> {esc(clip(a.get('for_world'), 300))}\n"
            f"<i>Evidence: {esc(clip(a.get('evidence'), 400))}</i>")


def header_msg(done, n_scanned, day, notes=()):
    counts = ", ".join(f"{n} {area}" for area, n in Counter(p.area for p, _ in done).items())
    top = max(done, key=lambda d: d[0].score)[0]
    lines = [f"<b>Research digest {esc(day)}</b>", f"{len(done)} papers ({counts}) from {n_scanned} new",
             f"Most important: {esc(clip(top.title, 200))}"]
    lines += [f"<i>{esc(n)}</i>" for n in notes]
    return "\n".join(lines)


def teach_msg(t):
    return (f"<b>Today's concept: {esc(clip(t.get('name'), 100))}</b>\n\n"
            f"{esc(clip(t.get('explain'), 1500))}\n\n"
            f"<i>Example:</i> {esc(clip(t.get('example'), 1000))}")
