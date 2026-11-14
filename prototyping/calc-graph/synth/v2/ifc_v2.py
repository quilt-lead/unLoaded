"""Write the v2 design to IFC4 (IfcOpenShell, shared helpers in calcgraph.ifc_common).

Metres in the file (model is in feet). GlobalId = uuid5(NS, element id), so an element keeps
its GlobalId in every layout / revision (what the revision store diffs on). Every element
carries Pset_CalcGraph: ElementId, Roles, Frame, CalcRecords (the record ids that design it).
"""
from __future__ import annotations

import math
import uuid

import numpy as np

from calcgraph.ifc_common import IfcBuilder

from . import aisc
from .model import PIER_TOP

NS = uuid.UUID("5b8f2a0e-7c1d-4f7e-9d3a-0c2b6e9a4d11")
FT = 0.3048
IN = 0.0254
STOREYS = [("Foundation", -3.0 * FT), ("Level 1", 0.0), ("Level 2", 14 * FT), ("Level 3", 27 * FT), ("Roof", 40 * FT)]
LV_STOREY = {"L1": "Level 1", "L2": "Level 2", "L3": "Level 3", "RF": "Roof"}


def write(exp: dict, path: str, label: str = "Base design", timestamp: str = "2026-11-14T09:00:00") -> dict[str, str]:
    B = IfcBuilder(path, namespace=NS, project_name="Harbor View Office (synthetic)",
                   project_description="Synthetic 3-storey steel office - calc-graph v2", project_phase=label,
                   building_name="Harbor View Office", storeys=STOREYS, author="calc-graph synth v2",
                   originating_system="calc-graph synth v2 generator", timestamp=timestamp)
    designed: dict[str, list[str]] = {}
    for r in exp["relations"]:
        if r["kind"] == "designed-by":
            designed.setdefault(r["src"], []).append(r["dst"])

    def iprof(name):
        s = aisc.get(name)
        if s["Type"] == "HSS":
            return B.rect_hollow_profile(name, s["B"] * IN, s["Ht"] * IN, s["tdes"] * IN)
        return B.i_profile(name, s["bf"] * IN, s["d"] * IN, s["tw"] * IN, s["tf"] * IN)

    def member(p1, p2, size, top_of_steel=True, trim_i=0.0, trim_j=0.0):
        p1, p2 = np.array(p1, float) * FT, np.array(p2, float) * FT
        dv = p2 - p1
        L0 = float(np.linalg.norm(dv))
        zdir = dv / L0
        p1 = p1 + zdir * trim_i * FT
        L = L0 - (trim_i + trim_j) * FT
        up = np.array([0.0, 0.0, 1.0])
        xdir = np.cross(up, zdir)
        if np.linalg.norm(xdir) < 1e-6:
            xdir = np.array([1.0, 0.0, 0.0])
        xdir /= np.linalg.norm(xdir)
        origin = p1 - up * aisc.get(size)["d"] * IN / 2 if top_of_steel else p1
        return B.ax(tuple(origin), tuple(zdir), tuple(xdir)), B.solid(iprof(size), L)

    def box(cx, cy, z0, sx, sy, sz):
        return B.ax((cx * FT, cy * FT, z0 * FT)), B.solid(B.rect_profile(sx * FT, sy * FT), sz * FT)

    gids = {}
    els = {e["id"]: e for e in exp["elements"]}
    support = {}
    for r in exp["relations"]:
        if r["kind"] == "frames-into" and r.get("end"):
            support[(r["src"], r["end"])] = r["dst"]

    def face(member_id: str, end: str) -> float:
        """Distance (ft) from the support's centreline to its face along the member, + 1" gap:
        members stop at the face of what they frame into, as fabricated."""
        m = els[member_id]
        sup = els.get(support.get((member_id, end), ""))
        if not sup:
            return 0.0
        ux, uy = m["p2"][0] - m["p1"][0], m["p2"][1] - m["p1"][1]
        if sup["type"] == "column":
            s_ = aisc.get(sup["size"])
            half = (s_["d"] if abs(ux) >= abs(uy) else s_["bf"]) / 2   # columns: depth along X
        elif sup["type"] in ("beam", "girder"):
            half = aisc.get(sup["size"])["tw"] / 2
        else:
            return 0.0
        return (half + 1.0) / 12

    def obox(cx, cy, z0, ux, uy, length, width, height):
        """Box oriented along plan direction (ux, uy), centred at (cx, cy), from z0 up."""
        n = math.hypot(ux, uy) or 1.0
        ax = B.ax((cx * FT, cy * FT, z0 * FT), (0, 0, 1), (ux / n, uy / n, 0))
        return ax, B.solid(B.rect_profile(length * FT, width * FT), height * FT)

    def emit(cls, e, name, otype, placement, storey, pre, extra=None):
        inst, gid = B.product(cls, e["id"], name, otype, placement[0], placement[1], storey, pre)
        ps = {"Pset_CalcGraph": {"ElementId": e["id"], "Roles": ",".join(e.get("roles", [])), "Frame": e.get("frame", "") or ",".join(e.get("frames", [])),
                                 "CalcRecords": ";".join(designed.get(e["id"], []))},
              "Identity Data": {"Mark": e.get("mark") or e["id"]}}
        if extra:
            ps["Structural"] = {k: str(v) for k, v in extra.items()}
        B.psets(inst, e["id"], ps)
        gids[e["id"]] = gid

    for e in exp["elements"]:
        t = e["type"]
        if t in ("beam", "girder"):
            emit("IfcBeam", e, e["id"], e["size"], member(e["p1"], e["p2"], e["size"], True, face(e["id"], "i"), face(e["id"], "j")),
                 LV_STOREY[e["level"]], "BEAM",
                 {"Section": e["size"], "Span": f"{e['span_ft']:.2f} ft", "Camber": e["camber_in"], "Studs": e["studs"],
                  "Grade": "A992"})
        elif t == "column":
            s = aisc.get(e["size"])
            ax = B.ax((e["x"] * FT, e["y"] * FT, e["z0"] * FT), (0, 0, 1), (0, 1, 0))
            # physical bottom = top of its base plate (column stands on the plate on the pier)
            emit("IfcColumn", e, e["id"], e["size"], (ax, B.solid(iprof(e["size"]), (e["z1"] - e["z0"]) * FT)), "Level 1",
                 "COLUMN", {"Section": e["size"], "Grid": e["grid"], "Grade": "A992"})
        elif t == "brace":
            emit("IfcMember", e, e["id"], e["size"], member(e["p1"], e["p2"], e["size"], False, 0.75, 0.75),
                 LV_STOREY.get(e["level"], "Level 1"), "BRACE", {"Section": e["size"], "Grade": "A500 Gr C"})
        elif t == "footing":
            emit("IfcFooting", e, e["id"], f"Spread footing {e['B_ft']}' sq x {e['h_in']}\"",
                 box(e["x"], e["y"], e["z_top"] - e["h_in"] / 12, e["B_ft"], e["B_ft"], e["h_in"] / 12), "Foundation",
                 "PAD_FOOTING", {"Size": f"{e['B_ft']}' x {e['B_ft']}' x {e['h_in']}\"", "Reinforcing": e["bars"]})
        elif t == "pier":
            b = e["b_in"] / 12
            emit("IfcColumn", e, e["id"], f"Pier {e['pier_type']}", box(e["x"], e["y"], e["z0"], b, b, e["z1"] - e["z0"]),
                 "Foundation", "PILASTER", {"Size": f"{e['b_in']:.0f}x{e['b_in']:.0f}", "Reinforcing": e["bars"]})
        elif t == "grade_beam":
            (x1, y1, z), (x2, y2, _) = e["p1"], e["p2"]
            L0 = math.dist((x1, y1), (x2, y2))
            ang = math.atan2(y2 - y1, x2 - x1)
            # spans between footing faces, embedded 6" into each footing (frames into, not over, the pier)
            fa, fb = (els.get(support.get((e["id"], k), ""), {}).get("B_ft", 0.0) for k in ("i", "j"))
            ta, tb = max(0.0, fa / 2 - 0.5), max(0.0, fb / 2 - 0.5)
            L = L0 - ta - tb
            ux, uy = (x2 - x1) / L0, (y2 - y1) / L0
            cx, cy = x1 + ux * (ta + L / 2), y1 + uy * (ta + L / 2)
            ax = B.ax((cx * FT, cy * FT, (z - e["h_in"] / 12) * FT), (0, 0, 1), (math.cos(ang), math.sin(ang), 0))
            emit("IfcBeam", e, e["id"], f"Grade beam {e['b_in']}x{e['h_in']}",
                 (ax, B.solid(B.rect_profile(L * FT, e["b_in"] * IN), e["h_in"] * IN)), "Foundation", "BEAM",
                 {"Size": f"{e['b_in']}x{e['h_in']}"})
        elif t == "connection" and e["id"].startswith("BP-"):
            emit("IfcPlate", e, e["id"], f"Base plate {e['conn_type']}",
                 box(e["x"], e["y"], PIER_TOP, e["B_in"] / 12, e["N_in"] / 12, e["t_in"] / 12), "Level 1", "NOTDEFINED",
                 {"Plate": f"PL{e['t_in']}x{e['B_in']:.0f}x{e['N_in']:.0f}", "Anchor Rods": e["rods"], "Type": e["conn_type"]})
        elif t == "connection":
            m = els.get(e["member"])
            if not m or "p1" not in m:
                continue
            p = np.array(m["p1"] if e["end"] == "i" else m["p2"], float)
            q = np.array(m["p2"] if e["end"] == "i" else m["p1"], float)
            u = (q - p) / max(np.linalg.norm(q - p), 1e-9)
            if m["type"] == "brace":   # gusset at the brace end, overlapping the brace and the member it lands on
                c = p + u * 0.6
                geom = box(c[0], c[1], c[2] - 0.3, 0.6, 0.6, 0.6)
            else:                      # single plate from the support face 9" into the member's web
                f = face(m["id"], e["end"])
                d_ft = aisc.get(m["size"])["d"] / 12
                h = max(0.5, d_ft - 0.75)
                c = p + u * (f - 1.0 / 12 + 0.375)
                geom = obox(c[0], c[1], p[2] - 0.375 - h, u[0], u[1], 0.75 + 1.0 / 12, 0.375 / 12 * 2, h)
            emit("IfcPlate", e, e["id"], f"Connection {e['conn_type']}", geom,
                 LV_STOREY.get(m.get("level", "L1"), "Level 1"), "NOTDEFINED",
                 {"Type": e["conn_type"], "Member": e["member"], "End": e["end"], "Supports": e["to"]})
        elif t == "deck":
            z = {"L2": 14, "L3": 27, "RF": 40}[e["level"]]
            th = 6.25 / 12 if e["level"] != "RF" else 1.5 / 12
            emit("IfcSlab", e, e["id"], e["name"], box(60, 42.5, z, 120.5, 85.5, th), LV_STOREY[e["level"]],
                 "ROOF" if e["level"] == "RF" else "FLOOR", {"Deck": e["name"]})
    B.write(path)
    return gids
