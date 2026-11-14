"""Unit tests for the mapper tiers on hand-built pages (CI only)."""
from calcgraph.matcher import run_mapping
from calcgraph.segment import segment


def page(n, text):
    words, pos = [], 0
    for line in text.split("\n"):
        for w in line.split(" "):
            words.append([0, 0, 1, 1, pos, pos + len(w)])
            pos += len(w) + 1
    return {"n": n, "text": text, "words": words, "width": 612, "height": 792}


def el(gid, cat, mark, profile="", storey="Level 2"):
    return {"global_id": gid, "cat": cat, "mark": mark, "profile": profile, "storey": storey}


def test_tiers():
    pages = [page(1, "HEADER LINE\nBEAM DESIGN - RAM STEEL\nbeams 2B1 - 2B3 and SL2\n2B9 W18X35\nCB1 see hand calc")]
    calcs = segment(pages)
    els = [el("a", "Beam", "2B1"), el("b", "Beam", "2B2"), el("c", "Beam", "2B9"), el("s", "Slab", "SL-2"),
           el("k", "Beam", "2CB1"), el("u", "Beam", "", "W18X35")]
    got = {(l["global_id"], l["tier"]) for l in run_mapping(els, calcs, pages)}
    # The named endpoint receives the stronger exact match; the interior is a range match.
    assert ("a", "exact") in got and ("b", "range") in got
    assert ("c", "exact") in got
    assert ("s", "xref") in got  # slab mark ignoring punctuation, but in a beam calc
    assert ("k", "partial") in got
    assert ("u", "size") in got


def test_scanned_and_front_never_mapped():
    pages = [page(1, "Design criteria .... 2\nBeams .... 3\nColumns .... 4"), page(2, "")]
    calcs = segment(pages)
    assert calcs[0]["front"] and calcs[1]["scanned"]
    assert run_mapping([el("a", "Beam", "B1")], calcs, pages) == []
