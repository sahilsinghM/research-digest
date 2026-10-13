from digest import clip, header_msg, paper_msg
from sources import Paper


def P(title="T", kind="preprint", area="finance", journal="J", url="https://e.com/p"):
    return Paper(id="x", title=title, abstract="", source="s", area=area, journal=journal,
                 url=url, published="2026-10-12", kind=kind)


A = {"did": "d", "found": "found it", "evidence": "n=10", "for_you": "mine", "action": "act", "for_world": "all"}


def test_paper_msg_has_all_sections():
    m = paper_msg(P(title="Rough Vol"), A)
    for s in ("Rough Vol", "found it", "mine", "act", "all", "n=10", "https://e.com/p"):
        assert s in m


def test_paper_msg_stays_under_limit_with_huge_fields():
    huge = {k: "x" * 5000 for k in A}
    assert len(paper_msg(P(title="t" * 5000, journal="j" * 5000), huge)) <= 4096


def test_badges():
    assert "Preprint · abstract only" in paper_msg(P(kind="preprint"), A)
    assert "Peer-reviewed · abstract only" in paper_msg(P(kind="peer"), A)


def test_paper_msg_tolerates_missing_fields():
    assert "T" in paper_msg(P(), {})


def test_header_counts_areas_and_notes():
    done = [(P(area="medical"), A), (P(area="finance"), A), (P(area="finance"), A)]
    h = header_msg(done, 120, "2026-10-13", ["sources failed: nber"])
    assert "3 papers" in h and "2 finance" in h and "1 medical" in h
    assert "120" in h and "2026-10-13" in h and "sources failed: nber" in h


def test_clip():
    assert clip("abc", 5) == "abc" and clip("abcdef", 4) == "abc…" and clip(None, 3) == ""


def test_paper_msg_escapes_html_in_every_dynamic_field():
    m = paper_msg(P(title="A < B & C", url="https://e.com/?a=1&b=2"), dict(A, found="x < y"))
    assert "A &lt; B &amp; C" in m and "x &lt; y" in m and "A < B" not in m
    assert 'href="https://e.com/?a=1&amp;b=2"' in m


def test_apostrophes_are_not_turned_into_entities_in_body_text():
    assert "don't" in paper_msg(P(), dict(A, found="don't"))
