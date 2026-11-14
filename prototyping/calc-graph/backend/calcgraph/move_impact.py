"""Move / remove a column: stale calc records, screened new demands, and a health meter.

Generic over a REGISTRY-shaped graph (elements with geometry, typed relations, calc records
with values), not over the synthetic generator: it never calls the design code that produced
the records. Inputs it uses:
- elements: columns {id, x, y, roles}, members {id, p1, p2, size, roles}, footings {B_ft, x, y},
  grade beams {p1, p2, b_in}, connections {id, conn_type}
- relations: frames-into (member -> support, with `end` and `via` connection), bears-on,
  connected-by, designed-by (element -> record), instance-of (connection -> DETAIL type),
  member-of (element -> FRAME:...), feeds (record -> record)
- records: values (w_D/L/Lr klf, self weight, reactions R_i_D / R_i_L, phiMn, phiVn, Pu, UC,
  P_service, capacities of typical details)

Three outputs, each labelled:
1. topological stale set - walk geometry (who frames into the moved column, who frames into
   those), load path (reactions down to columns, footings), connections, lateral membership
   (frame lines, chevron beams, collectors) and foundations (footing moves, grade beam
   spans, clashes). Every record carries its reason chain.
2. screening - new span from the moved geometry; a LOCAL PyNite re-solve of every affected
   beam / girder with the loads its own record (and the records of the members it carries)
   print; new demand and an ESTIMATED UC at the CURRENT size; reaction deltas pushed to the
   columns (UC scaled with axial), footings (bearing at the current size, required size) and
   connections (end reaction vs the typical detail's capacity). Labelled "estimate".
3. health meter - engineering categories, each with its reasons: easy (recalc only),
   moderate (a member or typical connection needs the next size, footing grows), hard
   (column resize, foundation clash, connection beyond the typicals, removal / transfer,
   lateral system or lateral analysis touched), do-not-move (a frame column whose frame
   members would exceed capacity, or no rolled shape works). Score 0-100 for the meter.
"""
from __future__ import annotations

import math
from collections import defaultdict

import networkx as nx
from Pynite import FEModel3D

E_KSF = 29000.0 * 144.0
COMBOS = {"LC1": (1.4, 0.0, 0.0), "LC2": (1.2, 1.6, 0.5), "LC3": (1.2, 0.5, 1.6)}
CHANGE = 0.05          # a record is "screened stale" when its estimated demand moves > 5 %
QA_DEFAULT = 4.0


def _shape(size: str) -> dict | None:
    try:
        from synth.v2 import aisc   # section property table (AISC v16) - data, not design logic
        return aisc.get(size)
    except Exception:
        return None


def _phi_mn(size: str, lb: float) -> float | None:
    try:
        from synth.v2 import aisc
        return aisc.phi_mn(size, lb)["phi_mn"]
    except Exception:
        return None


class Graph:
    def __init__(self, exp: dict):
        self.exp = exp
        self.el = {e["id"]: e for e in exp["elements"]}
        self.rec = {r["id"]: r for r in exp["records"]}
        self.types = {t["id"]: t for t in exp.get("types", [])}
        self.sup: dict[str, dict[str, str]] = defaultdict(dict)      # member -> end -> support id
        self.via: dict[tuple[str, str], str] = {}                     # (member, end) -> connection id
        self.carried: dict[str, list[tuple[str, str]]] = defaultdict(list)   # support -> [(member, end)]
        self.designed: dict[str, list[str]] = defaultdict(list)
        self.instance: dict[str, str] = {}
        self.member_of: dict[str, list[str]] = defaultdict(list)
        self.bears: dict[str, list[str]] = defaultdict(list)
        self.feeds: dict[str, list[str]] = defaultdict(list)
        self.links_exact = 0
        self.links_inferred = 0
        for r in exp["relations"]:
            k = r["kind"]
            if k == "frames-into":
                end = r.get("end", "i")
                self.sup[r["src"]][end] = r["dst"]
                self.carried[r["dst"]].append((r["src"], end))
                if r.get("via"):
                    self.via[(r["src"], end)] = r["via"]
            elif k == "designed-by":
                self.designed[r["src"]].append(r["dst"])
            elif k == "instance-of":
                self.instance[r["src"]] = r["dst"]
            elif k == "member-of":
                self.member_of[r["src"]].append(r["dst"])
            elif k == "bears-on":
                self.bears[r["src"]].append(r["dst"])
            elif k == "feeds":
                self.feeds[r["src"]].append(r["dst"])
            if r.get("confidence", "exact") == "exact":
                self.links_exact += 1
            else:
                self.links_inferred += 1
        self.type_cap = {}
        for tid in self.types:
            for rid in self.designed.get(tid, []):
                cap = self.rec[rid].get("capacity")
                if cap:
                    self.type_cap[tid] = cap
        self.occ = defaultdict(list)
        for o in exp.get("occurrences", []):
            self.occ[o["ref"]].append(o)

    def xy(self, eid: str) -> tuple[float, float]:
        e = self.el[eid]
        return (e["x"], e["y"])

    def frames(self, eid: str) -> list[str]:
        return [m[6:] for m in self.member_of.get(eid, []) if m.startswith("FRAME:")]


