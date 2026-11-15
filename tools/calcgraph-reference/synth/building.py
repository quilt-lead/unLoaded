"""Logical model of the synthetic steel-frame building.

Everything here is deterministic. Each element has a stable logical ``key`` that
the IFC writer turns into a stable GlobalId (uuid5), so the same element keeps
the same GlobalId across model revisions - which is what the revision store and
the future diff feature key on.

Ground truth produced here:
- ``design_calc``: the calc id that sized the element (None for elements no calc covers)
- ``ref_calcs``: calcs that mention the element's mark without designing it
- ``load_path``: (src_key, dst_key) edges - src carries load to dst
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import shapes

XS = [0.0, 8.0, 16.0, 24.0, 32.0]
YS = [0.0, 7.0, 14.0, 21.0]
XL = "ABCDE"
YL = "1234"
LEVELS = [("Level 2", 4.2, "2"), ("Level 3", 8.4, "3"), ("Roof", 12.6, "R")]
COL_TOP = 12.6
BASE_PL_T = 0.038  # 1-1/2" base plate
PLATE_H = 0.229  # 9" shear tab
PLATE_GAP_TOP = 0.05

# Truth calc ids (also used by the PDF writer)
K_FRONT, K_CRIT, K_SLAB, K_BEAM, K_ROOF, K_CANT = "K01", "K02", "K03", "K04", "K05", "K06"
K_ST1, K_MF1, K_COL, K_BP, K_BR, K_FTG = "K07", "K08", "K09", "K10", "K11", "K12"


@dataclass
class El:
    key: str
    ifc_class: str
    mark: str | None
    name: str
    object_type: str
    storey: str
    geom: dict
    psets: dict[str, dict[str, str]] = field(default_factory=dict)
    design_calc: str | None = None
    ref_calcs: list[str] = field(default_factory=list)
    # analysis bookkeeping (not written to IFC)
    meta: dict = field(default_factory=dict)


@dataclass
class Building:
    rev: int
    elements: list[El]
    load_path: list[tuple[str, str]]
    by_key: dict[str, El]
    label: str


def col_key(i: int, j: int) -> str:
    return f"col:{XL[i]}/{YL[j]}"


def col_mark(i: int, j: int) -> str:
    return f"C{1 + j * 5 + i}"


def col_size(i: int, j: int) -> str:
    if j == 3:
        return "W14X90"  # moment frame line 4
    if i in (0, 4) or j == 0:
        return "W12X53"
    return "W14X68"


def build(rev: int = 1) -> Building:
    """Build the logical model. rev 2 removes column C8 (grid C/2) and upsizes the
    framing that used to sit on it - the 'remove a column' scenario."""
    els: list[El] = []
    lp: list[tuple[str, str]] = []
    removed_cols = {(2, 1)} if rev == 2 else set()
    upsized: set[str] = set()

    def add(e: El) -> El:
        els.append(e)
        return e

    # ---------------- columns, base plates, footings ----------------
    for j in range(4):
        for i in range(5):
            if (i, j) in removed_cols:
                continue
            x, y = XS[i], YS[j]
            sec = col_size(i, j)
            c = add(El(
                key=col_key(i, j), ifc_class="IfcColumn", mark=col_mark(i, j), name=col_mark(i, j),
                object_type=sec, storey="Level 1",
                geom={"kind": "column", "base": (x, y, 0.0), "top": COL_TOP, "section": sec},
                psets={"Identity Data": {"Mark": col_mark(i, j)},
                       "Structural": {"Section": sec, "Grid": f"{XL[i]}/{YL[j]}", "Grade": "A992",
                                      "Base Level": "Level 1", "Top Level": "Roof"}},
                design_calc=K_COL,
            ))
            c.meta.update(i=i, j=j)
            bp = add(El(
                key=f"bp:{XL[i]}/{YL[j]}", ifc_class="IfcPlate", mark=None, name="Column base plate",
                object_type="Base plate PL1-1/2x18x18", storey="Foundation",
                geom={"kind": "box", "min": (x - 0.2286, y - 0.2286, -BASE_PL_T), "max": (x + 0.2286, y + 0.2286, 0.0)},
                psets={"Structural": {"Plate": "PL 1-1/2 x 18 x 18", "Grade": "A36", "Anchor Rods": "(4) 3/4 F1554 Gr 36",
                                      "Grid": f"{XL[i]}/{YL[j]}"}},
                design_calc=K_BP,
            ))
            fmark = "F1" if (i in (0, 4) and j in (0, 3)) else ("F2" if (i in (0, 4) or j in (0, 3)) else "F3")
            f = add(El(
                key=f"ftg:{XL[i]}/{YL[j]}", ifc_class="IfcFooting", mark=fmark, name=fmark,
                object_type="Spread footing", storey="Foundation",
                geom={"kind": "footing", "centre": (x, y), "top": -BASE_PL_T},  # size filled after analysis
                psets={"Identity Data": {"Mark": fmark}, "Structural": {"Grid": f"{XL[i]}/{YL[j]}", "f'c": "4,000 psi"}},
                design_calc=K_FTG,
            ))
            f.meta.update(i=i, j=j)
            lp.append((c.key, bp.key))
            lp.append((bp.key, f.key))

    # ---------------- framing per level ----------------
    def plate(member: El, support_key: str, axis: str, sign: int, origin: tuple[float, float], z: float,
              cls: str, start: float, level_name: str) -> None:
        """Connection plate at a member end. axis 'X'/'Y' = member direction,
        origin = support centreline point, sign = +1 plate goes +axis from origin."""
        t = 0.0095 if cls == "ST-1" else 0.019
        a0, a1 = sorted((start * sign, (start + 0.20) * sign))
        ox, oy = origin
        zmax = z - PLATE_GAP_TOP
        zmin = zmax - PLATE_H
        if axis == "X":
            mn, mx = (ox + a0, oy - t / 2, zmin), (ox + a1, oy + t / 2, zmax)
        else:
            mn, mx = (ox - t / 2, oy + a0, zmin), (ox + t / 2, oy + a1, zmax)
        end = "i" if sign > 0 else "j"
        k = f"cx:{member.key}:{end}"
        desc = "Shear tab connection ST-1" if cls == "ST-1" else "Moment connection MF-1"
        props = ({"Class": "ST-1 single-plate shear", "Bolts": "(4) 3/4 A325-N", "Plate": "3/8 A36"} if cls == "ST-1"
                 else {"Class": "MF-1 bolted flange plate", "Bolts": "(8) 7/8 A490-X", "Plate": "3/4 A572-50"})
        props["Supports"] = member.mark or ""
        add(El(key=k, ifc_class="IfcPlate", mark=cls, name=desc, object_type=desc, storey=level_name,
               geom={"kind": "box", "min": mn, "max": mx},
               psets={"Identity Data": {"Mark": cls}, "Connection": props},
               design_calc=K_ST1 if cls == "ST-1" else K_MF1))
        lp.append((member.key, k))
        lp.append((k, support_key))

    for lname, z, p in LEVELS:
        roof = p == "R"
        bp_ = "RB" if roof else f"{p}B"
        gp_ = "RG" if roof else f"{p}G"
        slab_key = f"slab:{p}"
        if roof:
            add(El(key=slab_key, ifc_class="IfcSlab", mark="RF-1", name="RF-1", object_type="Roof deck 1.5in B 20ga",
                   storey=lname, geom={"kind": "box", "min": (-0.10, -0.10, z), "max": (32.10, 21.10, z + 0.075)},
                   psets={"Identity Data": {"Mark": "RF-1"}, "Structural": {"Thickness": "1.5 in metal deck", "Deck": "1.5B20"}},
                   design_calc=K_ROOF, ref_calcs=[K_ROOF]))
        else:
            add(El(key=slab_key, ifc_class="IfcSlab", mark=f"SL-{p}", name=f"SL-{p}", object_type="PT slab 200",
                   storey=lname, geom={"kind": "box", "min": (-0.10, -0.10, z), "max": (32.10, 21.10, z + 0.20)},
                   psets={"Identity Data": {"Mark": f"SL-{p}"},
                          "Structural": {"Thickness": "200 mm (8 in)", "System": "Post-tensioned", "f'c": "5,000 psi"}},
                   design_calc=K_SLAB))

        girders: dict[tuple[int, int], El] = {}
        # girders along Y on every grid line
        for i in range(5):
            for jj in range(3):
                sec = "W16X26" if roof else ("W18X35" if i in (0, 4) else "W24X55")
                mark = f"{gp_}{1 + i * 3 + jj}"
                g = add(El(
                    key=f"girder:{p}:{XL[i]}:{YL[jj]}-{YL[jj + 1]}", ifc_class="IfcBeam", mark=mark, name=mark,
                    object_type=sec, storey=lname,
                    geom={"kind": "member", "p1": (XS[i], YS[jj] + 0.22, z), "p2": (XS[i], YS[jj + 1] - 0.22, z), "section": sec},
                    psets={"Identity Data": {"Mark": mark},
                           "Structural": {"Section": sec, "Grid": f"{XL[i]}/{YL[jj]}-{YL[jj + 1]}", "Grade": "A992",
                                          "Span": "7.0 m", "Role": "girder"}},
                    design_calc=K_ROOF if roof else K_BEAM,
                ))
                g.meta.update(kind="girder", i=i, j=jj, level=p, span=7.0 - 0.44)
                girders[(i, jj)] = g
                lp.append((slab_key, g.key))
                for end, (jc, sign) in enumerate(((jj, +1), (jj + 1, -1))):
                    if (i, jc) in removed_cols:
                        upsized.add(g.key)
                        continue
                    plate(g, col_key(i, jc), "Y", sign, (XS[i], YS[jc]), z, "ST-1", 0.10, lname)
        # grid beams along X
        for j in range(4):
            for i in range(4):
                if roof:
                    sec = "W12X19"
                else:
                    sec = "W21X44" if j == 3 else ("W16X26" if j == 0 else "W18X35")
                mark = f"{bp_}{1 + j * 4 + i}"
                b = add(El(
                    key=f"beam:{p}:{XL[i]}-{XL[i + 1]}:{YL[j]}", ifc_class="IfcBeam", mark=mark, name=mark,
                    object_type=sec, storey=lname,
                    geom={"kind": "member", "p1": (XS[i] + 0.22, YS[j], z), "p2": (XS[i + 1] - 0.22, YS[j], z), "section": sec},
                    psets={"Identity Data": {"Mark": mark},
                           "Structural": {"Section": sec, "Grid": f"{XL[i]}-{XL[i + 1]}/{YL[j]}", "Grade": "A992",
                                          "Span": "8.0 m", "Role": "moment frame beam" if j == 3 else "beam"}},
                    design_calc=K_ROOF if roof else K_BEAM,
                ))
                b.meta.update(kind="grid", i=i, j=j, level=p, span=8.0 - 0.44, trib=1.75 if j in (0, 3) else 3.5)
                lp.append((slab_key, b.key))
                cls = "MF-1" if j == 3 else "ST-1"
                for (ic, sign) in ((i, +1), (i + 1, -1)):
                    if (ic, j) in removed_cols:
                        upsized.add(b.key)
                        continue
                    plate(b, col_key(ic, j), "X", sign, (XS[ic], YS[j]), z, cls, 0.10, lname)
        # infill beams along X at mid-bay, framing into girders
        for jj in range(3):
            for i in range(4):
                sec = "W12X19" if roof else "W18X35"
                mark = f"{bp_}{17 + jj * 4 + i}"
                y = YS[jj] + 3.5
                b = add(El(
                    key=f"infill:{p}:{XL[i]}-{XL[i + 1]}:{YL[jj]}.5", ifc_class="IfcBeam", mark=mark, name=mark,
                    object_type=sec, storey=lname,
                    geom={"kind": "member", "p1": (XS[i] + 0.15, y, z), "p2": (XS[i + 1] - 0.15, y, z), "section": sec},
                    psets={"Identity Data": {"Mark": mark},
                           "Structural": {"Section": sec, "Grid": f"{XL[i]}-{XL[i + 1]}/{YL[jj]}.5", "Grade": "A992",
                                          "Span": "8.0 m", "Role": "infill beam"}},
                    design_calc=K_ROOF if roof else K_BEAM,
                ))
                b.meta.update(kind="infill", i=i, j=jj, level=p, span=8.0 - 0.30, trib=3.5)
                lp.append((slab_key, b.key))
                for (ig, sign) in ((i, +1), (i + 1, -1)):
                    plate(b, girders[(ig, jj)].key, "X", sign, (XS[ig], y), z, "ST-1", 0.03, lname)

        if p == "2":
            # cantilever balcony beam off column E/2, direct moment connection (no plate element)
            x0 = XS[4] + shapes.w_si(col_size(4, 1))["d"] / 2 + 0.01
            cb = add(El(
                key="cant:2:E/2", ifc_class="IfcBeam", mark="2CB1", name="2CB1", object_type="W16X31", storey=lname,
                geom={"kind": "member", "p1": (x0, YS[1], z), "p2": (x0 + 2.7, YS[1], z), "section": "W16X31"},
                psets={"Identity Data": {"Mark": "2CB1"},
                       "Structural": {"Section": "W16X31", "Grid": "E/2 east", "Grade": "A992", "Span": "2.7 m cantilever",
                                      "Role": "cantilever"}},
                design_calc=K_CANT, ref_calcs=[K_BEAM, K_COL],
            ))
            cb.meta.update(kind="cant", level="2", span=2.7, trib=3.5)
            lp.append((cb.key, col_key(4, 1)))

    # ---------------- X bracing, grid A between 1 and 2, every storey ----------------
    z0s = [0.0, 4.2, 8.4]
    bf_a1 = shapes.w_si(col_size(0, 0))["bf"] / 2
    for s, z0 in enumerate(z0s):
        storey = ["Level 1", "Level 2", "Level 3"][s]
        for n, (ya, yb, low) in enumerate(((bf_a1 + 0.003, 7.0 - bf_a1 - 0.003, (0, 0)), (7.0 - bf_a1 - 0.003, bf_a1 + 0.003, (0, 1)))):
            mark = f"BR1-{s * 2 + n + 1}"
            br = add(El(
                key=f"brace:{s}:{n}", ifc_class="IfcMember", mark=mark, name=mark, object_type="HSS6X6X3/8", storey=storey,
                geom={"kind": "brace", "p1": (0.0, ya, z0 + 0.4), "p2": (0.0, yb, z0 + 4.2 - 0.4), "section": "HSS6X6X3/8"},
                psets={"Identity Data": {"Mark": mark},
                       "Structural": {"Section": "HSS6X6X3/8", "Grid": "A/1-2", "Grade": "A500 Gr C", "Role": "brace"}},
                design_calc=K_BR,
            ))
            lp.append((br.key, col_key(*low)))

    # ---------------- elevator pit walls (no calc covers these) ----------------
    for n, x in enumerate((11.0, 12.8)):
        add(El(key=f"wall:pit:{n}", ifc_class="IfcWall", mark="W1", name="W1", object_type="Elevator pit wall 200",
               storey="Foundation", geom={"kind": "box", "min": (x, 9.5, -1.5), "max": (x + 0.2, 11.5, 0.0)},
               psets={"Identity Data": {"Mark": "W1"}, "Structural": {"Thickness": "200 mm", "Role": "elevator pit"}}))

    by_key = {e.key: e for e in els}
    if upsized:
        for k in upsized:
            e = by_key[k]
            new = "W21X44" if e.storey == "Roof" else "W24X68"
            e.object_type = new
            e.geom = {**e.geom, "section": new}
            e.psets["Structural"]["Section"] = new
            e.psets["Structural"]["Note"] = "Upsized after column C8 removal - transfer framing, design in progress"
    label = "Rev 1 - issued for permit" if rev == 1 else "Rev 2 - column C8 removed, adjacent framing upsized"
    return Building(rev=rev, elements=els, load_path=lp, by_key=by_key, label=label)
