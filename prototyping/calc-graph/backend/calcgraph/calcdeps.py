"""Calc dependency graph: output of one calc feeds the input of another.

Two deterministic rules, each edge keeps its evidence:

1. page reference - "page 7", "pages 5-8", "p. 12" inside a calc points at the calc
   that holds that page. Direction from the nearest cue word earlier on the same
   line: "to" means this calc's output goes TO that page's calc (this -> that);
   "from" / "per" / "see" / "using" or no cue means it is an input (that -> this).
2. cross-reference - a calc that mentions (xref tier) an element designed by another
   calc takes that calc's output as input (designer -> this), unless the same line
   has a "to" cue before the mention ("carried to ST-1 design"), then this -> designer.
"""
from __future__ import annotations

import re

from .pdf_ingest import rects_for_span

_PAGE = re.compile(r"\b(?:PAGES?|PP?\.)\s*(\d{1,4})(?:\s*(?:-|–|TO)\s*(\d{1,4}))?")
_CUE = re.compile(r"\b(FROM|PER|SEE|USING|TO)\b")


def infer(calcs: list[dict], pages: list[dict], links: list[dict]) -> list[dict]:
    page_owner = {n: c for c in calcs for n in c["pages"]}
    page_by_n = {p["n"]: p for p in pages}
    edges: dict[tuple[str, str], dict] = {}

    def add(src, dst, rule, ev):
        if src == dst:
            return
        e = edges.setdefault((src, dst), {"src": src, "dst": dst, "rules": [], "evidence": []})
        if rule not in e["rules"]:
            e["rules"].append(rule)
        if len(e["evidence"]) < 6:
            e["evidence"].append(ev)

    for c in calcs:
        if c["front"] or c["scanned"]:
            continue
        for pn in c["pages"]:
            pg = page_by_n[pn]
            U = pg["text"].upper()
            for m in _PAGE.finditer(U):
                a = int(m.group(1))
                b = int(m.group(2) or a)
                ls = U.rfind("\n", 0, m.start()) + 1
                cues = _CUE.findall(U[ls:m.start()])
                out = bool(cues) and cues[-1] == "TO"
                targets = []
                for n in range(a, min(b, a + 50) + 1):
                    o = page_owner.get(n)
                    if o and not o["front"] and o["key"] != c["key"] and o not in targets:
                        targets.append(o)
                for o in targets:
                    ev = {"calc": c["key"], "page": pn, "text": pg["text"][m.start():m.end()],
                          "line": pg["text"][ls:(U.find("\n", m.end()) if U.find("\n", m.end()) >= 0 else None)],
                          "rects": rects_for_span(pg, m.start(), m.end())}
                    if out:
                        add(c["key"], o["key"], "page reference (output to)", ev)
                    else:
                        add(o["key"], c["key"], "page reference (input from)", ev)

    designer: dict[str, dict] = {}
    for l in links:
        if l["tier"] != "xref" and l.get("status") != "rejected":
            cur = designer.get(l["global_id"])
            if cur is None or l["conf"] > cur["conf"]:
                designer[l["global_id"]] = l
    for l in links:
        if l["tier"] == "xref" and l.get("status") != "rejected" and l["global_id"] in designer:
            d = designer[l["global_id"]]
            U = page_by_n[l["page"]]["text"].upper()
            ls = U.rfind("\n", 0, l["span"][0]) + 1
            cues = _CUE.findall(U[ls:l["span"][0]])
            src, dst = (l["calc_key"], d["calc_key"]) if cues and cues[-1] == "TO" else (d["calc_key"], l["calc_key"])
            add(src, dst, "cross-reference (mentions an element the other calc designs)",
                {"calc": l["calc_key"], "page": l["page"], "text": l["token"], "global_id": l["global_id"], "rects": l["rects"]})
    return sorted(edges.values(), key=lambda e: (e["src"], e["dst"]))