# ------------------------------------------------------------------ geometry
def _line_intersect(p, d, a, b):
    """Point where the line p + t d meets the (infinite) line through a, b."""
    ex, ey = b[0] - a[0], b[1] - a[1]
    den = d[0] * ey - d[1] * ex
    if abs(den) < 1e-9:
        return None
    t = ((a[0] - p[0]) * ey - (a[1] - p[1]) * ex) / den
    return (p[0] + t * d[0], p[1] + t * d[1])


def _endpoint(g: Graph, mid: str, end: str) -> tuple[float, float]:
    e = g.el[mid]
    p = e["p1"] if end == "i" else e["p2"]
    return (p[0], p[1])


def moved_geometry(g: Graph, col: str, dx: float, dy: float) -> dict[str, dict]:
    """New plan endpoints of every member whose geometry changes when `col` moves: members
    framing into the column follow it; members framing into a moved member keep their own
    line and slide to the support's new line (re-span). Returns {member: {p1, p2, L0, L1, why}}."""
    cx, cy = g.xy(col)
    newc = (cx + dx, cy + dy)
    geo: dict[str, dict] = {}
    for mid, end in g.carried.get(col, []):
        e = g.el[mid]
        if "p1" not in e:
            continue
        p1, p2 = list(e["p1"][:2]), list(e["p2"][:2])
        if end == "i":
            p1 = list(newc)
        else:
            p2 = list(newc)
        geo[mid] = {"p1": p1, "p2": p2, "why": f"frames into {col} (end {end})"}
    frontier = list(geo)
    while frontier:
        nxt = []
        for sup in frontier:
            a, b = geo[sup]["p1"], geo[sup]["p2"]
            for mid, end in g.carried.get(sup, []):
                e = g.el[mid]
                if "p1" not in e:
                    continue
                cur = geo.get(mid, {"p1": list(e["p1"][:2]), "p2": list(e["p2"][:2])})
                p1, p2 = list(cur["p1"]), list(cur["p2"])
                other = p2 if end == "i" else p1
                d = (e["p2"][0] - e["p1"][0], e["p2"][1] - e["p1"][1])
                hit = _line_intersect(other, d, a, b)
                if not hit:
                    continue
                new_sup = None
                seg = math.dist(a, b)
                t = ((hit[0] - a[0]) * (b[0] - a[0]) + (hit[1] - a[1]) * (b[1] - a[1])) / max(seg * seg, 1e-9)
                if t < -1e-6 or t > 1 + 1e-6:
                    # the support no longer spans past this member: it re-frames onto the collinear
                    # member on the other side of the moved column (the one whose new span covers it)
                    for sib, sv in geo.items():
                        if sib == sup or g.el[sib].get("level") != g.el[sup].get("level"):
                            continue
                        sa, sb = sv["p1"], sv["p2"]
                        hit2 = _line_intersect(other, d, sa, sb)
                        if not hit2:
                            continue
                        sl = math.dist(sa, sb)
                        t2 = ((hit2[0] - sa[0]) * (sb[0] - sa[0]) + (hit2[1] - sa[1]) * (sb[1] - sa[1])) / max(sl * sl, 1e-9)
                        ua = (b[0] - a[0], b[1] - a[1])
                        ub = (sb[0] - sa[0], sb[1] - sa[1])
                        if -1e-6 <= t2 <= 1 + 1e-6 and abs(ua[0] * ub[1] - ua[1] * ub[0]) / max(seg * sl, 1e-9) < 0.2:
                            new_sup, hit = sib, hit2
                            break
                if end == "i":
                    p1 = list(hit)
                else:
                    p2 = list(hit)
                old = (e["p1"][:2] if end == "i" else e["p2"][:2])
                if math.dist(old, hit) < 1e-6 and not new_sup:
                    continue
                geo[mid] = {**geo.get(mid, {}), "p1": p1, "p2": p2,
                            "why": f"frames into {sup}, which moved with {col}"}
                if new_sup:
                    geo[mid].setdefault("reframe", {})[end] = new_sup
                    geo[mid]["why"] = f"re-frames from {sup} onto {new_sup} (moved support no longer spans past it)"
                nxt.append(mid)
        frontier = nxt
    for mid, v in geo.items():
        e = g.el[mid]
        v["L0"] = math.dist(e["p1"][:2], e["p2"][:2])
        v["L1"] = math.dist(v["p1"], v["p2"])
    return geo


def removal_geometry(g: Graph, col: str) -> dict:
    """Members framing into a removed column: the collinear pair with the shortest combined span
    becomes one transfer member (far end to far end); the others frame into it at the column."""
    into = [(m, e) for m, e in g.carried.get(col, []) if "p1" in g.el[m]]
    by_level = defaultdict(list)
    for m, e in into:
        by_level[g.el[m].get("level")].append((m, e))
    out = {"merged": [], "reframed": []}
    for lv, ms in by_level.items():
        best = None
        for i in range(len(ms)):
            for j in range(i + 1, len(ms)):
                a, b = ms[i][0], ms[j][0]
                ea, eb = g.el[a], g.el[b]
                ua = (ea["p2"][0] - ea["p1"][0], ea["p2"][1] - ea["p1"][1])
                ub = (eb["p2"][0] - eb["p1"][0], eb["p2"][1] - eb["p1"][1])
                cross = abs(ua[0] * ub[1] - ua[1] * ub[0]) / (math.hypot(*ua) * math.hypot(*ub))
                if cross > 0.05:
                    continue
                tot = ea["span_ft"] + eb["span_ft"]
                if not best or tot < best[0]:
                    best = (tot, a, b)
        if not best:
            continue
        _, a, b = best
        out["merged"].append({"level": lv, "members": [a, b], "span": best[0]})
        for m, e in ms:
            if m not in (a, b):
                out["reframed"].append({"member": m, "end": e, "onto": f"{a}+{b}"})
    return out


