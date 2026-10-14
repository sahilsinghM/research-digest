import re

from digest import clip, header_msg, paper_msg, teach_msg
from sources import Paper


def P(title="T", kind="preprint", area="finance", journal="J", url="https://e.com/p", score=0.0):
    return Paper(id="x", title=title, abstract="", source="s", area=area, journal=journal,
                 url=url, published="2026-10-12", kind=kind, score=score)


A = {"headline": "Plain headline", "takeaway": "They found a thing.", "for_you": "mine", "action": "act",
     "trust": "weak", "trust_why": "simulation only",
     "prereads": [{"term": "Market making", "plain": "quoting buy and sell prices together", "example": "like a currency booth"},
                  {"term": "Spread", "plain": "the gap between buy and sell", "example": ""}],
     "did": "built a model", "evidence": "simulated data", "for_world": "could matter"}


def _blockquote(m):
    return m[m.index("<blockquote expandable>"):m.index("</blockquote>")]


def test_card_reads_in_learning_order_headline_then_preread_then_takeaway_then_you_then_details():
    m = paper_msg(P(), A)
    order = [m.index(s) for s in ("Plain headline", "Pre-read", "They found a thing.", "For you", "Do:",
                                  "<blockquote expandable>")]
    assert order == sorted(order)


def test_preread_shows_each_term_with_plain_meaning_and_optional_example():
    m = paper_msg(P(), A)
    assert "<b>Market making</b>" in m and "quoting buy and sell prices together" in m and "like a currency booth" in m
    assert "<b>Spread</b>" in m and "the gap between buy and sell" in m


def test_card_without_prereads_has_no_preread_heading():
    assert "Pre-read" not in paper_msg(P(), dict(A, prereads=[]))


def test_heavy_details_are_folded_and_the_summary_is_not():
    m = paper_msg(P(title="Original Title"), A)
    folded = _blockquote(m)
    for s in ("built a model", "simulated data", "could matter", "Original Title", "https://e.com/p", "abstract only"):
        assert s in folded
    assert "They found a thing." not in folded and "mine" not in folded


def test_trust_light_follows_the_models_rating_and_defaults_to_moderate():
    assert "🟢" in paper_msg(P(), dict(A, trust="strong"))
    assert "🟡" in paper_msg(P(), dict(A, trust="moderate"))
    assert "🔴" in paper_msg(P(), dict(A, trust="weak"))
    assert "🟡" in paper_msg(P(), dict(A, trust="banana")) and "🟡" in paper_msg(P(), {})


def test_area_emoji_and_source_kind_in_the_top_line():
    assert paper_msg(P(area="finance"), A).startswith("📈")
    assert paper_msg(P(area="science"), A).startswith("🔬")
    assert paper_msg(P(area="medical", kind="peer", journal="The Lancet"), A).startswith("🩺")
    top = paper_msg(P(area="medical", kind="peer", journal="The Lancet"), A).split("\n")[0]
    assert "The Lancet" in top and "Peer-reviewed" in top
    assert "Preprint" in paper_msg(P(kind="preprint"), A).split("\n")[0]


def test_headline_falls_back_to_the_title_and_missing_fields_are_tolerated():
    m = paper_msg(P(title="Real Title"), {})
    assert "Real Title" in m.split("\n")[1]


def test_everything_dynamic_is_escaped():
    a = dict(A, headline="A < B & C", prereads=[{"term": "P&L", "plain": "x<y", "example": "it's"}])
    m = paper_msg(P(title="T & <i>", url="https://e.com/?a=1&b=2"), a)
    assert "A &lt; B &amp; C" in m and "P&amp;L" in m and "x&lt;y" in m and "it's" in m
    assert 'href="https://e.com/?a=1&amp;b=2"' in m and "<i>T" not in m


def _well_formed(m):
    assert len(m) <= 4096
    for tag in ("b", "i"):
        assert m.count(f"<{tag}>") == m.count(f"</{tag}>")
    assert m.count("<blockquote expandable>") == m.count("</blockquote>")
    assert not re.search(r"&(?!amp;|lt;|gt;|quot;|#)", m)  # no dangling or cut-off entity


def test_cards_stay_whole_and_under_the_limit_even_with_huge_hostile_fields():
    huge = {k: "&<" * 3000 for k in ("headline", "takeaway", "for_you", "action", "trust_why", "did", "evidence", "for_world")}
    huge["trust"] = "weak"
    huge["prereads"] = [{"term": "&" * 900, "plain": "<" * 900, "example": "&<" * 900}] * 3
    _well_formed(paper_msg(P(title="<" * 3000, journal="&" * 3000), huge))


def test_normal_cards_are_not_shortened_by_the_safety_net():
    assert "f" * 200 in paper_msg(P(), dict(A, takeaway="f" * 200))


def test_header_lists_one_numbered_headline_per_paper_with_area_emoji():
    done = [(P(area="medical"), dict(A, headline="First one")), (P(area="finance"), dict(A, headline="Second one")),
            (P(area="science"), dict(A, headline="Third one"))]
    h = header_msg(done, 120, "2026-10-13", ["sources failed: nber"])
    assert "1️⃣ 🩺 First one" in h and "2️⃣ 📈 Second one" in h and "3️⃣ 🔬 Third one" in h
    assert "3 papers" in h and "120" in h and "2026-10-13" in h and "sources failed: nber" in h


def test_header_stays_whole_with_hostile_headlines_and_notes():
    done = [(P(), dict(A, headline="&<" * 3000))] * 8
    _well_formed(header_msg(done, 10, "2026-10-13", ["&<" * 3000] * 5))


def test_teach_msg_is_short_with_the_example_folded_and_escaped():
    m = teach_msg({"name": "P&L", "explain": "a<b", "example": "it's c"})
    assert "P&amp;L" in m and "a&lt;b" in m and "it's c" in _blockquote(m)
    assert "a&lt;b" not in _blockquote(m)


def test_teach_msg_stays_under_limit_and_tolerates_missing_fields():
    _well_formed(teach_msg({"name": "n" * 9000, "explain": "e" * 9000, "example": "x" * 9000}))
    assert teach_msg({})


def test_clip():
    assert clip("abc", 5) == "abc" and clip("abcdef", 4) == "abc…" and clip(None, 3) == "" and clip("abc", 0) == ""
