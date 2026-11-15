"""Unit tests for the mapper tiers on hand-built pages (CI only)."""
from calcgraph.matcher import run_mapping
from calcgraph.segment import segment


def page(n, text):
    words, pos = [], 0
    for line in text.split("\n"):
        for w in line.split(" "):
            words.append([0, 0, 1, 1, pos, pos + len(w)])
            pos += len(w) + 1
    return {"n": n, "text": text, "words": words, "width": 612.0, "height": 792.0}  # segment.title_box reads the page size


def el(gid, cat, mark, profile="", storey="Level 2"):
    return {"global_id": gid, "cat": cat, "mark": mark, "profile": profile, "storey": storey}


def head(n, title, group="calcs:B1-1", software="", toc=False):
    """A calcpkg_ingest page head (the fields segment reads)."""
    return {"page": n, "title": title, "group": group, "software": software, "toc": toc, "tables": [],
            "sheet_rect": [500, 20, 540, 30], "title_rect": [72, 40, 300, 52]}


def test_tiers():
    pages = [page(1, "HEADER LINE\nBEAM DESIGN - RAM STEEL\nbeams 2B1 - 2B3 and SL2\n2B9 W18X35\nCB1 see hand calc")]
    calcs = segment(pages, [head(1, "BEAM DESIGN - RAM STEEL")])
    els = [el("a", "Beam", "2B1"), el("b", "Beam", "2B2"), el("c", "Beam", "2B9"), el("s", "Slab", "SL-2"),
           el("k", "Beam", "2CB1"), el("u", "Beam", "", "W18X35")]
    got = {(l["global_id"], l["tier"]) for l in run_mapping(els, calcs, pages)}
    assert ("a", "exact") in got and ("b", "range") in got  # 2B1 is also written out: the stronger tier wins
    assert ("c", "exact") in got
    assert ("s", "xref") in got  # slab mark ignoring punctuation, but in a beam calc
    assert ("k", "partial") in got
    # the calc names its beams by mark, so "2B9 W18X35" describes 2B9 - not every W18X35 beam in the model
    assert not any(g == "u" for g, _ in got)


def test_size_tier_only_where_the_calc_names_no_mark_of_that_type():
    pages = [page(1, "HEADER LINE\nBEAM DESIGN - TYPICAL INFILL\nTypical infill beams W18X35 at 10 ft\n"
                     "Columns W14X90 carry the girders"),
             page(2, "HEADER LINE\nCOLUMN DESIGN\nC1 W14X90 column\nBeams W18X35 frame in")]
    calcs = segment(pages, [head(1, "BEAM DESIGN - TYPICAL INFILL"), head(2, "COLUMN DESIGN", group="calcs:C1")])
    els = [el("u", "Beam", "", "W18X35"), el("c1", "Column", "C1", "W14X90"), el("c2", "Column", "C2", "W14X90")]
    got = {(l["global_id"], l["calc_key"], l["tier"]) for l in run_mapping(els, calcs, pages)}
    beam_calc, col_calc = calcs[0]["key"], calcs[1]["key"]
    assert ("u", beam_calc, "size") in got  # beam calc naming no beam mark: the size is the evidence
    assert ("c2", beam_calc, "xref") in got  # a column size in a beam calc is a mention, not a design link
    assert ("c1", col_calc, "exact") in got
    assert not any(g == "c2" and k == col_calc for g, k, _ in got)  # C1 named: W14X90 there is C1
    assert ("u", col_calc, "xref") in got  # beam size named in a column calc


def test_scanned_and_front_never_mapped():
    pages = [page(1, "Design criteria .... 2\nBeams .... 3\nColumns .... 4"), page(2, "")]
    # the contents flag comes from calcpkg_ingest's page head (the profile's dot-leader rule), not from segment
    calcs = segment(pages, [head(1, "Contents", toc=True), head(2, "")])
    assert calcs[0]["front"] and calcs[1]["scanned"]
    assert run_mapping([el("a", "Beam", "B1")], calcs, pages) == []