# ------------------------------------------------------------------ local re-solve
def _vec(rv: dict, prefix: str, roof: bool) -> list[float]:
    d = rv.get(f"{prefix}_D") or 0.0
    lv = rv.get(f"{prefix}_L") or 0.0
    return [d, 0.0, lv] if roof else [d, lv, 0.0]


def resolve_beam(L: float, w: list[float], pts: list[tuple[float, list[float]]], size: str, roof: bool,
                 lb: float | None = None) -> dict:
    """Simple span re-solve in PyNite (D, L, Lr cases), checks at the CURRENT size."""
    s = _shape(size)
    m = FEModel3D()
    m.add_node("I", 0, 0, 0)
    m.add_node("J", L, 0, 0)
    ix = (s["Ix"] if s else 500.0) / 20736.0
    a = (s["A"] if s else 10.0) / 144.0
    m.add_material("S", E_KSF, 11200.0 * 144, 0.3, 0.49)
    m.add_section("S", a, ix, ix, ix / 100)
    m.add_member("M", "I", "J", "S", "S")
    m.def_support("I", True, True, True, True, False, False)
    m.def_support("J", False, True, True, False, False, False)
    for n, case in enumerate(("D", "L", "Lr")):
        m.add_member_dist_load("M", "FY", -w[n], -w[n], case=case)
        for x, p in pts:
            if p[n]:
                m.add_member_pt_load("M", "FY", -p[n], min(max(x, 0.0), L), case=case)
    for c, f in COMBOS.items():
        m.add_load_combo(c, {"D": f[0], "L": f[1], "Lr": f[2]})
    m.add_load_combo("SVC", {"D": 1.0, "L": 1.0, "Lr": 1.0})
    m.add_load_combo("LIVE", {"L": 0.0 if roof else 1.0, "Lr": 1.0 if roof else 0.0})
    m.add_load_combo("DEAD", {"D": 1.0})
    m.analyze_linear(check_statics=False, check_stability=False)
    mem = m.members["M"]
    mu = max(max(abs(mem.max_moment("Mz", c)), abs(mem.min_moment("Mz", c))) for c in COMBOS)
    vu = max(max(abs(mem.max_shear("Fy", c)), abs(mem.min_shear("Fy", c))) for c in COMBOS)
    dl = abs(mem.min_deflection("dy", "LIVE")) * 12
    dt = abs(mem.min_deflection("dy", "SVC")) * 12
    out = {"L": L, "mu": mu, "vu": vu, "d_live": dl, "d_total": dt}
    phimn = _phi_mn(size, lb if lb is not None else 0.0)
    phivn = 0.6 * 50 * s["d"] * s["tw"] if s else None
    ratios = {}
    if phimn:
        ratios["flexure"] = mu / phimn
    if phivn:
        ratios["shear"] = vu / phivn
    ratios["defl_live"] = dl / (L * 12 / (240 if roof else 360))
    ratios["defl_total"] = dt / (L * 12 / 240)
    gov = max(ratios, key=ratios.get)
    out.update(phi_mn=phimn, phi_vn=phivn, ratios=ratios, uc=ratios[gov], governs=gov)
    return out


def _fac(v, c="LC2"):
    f = COMBOS[c]
    return v[0] * f[0] + v[1] * f[1] + v[2] * f[2]


def _ru(v) -> float:
    return max(_fac(v, c) for c in COMBOS)


