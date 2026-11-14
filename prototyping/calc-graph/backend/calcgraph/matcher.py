"""Element <-> calc mapping. Faithful port of the mockup's runMapping().

Tiers and confidences (deterministic, in this order of strength):
  exact    0.97  the element's mark appears as a token
  range    0.90  the mark falls inside a written range ("2B1 - 2B9", "C1 thru C12")
  loose    0.88  the mark matches ignoring punctuation ("SL2" for "SL-2")
  family   0.85  token names a mark family ("BR1" covers "BR1-1".."BR1-n")
  size     0.62  section size + element type (+ storey if the line names one), no mark
  partial  0.50  token is the tail of exactly one model mark ("CB1" -> "2CB1")
  xref     <=.45 any mark tier where the element type differs from the calc's type -
                 the calc mentions the element, it probably did not design it
  type     0.30  calc names no marks or sizes: covers unclaimed elements of its type
Scanned pages and front matter are never mapped. Every link keeps page, the exact
text span it matched, a snippet, word boxes for highlighting, and the rule.
"""
from __future__ import annotations

import re

from .ifc_ingest import norm_profile, profile_from
from .pdf_ingest import rects_for_span
from .segment import CAT_WORDS

CONF = {"exact": 0.97, "range": 0.9, "loose": 0.88, "family": 0.85, "size": 0.62, "partial": 0.5, "type": 0.3}

_DASHES = re.compile("[‐-―]")
_RANGE = re.compile(r"\b([A-Z]{0,3}\d{0,2}[A-Z]{1,3})(\d{1,4})\s*(?:-|–|—|TO|THRU|THROUGH)\s*(?:\1)?(\d{1,4})\b")
_TOK = re.compile(r"[A-Z0-9]+(?:[-./][A-Z0-9]+)*")
_PROF = re.compile(r"\b(?:W|HSS|WT|MC|UB|UC|PFC|SHS|RHS|CHS|IPE|HEA|HEB)\s?\d+(?:\.\d+)?X\d+(?:\.\d+)?(?:X\d+(?:/\d+)?(?:\.\d+)?)?\b"
                   r"|\b\d{3,4}X\d{3,4}\b")


def norm_mark(s: str | None) -> str:
    return re.sub(r"\s+", "", _DASHES.sub("-", str(s or "").upper()))


def dashless(s: str | None) -> str:
    return re.sub(r"[-./]", "", norm_mark(s))


def _snippet(text: str, idx: int, n: int) -> dict:
    a, b = max(0, idx - 70), min(len(text), idx + n + 70)
    return {"before": ("…" if a > 0 else "") + text[a:idx], "match": text[idx:idx + n],
            "after": text[idx + n:b] + ("…" if b < len(text) else "")}


