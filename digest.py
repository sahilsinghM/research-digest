"""Format the digest as Telegram-HTML messages. Sending lives elsewhere."""
from collections import Counter
from html import escape


def esc(s):
    return escape(s, quote=False)


LIMIT = 4096


def clip(s, n):
    s, n = str(s or ""), int(n)
    return s if len(s) <= n else (s[:n - 1] + "…" if n > 0 else "")


def _fit(build):
    """Escaping can expand text up to 5x, so clip raw text by shrinking budgets until the escaped message fits.
    Clipping happens before escaping and tags are ours, so a message is never cut inside a tag or entity."""
    for scale in (1.0, 0.5, 0.25, 0.1):
        m = build(scale)
        if len(m) <= LIMIT:
            return m
    return build(0.0)


def _badge(p):
    kind = "Preprint" if p.kind == "preprint" else "Peer-reviewed"
    return f"{kind} · abstract only"  # full-text reading is out of scope for now


def paper_msg(p, a):
    return _fit(lambda k: (
        f"<b>{esc(clip(p.title, 250 * k))}</b>\n"
        f"{esc(clip(p.journal, 100 * k))} · {_badge(p)}\n"
        f'<a href="{escape(p.url)}">Open paper</a>\n\n'
        f"{esc(clip(a.get('found'), 500 * k))}\n\n"
        f"<b>For you:</b> {esc(clip(a.get('for_you'), 500 * k))}\n"
        f"<b>Do:</b> {esc(clip(a.get('action'), 300 * k))}\n"
        f"<b>World:</b> {esc(clip(a.get('for_world'), 300 * k))}\n"
        f"<i>Evidence: {esc(clip(a.get('evidence'), 400 * k))}</i>"))


def header_msg(done, n_scanned, day, notes=()):
    counts = ", ".join(f"{n} {area}" for area, n in Counter(p.area for p, _ in done).items())
    top = max(done, key=lambda d: d[0].score)[0]

    def build(k):
        lines = [f"<b>Research digest {esc(day)}</b>", f"{len(done)} papers ({counts}) from {n_scanned} new",
                 f"Most important: {esc(clip(top.title, 200 * k))}"]
        return "\n".join(lines + [f"<i>{esc(clip(n, 300 * k))}</i>" for n in notes])

    return _fit(build)


def teach_msg(t):
    return _fit(lambda k: (
        f"<b>Today's concept: {esc(clip(t.get('name'), 100 * k))}</b>\n\n"
        f"{esc(clip(t.get('explain'), 1500 * k))}\n\n"
        f"<i>Example:</i> {esc(clip(t.get('example'), 1000 * k))}"))