# ------------------------------------------------------------------ main entry
def impact(exp: dict, column: str, dx: float = 0.0, dy: float = 0.0, remove: bool = False,
           platform_status=None) -> dict:
    g = Graph(exp)
    if column not in g.el:
        raise KeyError(column)
    col = g.el[column]
    stale: dict[str, dict] = {}
    est: dict[str, dict] = {}
    notes: list[str] = []

    def mark(rid, reason, chain, kind="topological"):
        if rid not in g.rec:
            return
        if rid not in stale:
            stale[rid] = {"record": rid, "calc": g.rec[rid]["calc"], "kind": g.rec[rid]["kind"],
                          "reasons": [], "chain": chain, "screened": None}
        if reason not in stale[rid]["reasons"]:
            stale[rid]["reasons"].append(reason)

    def mark_el(eid, reason, chain):
        for rid in g.designed.get(eid, []):
            mark(rid, reason, chain + [eid])

    # ---- the column itself and what bears under it
    verb = "removed" if remove else f"moved ({dx:+g}, {dy:+g}) ft"
    chain0 = [column]
    mark_el(column, f"{column} {verb}: tributary area and axial load change", [])
    base = column[4:]
    for fid, why in ((f"BP-{base}", "base plate under the moved column"), (f"P-{base}", "pier under the moved column"),
                     (f"F-{base}", "footing moves with the column; size from the new axial load")):
        if fid in g.el:
            mark_el(fid, why, chain0)

    # ---- geometry
    if remove:
        rg = removal_geometry(g, column)
        geo = {}
        for mg in rg["merged"]:
            for m in mg["members"]:
                mark_el(m, f"merged into one transfer member spanning {mg['span']:.1f} ft (column removed)", chain0)
            notes.append(f"{mg['level']}: {' + '.join(mg['members'])} become one {mg['span']:.1f} ft transfer member - NEW calc record needed")
        for rf in rg["reframed"]:
            mark_el(rf["member"], f"now frames into the transfer member {rf['onto']} instead of {column}", chain0)
    else:
        geo = moved_geometry(g, column, dx, dy)
        for mid, v in geo.items():
            if True:   # every member whose geometry moves is re-checked (skew alone changes the girder's point loads)
                mark_el(mid, f"span {v['L0']:.2f} -> {v['L1']:.2f} ft ({v['why']})", chain0)

    # effective support graph after re-framing
    eff_sup = {m: dict(v) for m, v in g.sup.items()}
    eff_carried = {k: list(v) for k, v in g.carried.items()}
    for mid, v in geo.items():
        for end, ns in v.get("reframe", {}).items():
            old = eff_sup.get(mid, {}).get(end)
            eff_sup.setdefault(mid, {})[end] = ns
            if old in eff_carried:
                eff_carried[old] = [x for x in eff_carried[old] if x != (mid, end)]
            eff_carried.setdefault(ns, []).append((mid, end))
            if old:
                mark_el(old, f"{mid} no longer frames into it (re-framed onto {ns})", [column, mid])

    # ---- screening: affected beams/girders in dependency order (carried members first)
    affected = set(geo) if not remove else set()
    if remove:
        for mg in rg["merged"]:
            affected.update(mg["members"])
        affected.update(rf["member"] for rf in rg["reframed"])
    # supports of affected members are affected (point load moves / changes)
    # load path after re-framing as a NetworkX graph (member -> support); every beam/girder
    # downstream of an affected member carries a changed point load
    lp = nx.DiGraph()
    for m_, ends in eff_sup.items():
        for end_, s_ in ends.items():
            lp.add_edge(m_, s_, end=end_)
    for m in list(affected):
        if m not in lp:
            continue
        for s in nx.descendants(lp, m):
            if s in g.el and g.el[s]["type"] in ("beam", "girder") and s not in affected:
                affected.add(s)
                via = next(iter(nx.shortest_path(lp, m, s)[-2:-1]), m)
                mark_el(s, f"carries {via}: point load position / magnitude changes", [column, m])
    new_rx: dict[str, dict[str, list[float]]] = {}
    old_rx: dict[str, dict[str, list[float]]] = {}

    def member_loads(mid: str, geom_override=None):
        e = g.el[mid]
        rv = next((g.rec[r]["values"] for r in g.designed.get(mid, []) if g.rec[r]["kind"] in ("beam_design", "smf_beam")), None)
        return e, rv

    # carried members before their supports: topological order of the load path on the affected set
    sub = lp.subgraph(affected).copy()
    sub.add_nodes_from(affected)
    order = list(nx.lexicographical_topological_sort(sub))
    resolved = {}
    for _pass in range(1):
        for mid in order:
            e, rv = member_loads(mid)
            if not rv or "w_D_klf" not in rv:
                continue
            roof = e.get("level") == "RF"
            sw = rv.get("self_wt_klf") or 0.0
            w = [rv["w_D_klf"] + sw, rv["w_L_klf"], rv["w_Lr_klf"]]
            p1 = geo.get(mid, {}).get("p1", e["p1"][:2])
            p2 = geo.get(mid, {}).get("p2", e["p2"][:2])
            L = math.dist(p1, p2)
            pts = []
            for c, cend in eff_carried.get(mid, []):
                ce = g.el.get(c)
                if not ce or "p1" not in ce:
                    continue
                if c in resolved:
                    rvec = resolved[c]["Ri_c" if cend == "i" else "Rj_c"]
                else:
                    crv = next((g.rec[r]["values"] for r in g.designed.get(c, []) if g.rec[r]["kind"] in ("beam_design", "smf_beam")), None)
                    if not crv:
                        continue
                    rvec = _vec(crv, "R_i" if cend == "i" else "R_j", roof)
                cp = geo.get(c, {}).get("p1" if cend == "i" else "p2", (ce["p1"] if cend == "i" else ce["p2"])[:2])
                pts.append((math.dist(p1, cp), rvec))
            stops = sorted([0.0] + [a for a, _ in pts] + [L])
            lb = max(b - a for a, b in zip(stops, stops[1:])) if e["type"] == "girder" else 0.0
            r = resolve_beam(L, w, pts, e["size"], roof, lb)
            r["Ri_c"], r["Rj_c"] = _reactions(L, w, pts)
            resolved[mid] = r
            old_rec = next((g.rec[x] for x in g.designed.get(mid, []) if g.rec[x]["kind"] in ("beam_design", "smf_beam")), None)
            est[mid] = {"element": mid, "size": e["size"], "span_old": e.get("span_ft"), "span_new": round(L, 3),
                        "mu_old": old_rec["values"].get("Mu_kft") if old_rec else None, "mu_new": round(r["mu"], 1),
                        "uc_old": old_rec["uc"] if old_rec else None, "uc_new": round(r["uc"], 3), "governs": r["governs"],
                        "method": "estimate - local PyNite re-solve at current size", "record": old_rec["id"] if old_rec else None}
            if r["uc"] > 1.0:
                est[mid]["size_est"] = _size_up(e["size"], r)
            old_rx[mid] = {"i": _vec(rv, "R_i", roof), "j": _vec(rv, "R_j", roof)}
            new_rx[mid] = {"i": r["Ri_c"], "j": r["Rj_c"]}

    # ---- connections at both ends of every affected member
    for mid in list(resolved) + ([m for mg in (rg["merged"] if remove else []) for m in mg["members"]]):
        for end in ("i", "j"):
            cx = g.via.get((mid, end)) or f"CX-{mid}-{end}"
            if cx not in g.el:
                continue
            mark_el(cx, f"end reaction of {mid} changes", [column, mid])
            if mid in new_rx:
                ru = _ru(new_rx[mid][end])
                t = g.instance.get(cx)
                cap = g.type_cap.get(t)
                if cap:
                    est[cx] = {"element": cx, "detail": t, "ru_new": round(ru, 1), "ru_old": round(_ru(old_rx[mid][end]), 1),
                               "capacity": cap, "uc_new": round(ru / cap, 3), "method": "estimate - new end reaction vs typical capacity"}
                    if ru > cap:
                        # next typical of the same family whose bolt row still fits the beam web
                        # (T-distance: d - 2 (tf + 3/4") - 1", 3" pitch)
                        sh = _shape(g.el[mid]["size"])
                        nmax = int((sh["d"] - 2 * (sh["tf"] + 0.75) - 1.0) // 3) if sh else 99
                        better = sorted((c, tid) for tid, c in g.type_cap.items()
                                        if tid.startswith(t.rsplit("-", 1)[0] + "-") and c >= ru
                                        and (g.types.get(tid, {}).get("bolts") or 0) <= nmax)
                        est[cx]["next_typical"] = better[0][1] if better else None
                        est[cx]["special"] = not better
                        if not better:
                            est[cx]["why_special"] = f"no typical with capacity >= {ru:.1f} k fits a {g.el[mid]['size']} web ({nmax} bolts max)"

    # ---- columns, footings, piers, base plates (reaction deltas)
    dcol: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0, 0.0])
    for mid in resolved:
        for end in ("i", "j"):
            s = eff_sup.get(mid, {}).get(end)
            if s and g.el.get(s, {}).get("type") == "column":
                o, n = old_rx[mid][end], new_rx[mid][end]
                for k in range(3):
                    dcol[s][k] += n[k] - o[k]
    if remove:
        # transfer member: both halves' loads + the re-framed members' reactions at the old column
        for mg in rg["merged"]:
            a_, b_ = mg["members"]
            ea, eb = g.el[a_], g.el[b_]
            # orient: a_ runs far end -> column, b_ column -> far end
            def far(m):
                e = g.el[m]
                return ("i", e["p1"][:2]) if g.sup.get(m, {}).get("j") == column else ("j", e["p2"][:2])
            (fa_end, pa), (fb_end, pb) = far(a_), far(b_)
            L = math.dist(pa, pb)
            roof = ea.get("level") == "RF"
            rva = next((g.rec[r]["values"] for r in g.designed.get(a_, []) if g.rec[r]["kind"] == "beam_design"), None)
            rvb = next((g.rec[r]["values"] for r in g.designed.get(b_, []) if g.rec[r]["kind"] == "beam_design"), None)
            if not rva or not rvb:
                continue
            la, lb_ = ea["span_ft"], eb["span_ft"]
            w = [(rva["w_D_klf"] * la + rvb["w_D_klf"] * lb_) / L, (rva["w_L_klf"] * la + rvb["w_L_klf"] * lb_) / L,
                 (rva["w_Lr_klf"] * la + rvb["w_Lr_klf"] * lb_) / L]
            pts = []
            for m in (a_, b_):
                for c, cend in g.carried.get(m, []):
                    crv = next((g.rec[r]["values"] for r in g.designed.get(c, []) if g.rec[r]["kind"] in ("beam_design", "smf_beam")), None)
                    ce = g.el[c]
                    if crv and "p1" in ce:
                        cp = (ce["p1"] if cend == "i" else ce["p2"])[:2]
                        pts.append((math.dist(pa, cp), _vec(crv, "R_i" if cend == "i" else "R_j", roof)))
            for rf in rg["reframed"]:
                if g.el[rf["member"]].get("level") != ea.get("level"):
                    continue
                crv = next((g.rec[r]["values"] for r in g.designed.get(rf["member"], []) if g.rec[r]["kind"] in ("beam_design", "smf_beam")), None)
                if crv:
                    pts.append((la, _vec(crv, "R_i" if rf["end"] == "i" else "R_j", roof)))
            size = max((ea["size"], eb["size"]), key=lambda z: (_shape(z) or {"W": 0})["W"])
            stops = sorted([0.0] + [x for x, _ in pts] + [L])
            lbx = max(q - p_ for p_, q in zip(stops, stops[1:]))
            r = resolve_beam(L, [w[0] + (rva.get("self_wt_klf") or 0), w[1], w[2]], pts, size, roof, lbx)
            ri, rj = _reactions(L, [w[0] + (rva.get("self_wt_klf") or 0), w[1], w[2]], pts)
            req = None
            try:
                from synth.v2 import aisc
                for cand in [c for c in aisc.beam_candidates() if aisc.get(c)["W"] >= (_shape(size) or {"W": 0})["W"]]:
                    rr = resolve_beam(L, [w[0] + aisc.get(cand)["W"] / 1000, w[1], w[2]], pts, cand, roof, lbx)
                    if rr["uc"] <= 1.0:
                        req = cand
                        break
            except Exception:
                pass
            tid = f"NEW:{a_}+{b_}"
            est[tid] = {"element": tid, "size": size, "span_new": round(L, 2), "mu_new": round(r["mu"], 1),
                        "uc_new": round(r["uc"], 3), "governs": r["governs"], "required_size": req,
                        "method": "estimate - transfer member re-solved in PyNite (both halves + re-framed reactions)"}
            if req is None:
                notes.append(f"{tid}: no rolled W shape up to W36 works over {L:.1f} ft - do not remove without a re-think")
            for (end, sup_end, old_m, old_end) in (("i", g.sup[a_][fa_end], a_, fa_end), ("j", g.sup[b_][fb_end], b_, fb_end)):
                rv0 = rva if old_m == a_ else rvb
                old = _vec(rv0, f"R_{old_end}", roof)
                new = ri if end == "i" else rj
                for k in range(3):
                    dcol[sup_end][k] += new[k] - old[k]
    for c, dv in dcol.items():
        if c == column and remove:
            continue
        crec = next((g.rec[r] for r in g.designed.get(c, []) if g.rec[r]["kind"] == "column_design"), None)
        if not crec:
            continue
        pu0 = crec["values"].get("Pu_k") or crec["demand"] or 1.0
        dpu = _fac(dv, "LC2")
        if abs(dpu) / max(pu0, 1e-6) > 0.001 or c == column:
            mark_el(c, f"axial changes by {dpu:+.1f} k (reactions of re-spanned members)", [column])
        pu1 = pu0 + dpu
        est[c] = {"element": c, "size": g.el[c]["size"], "pu_old": round(pu0, 1), "pu_new": round(pu1, 1),
                  "uc_old": crec["uc"], "uc_new": round(crec["uc"] * pu1 / pu0, 3),
                  "method": "estimate - H1 scaled with axial (eccentric moments held)"}
        fid = f"F-{c[4:]}"
        frec = next((g.rec[r] for r in g.designed.get(fid, []) if g.rec[r]["kind"] == "footing"), None)
        if frec:
            ps0 = frec["values"]["P_service_k"]
            ps1 = ps0 + sum(dv)
            qa = frec["values"].get("qa_ksf", QA_DEFAULT)
            b0 = g.el[fid]["B_ft"]
            breq = max(4.0, math.ceil(math.sqrt(max(ps1, 0) / qa) * 2) / 2)
            est[fid] = {"element": fid, "B_old": b0, "B_req": breq, "p_old": ps0, "p_new": round(ps1, 1),
                        "uc_new": round(ps1 / (qa * b0 * b0), 3), "uc_old": frec["uc"],
                        "method": "estimate - bearing at current size, required size from qa"}
            if abs(ps1 - ps0) / max(ps0, 1e-6) > 0.001 or c == column:
                mark_el(fid, f"column load changes by {sum(dv):+.1f} k service", [column, c])
                for x in (f"P-{c[4:]}", f"BP-{c[4:]}"):
                    if x in g.el:
                        mark_el(x, "column load changes", [column, c])

    # ---- foundations: new footing position vs neighbours and grade beams
    clashes = []
    if not remove:
        fid = f"F-{base}"
        if fid in g.el:
            fx, fy = col["x"] + dx, col["y"] + dy
            B = est.get(fid, {}).get("B_req", g.el[fid]["B_ft"])
            B = max(B, g.el[fid]["B_ft"])
            for oid, o in g.el.items():
                if o["type"] == "footing" and oid != fid:
                    if abs(o["x"] - fx) < (o["B_ft"] + B) / 2 and abs(o["y"] - fy) < (o["B_ft"] + B) / 2:
                        clashes.append({"a": fid, "b": oid, "kind": "footing-footing"})
                if o["type"] == "grade_beam":
                    ends = [s for s in g.sup.get(oid, {}).values()]
                    tied = fid in ends or any(r["src"] == oid and r["dst"] == fid for r in exp["relations"] if r["kind"] == "frames-into")
                    if tied:
                        mark_el(oid, f"grade beam span changes: {fid} moves", [column, fid])
                        continue
                    (x1, y1, _), (x2, y2, _) = o["p1"], o["p2"]
                    w = o["b_in"] / 24
                    if fx + B / 2 > min(x1, x2) - w and fx - B / 2 < max(x1, x2) + w and \
                            fy + B / 2 > min(y1, y2) - w and fy - B / 2 < max(y1, y2) + w:
                        clashes.append({"a": fid, "b": oid, "kind": "footing-grade_beam"})
            for c_ in clashes:
                mark_el(c_["b"], f"clashes with the moved footing {fid}", [column, fid])
    # grade beams that frame into the moved footing (relation frames-into GB -> F)
    for r in exp["relations"]:
        if r["kind"] == "frames-into" and r["src"].startswith("GB-") and r["dst"] == f"F-{base}":
            mark_el(r["src"], f"grade beam span changes: F-{base} {'removed' if remove else 'moves'}", [column, f"F-{base}"])

    # ---- lateral
    frames = g.frames(column)
    lateral = []
    if frames:
        for f in frames:
            lateral.append(f"{column} is in {f}: frame stiffness, drift and force distribution change - re-run the frame analysis")
            for eid, mof in g.member_of.items():
                if f"FRAME:{f}" in mof:
                    mark_el(eid, f"member of {f} - frame re-analysis", [column, f"FRAME:{f}"])
            for rid in g.designed.get(f"FRAME:{f}", []):
                mark(rid, f"{f} frame analysis is stale", [column, f"FRAME:{f}"])
    for mid in resolved:
        roles = g.el[mid].get("roles", [])
        e0 = est.get(mid, {})
        change = abs((e0.get("mu_new") or 0) - (e0.get("mu_old") or 0)) / max(e0.get("mu_old") or 1, 1e-6)
        if "scbf_beam" in roles and change > CHANGE:
            fr = g.el[mid].get("frame")
            lateral.append(f"{mid} is a chevron SCBF beam: its gravity load reaches the braces - brace forces change")
            for rid in g.designed.get(f"FRAME:{fr}", []):
                mark(rid, f"gravity on {mid} changes the {fr} brace forces", [column, mid])
            for eid, e in g.el.items():
                if e["type"] == "brace" and e.get("frame") == fr:
                    mark_el(eid, f"gravity on chevron beam {mid} changes", [column, mid])
        if "collector" in roles:
            for rid in g.designed.get(mid, []):
                if g.rec[rid]["kind"] == "collector":
                    mark(rid, f"collector {mid} span/gravity changes", [column, mid])

    # ---- screened subset: estimated demand change > 5 %
    def screened(rid):
        r = g.rec[rid]
        els = r["elements"]
        for e in els:
            x = est.get(e)
            if not x:
                continue
            for a, b in (("mu_old", "mu_new"), ("pu_old", "pu_new"), ("p_old", "p_new"), ("ru_old", "ru_new")):
                if x.get(a) and x.get(b) is not None:
                    return abs(x[b] - x[a]) / abs(x[a]) > CHANGE
        return True   # no estimate: keep it (topology says it is on the path)
    merged_ids = {m for mg in (rg["merged"] if remove else []) for m in mg["members"]}
    for rid, s in stale.items():
        s["screened"] = True if set(g.rec[rid]["elements"]) & merged_ids else screened(rid)

    health = health_of(g, column, remove, est, stale, clashes, lateral, frames, platform_status)
    occ = {}
    touched = {e for rid in stale for e in g.rec[rid]["elements"]} | {column}
    for e in touched:
        occ[e] = g.occ.get(e, [])
    return {"column": column, "dx": dx, "dy": dy, "remove": remove,
            "stale": sorted(stale.values(), key=lambda s: (s["calc"], s["record"])),
            "estimates": est, "geometry": geo, "clashes": clashes, "lateral": lateral, "notes": notes,
            "health": health, "occurrences": occ,
            "labels": {"stale": "topological (load path + connections + lateral + foundations)",
                       "screened": f"estimate: demand change > {CHANGE:.0%}",
                       "estimates": "estimate - not a re-design"}}