def run_mapping(elements: list[dict], calcs: list[dict], pages: list[dict]) -> list[dict]:
    links: dict[tuple[str, str], dict] = {}
    if not elements or not calcs:
        return []
    page_by_n = {p["n"]: p for p in pages}
    exact: dict[str, list[dict]] = {}
    loose: dict[str, list[dict]] = {}
    families: dict[str, list[dict]] = {}
    for el in elements:
        if not el.get("mark"):
            continue
        n = norm_mark(el["mark"])
        exact.setdefault(n, []).append(el)
        loose.setdefault(dashless(el["mark"]), []).append(el)
        fam = re.match(r"^(.+?)-\d{1,3}[A-Z]?$", n)
        if fam:
            families.setdefault(fam.group(1), []).append(el)
    all_marks = list(exact.keys())
    by_profile: dict[str, list[dict]] = {}
    for el in elements:
        if el.get("profile"):
            by_profile.setdefault(f"{el['profile']}|{el['cat']}", []).append(el)
    storeys = sorted({e["storey"] for e in elements if e.get("storey") and len(e["storey"]) > 2}, key=lambda s: -len(s))

    def link(el, c, conf, tier, rule, pg, idx, n):
        if c["cat"] and el["cat"] != c["cat"] and el["cat"] != "Other" and tier not in ("size", "type"):
            conf = min(conf, 0.45)
            tier = "xref"
            rule = f"{el['cat']} \"{el['mark']}\" is mentioned in a {c['cat'].lower()} calc - likely a cross-reference"
        k = (el["global_id"], c["key"])
        rec = {"global_id": el["global_id"], "calc_key": c["key"], "conf": conf, "tier": tier, "rule": rule,
               "page": pg["n"], "span": [idx, idx + n], "token": pg["text"][idx:idx + n],
               "snippet": _snippet(pg["text"], idx, n), "rects": rects_for_span(pg, idx, idx + n)}
        ex = links.get(k)
        if ex is None or conf > ex["conf"]:
            links[k] = rec

    for c in calcs:
        if c["scanned"] or c["front"]:
            continue
        c["mark_hits"] = 0
        for pn in c["pages"]:
            pg = page_by_n.get(pn)
            if not pg:
                continue
            T = pg["text"]
            U = T.upper()
            # 1. ranges
            for m in _RANGE.finditer(U):
                pre, a, b = m.group(1), int(m.group(2)), int(m.group(3))
                if not (b > a and b - a < 300):
                    continue
                if norm_mark(m.group(0)) in exact:
                    continue
                hit = False
                for i in range(a, b + 1):
                    for el in exact.get(f"{pre}{i}", []):
                        link(el, c, CONF["range"], "range", f"In range {pre}{a}–{pre}{b}", pg, m.start(), len(m.group(0)))
                        hit = True
                if hit:
                    c["mark_hits"] += 1
            # 2. tokens
            for m in _TOK.finditer(U):
                tok = m.group(0)
                if not re.search(r"[A-Z]", tok) or not re.search(r"\d", tok) or len(tok) < 2:
                    continue
                hit = exact.get(tok)
                if hit:
                    for el in hit:
                        link(el, c, CONF["exact"], "exact", f"Mark \"{el['mark']}\" named in calc", pg, m.start(), len(tok))
                    c["mark_hits"] += 1
                    continue
                hit = loose.get(dashless(tok))
                if hit:
                    for el in hit:
                        link(el, c, CONF["loose"], "loose", f"\"{tok}\" matches mark \"{el['mark']}\" ignoring punctuation",
                             pg, m.start(), len(tok))
                    c["mark_hits"] += 1
                    continue
                hit = families.get(tok)
                if hit:
                    for el in hit:
                        link(el, c, CONF["family"], "family", f"\"{tok}\" covers mark family {tok}-n", pg, m.start(), len(tok))
                    c["mark_hits"] += 1
                    continue
                if re.fullmatch(r"[A-Z]+\d+", tok) and not profile_from(tok):
                    cands = [mk for mk in all_marks if len(mk) > len(tok) and mk.endswith(tok)
                             and re.match(r"[0-9A-Z]", mk[len(mk) - len(tok) - 1])]
                    if len(cands) == 1:
                        for el in exact[cands[0]]:
                            link(el, c, CONF["partial"], "partial",
                                 f"\"{tok}\" is a partial mark - only \"{el['mark']}\" ends with it", pg, m.start(), len(tok))
                        c["mark_hits"] += 1
            # 3. section size + element type (+ storey named on the line)
            if c["cat"]:
                for m in _PROF.finditer(U):
                    p = norm_profile(m.group(0))
                    ls = U.rfind("\n", 0, m.start()) + 1
                    le = U.find("\n", m.start())
                    line = U[ls:le if le >= 0 else None]
                    line_cat = next((k for k, rx in CAT_WORDS if rx.search(line)), "") or c["cat"]
                    line_storey = next((st for st in storeys if st.upper() in line), None)
                    for el in by_profile.get(f"{p}|{line_cat}", []):
                        if line_storey and el["storey"] != line_storey:
                            continue
                        if el.get("mark") and (el["global_id"], c["key"]) in links:
                            continue
                        link(el, c, CONF["size"], "size",
                             f"Size {p} + element type {line_cat}{' on ' + line_storey if line_storey else ''} (no mark given)",
                             pg, m.start(), len(m.group(0)))
    # 4. element type only
    claimed = {k[0] for k in links}
    linked_calcs = {k[1] for k in links}
    for c in calcs:
        if c["scanned"] or c["front"] or not c["cat"] or c.get("mark_hits") or c["key"] in linked_calcs:
            continue
        pg = page_by_n[c["pages"][0]]
        rx = dict(CAT_WORDS)[c["cat"]]
        mm = rx.search(pg["text"])
        idx, n = (mm.start(), len(mm.group(0))) if mm else (0, 0)
        for el in elements:
            if el["cat"] == c["cat"] and el["global_id"] not in claimed:
                link(el, c, CONF["type"], "type", f"Calc covers {c['cat'].lower()}s but names no marks or sizes", pg, idx, n)
    return sorted(links.values(), key=lambda l: (l["calc_key"], l["global_id"]))
