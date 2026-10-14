"""Format the digest as Telegram-HTML messages. Sending lives elsewhere."""
from html import escape

LIMIT = 4096
AREA_EMOJI = {"finance": "📈", "science": "🔬", "medical": "🩺"}
TRUST_LIGHT = {"strong": ("🟢", "strong evidence"), "moderate": ("🟡", "moderate evidence"),
               "weak": ("🔴", "weak or early evidence")}
NUMBERS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣"]


def esc(s):
    return escape(s, quote=False)


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


def _kind(p):
    return "Preprint" if p.kind == "preprint" else "Peer-reviewed"


def paper_msg(p, a):
    """One card: where it is from and how far to trust it, the headline, a pre-read of the ideas needed first,
    the takeaway and what it means for the reader, with the heavy detail folded away."""
    light, label = TRUST_LIGHT.get(str(a.get("trust") or "").lower(), TRUST_LIGHT["moderate"])
    pre = [x for x in (a.get("prereads") or []) if isinstance(x, dict) and x.get("term")][:3]

    def build(k):
        lines = [f"{AREA_EMOJI.get(p.area, '📄')} <b>{esc(p.area.upper())}</b> · {esc(clip(p.journal, 60 * k))}"
                 f" · {_kind(p)} · {light} {label}",
                 f"<b>{esc(clip(a.get('headline') or p.title, 160 * k))}</b>", ""]
        if pre:
            lines.append("🧠 <b>Pre-read</b>")
            for i, x in enumerate(pre, 1):
                line = f"{i}. <b>{esc(clip(x['term'], 60 * k))}</b>: {esc(clip(x.get('plain'), 160 * k))}"
                if x.get("example"):
                    line += f" <i>{esc(clip(x['example'], 140 * k))}</i>"
                lines.append(line)
            lines.append("")
        lines += [esc(clip(a.get("takeaway"), 240 * k)), "",
                  f"👉 <b>For you:</b> {esc(clip(a.get('for_you'), 200 * k))}",
                  f"✅ <b>Do:</b> {esc(clip(a.get('action'), 120 * k))}", "",
                  "<blockquote expandable>"
                  f"📄 {esc(clip(p.title, 250 * k))}\n"
                  f"Source: {_kind(p)} · abstract only\n"
                  f"Trust: {esc(clip(a.get('trust_why'), 120 * k))}\n"
                  f"What they did: {esc(clip(a.get('did'), 240 * k))}\n"
                  f"Evidence: {esc(clip(a.get('evidence'), 320 * k))}\n"
                  f"Why it matters: {esc(clip(a.get('for_world'), 200 * k))}\n"
                  f'<a href="{escape(p.url)}">Open paper</a></blockquote>']
        return "\n".join(lines)

    return _fit(build)


def header_msg(done, n_scanned, day, notes=()):
    def build(k):
        lines = [f"📚 <b>Digest · {esc(day)}</b>",
                 f"{len(done)} paper{'s' if len(done) != 1 else ''} worth a look (from {n_scanned} new):"]
        for i, (p, a) in enumerate(done):
            num = NUMBERS[i] if i < len(NUMBERS) else f"{i + 1}."
            lines.append(f"{num} {AREA_EMOJI.get(p.area, '📄')} {esc(clip(a.get('headline') or p.title, 90 * k))}")
        return "\n".join(lines + [f"<i>{esc(clip(n, 300 * k))}</i>" for n in notes])

    return _fit(build)


def teach_msg(t):
    return _fit(lambda k: (
        f"🎓 <b>Idea of the day: {esc(clip(t.get('name'), 100 * k))}</b>\n"
        f"{esc(clip(t.get('explain'), 700 * k))}\n"
        f"<blockquote expandable>Example: {esc(clip(t.get('example'), 700 * k))}</blockquote>"))