def _size_up(size: str, r: dict) -> str | None:
    """Lightest heavier W whose Zx and Ix cover the screened flexure / deflection ratios
    (strength and stiffness scale with Zx and Ix at a given span) - an estimate."""
    try:
        from synth.v2 import aisc
    except Exception:
        return None
    s0 = aisc.get(size)
    need_z = s0["Zx"] * max(r["ratios"].get("flexure", 0), 1.0) if r["ratios"].get("flexure", 0) > 1 else s0["Zx"]
    need_i = s0["Ix"] * max(r["ratios"].get("defl_live", 0), r["ratios"].get("defl_total", 0), 1.0)
    for c in aisc.beam_candidates():
        sc = aisc.get(c)
        if sc["W"] > s0["W"] and sc["Zx"] >= need_z and sc["Ix"] >= need_i:
            return c
    return None


def _reactions(L, w, pts):
    """Simple-span reactions per component (D, L, Lr) - statics, exact."""
    ri, rj = [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]
    for k in range(3):
        ri[k] += w[k] * L / 2
        rj[k] += w[k] * L / 2
        for a, p in pts:
            a = min(max(a, 0.0), L)
            ri[k] += p[k] * (L - a) / L
            rj[k] += p[k] * a / L
    return ri, rj


# ------------------------------------------------------------------ health
BANDS = ["easy", "moderate", "hard", "do-not-move"]


def health_of(g: Graph, column: str, remove: bool, est: dict, stale: dict, clashes: list, lateral: list,
              frames: list, platform_status=None) -> dict:
    reasons: list[tuple[int, str, str]] = []   # (band index, reason, factor)
    col = g.el[column]
    over = {k: v for k, v in est.items() if (v.get("uc_new") or 0) > 1.0}
    mem_over = [k for k in over if g.el.get(k, {}).get("type") in ("beam", "girder")]
    col_over = [k for k in over if g.el.get(k, {}).get("type") == "column"]
    ftg_over = [k for k in over if g.el.get(k, {}).get("type") == "footing"]
    cx_over = [k for k in over if k.startswith("CX-")]
    special = [k for k in cx_over if est[k].get("special")]
    sfrs_over = [k for k in over if g.el.get(k, {}).get("sfrs")]
    if frames:
        reasons.append((2, f"part of the lateral system ({', '.join(frames)}): moving it changes frame geometry - frame re-analysis and re-detailing", "SFRS role"))
        # the screen does not re-run the frame analysis, so a frame member within 5 % of its
        # capacity is treated as having no reserve for the geometry change
        near = [k for k, v in est.items() if g.el.get(k, {}).get("sfrs") and (v.get("uc_new") or 0) > 0.95]
        sfrs_over = sorted(set(sfrs_over) | set(near))
        if sfrs_over:
            reasons.append((3, f"frame member(s) {', '.join(sfrs_over[:3])} at or over capacity at current size (estimate) - frame must be re-designed", "SFRS reserve"))
        else:
            fr_uc = [g.rec[r]["uc"] for f in frames for r in g.designed.get(f"FRAME:{f}", []) if g.rec[r]["uc"] is not None]
            if fr_uc and max(fr_uc) > 0.95:
                reasons.append((3, f"frame drift already at {max(fr_uc):.2f} of the limit - no reserve for a geometry change", "SFRS reserve"))
    if remove:
        reasons.append((2, "column removed: transfer member over two bays, neighbouring columns and footings pick up its load", "removal"))
    if col_over:
        reasons.append((2, f"column(s) {', '.join(col_over[:3])} over capacity at current size (estimate)", "reserve"))
    if clashes:
        reasons.append((2, "footing clash: " + ", ".join(f"{c['a']} vs {c['b']}" for c in clashes[:3]), "foundation clash"))
    if special:
        reasons.append((2, f"{len(special)} connection(s) beyond the largest typical detail - special detail", "connection headroom"))
    if any("SCBF beam" in l or "brace" in l for l in lateral) and not frames:
        reasons.append((2, "gravity change reaches the chevron braces - lateral analysis changes", "lateral"))
    if mem_over:
        reasons.append((1, f"{len(mem_over)} beam/girder(s) over capacity at current size - next size up (estimate, worst UC {max(est[k]['uc_new'] for k in mem_over):.2f})", "reserve"))
    if cx_over and not special:
        reasons.append((1, f"{len(cx_over)} connection(s) exceed their typical detail - next typical", "connection headroom"))
    if ftg_over:
        reasons.append((1, f"footing(s) {', '.join(ftg_over[:3])} must grow (bearing, estimate)", "foundation"))
    if platform_status:
        st = platform_status(column) or {}
        stage = st.get("stage")
        if stage in ("fabricated", "delivered", "erected"):
            reasons.append((2 if stage != "erected" else 3, f"steel already {stage} - field or shop rework", "construction status"))
        elif stage == "approved":
            reasons.append((1, "shop drawings approved - resubmittal required", "construction status"))
        for rsn in st.get("reasons", [])[:2]:
            reasons.append((0, rsn, "construction status"))
    # reserve and fan-out as context (do not raise the band on their own)
    worst = max((v.get("uc_new") or 0 for v in est.values()), default=0)
    n_stale = len(stale)
    sheets = sorted({o.get("sheet") for rid in stale for e in g.rec[rid]["elements"] for o in g.occ.get(e, [])
                     if o.get("doc") == "drawings" and o.get("sheet")})
    reasons.append((0, f"{n_stale} calc records to redo" + (f", {len(sheets)} sheets" if sheets else ""), "fan-out"))
    reasons.append((0, f"worst estimated UC at current sizes {worst:.2f}", "reserve"))
    if g.links_inferred:
        reasons.append((0, f"{g.links_inferred} inferred links in the graph - check them", "data confidence"))
    # design health (engineering only - what the answer key scores) vs construction-adjusted
    # health (adds the platforms' fabrication / erection status, submittals, RFIs, float)
    band = max((b for b, _, f in reasons if f != "construction status"), default=0)
    band_c = max((b for b, _, _ in reasons), default=0)
    def score_of(b):
        return min(100, int(25 * b + min(15, n_stale / 10) + max(0.0, min(10.0, (worst - 0.8) * 25))))
    top = [{"band": BANDS[b], "reason": r, "factor": f} for b, r, f in sorted(reasons, key=lambda t: -t[0])]
    return {"band": BANDS[band], "score": score_of(band), "band_construction": BANDS[band_c],
            "score_construction": score_of(band_c), "construction_status_used": platform_status is not None,
            "reasons": top[:10], "worst_uc": round(worst, 3), "stale_records": n_stale, "sheets": sheets}


def heat(exp: dict, probe_ft: float = 2.0, platform_status=None) -> dict:
    """Health of every column for a small probe move (+/- probe in x and y; worst case), the
    'how hard is this to move' heat view."""
    out = {}
    for e in exp["elements"]:
        if e["type"] != "column":
            continue
        best = None
        for dx, dy in ((probe_ft, 0), (-probe_ft, 0), (0, probe_ft), (0, -probe_ft)):
            try:
                h = impact(exp, e["id"], dx, dy, platform_status=platform_status)["health"]
            except Exception as ex:   # surface, never hide
                h = {"band": "hard", "score": 75, "reasons": [{"band": "hard", "reason": f"engine error: {ex}", "factor": "error"}]}
            if not best or h["score"] > best["score"]:
                best = {**h, "probe": [dx, dy]}
        out[e["id"]] = best
    return out
