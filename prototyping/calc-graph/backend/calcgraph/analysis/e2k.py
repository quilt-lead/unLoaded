"""ETABS text model (.e2k) writer and reader for the analysis adapters.

The writer emits the ETABS .e2k keyword syntax for a SUBSET of the format; the reader parses
that subset back (and tolerates the extra sections/keywords real ETABS exports carry by
ignoring them). Files written here were NOT produced or opened by ETABS: the header says so.

Syntax sources (public examples, read 2026-11-14):
- Karamba3D manual, "Export model to ETABS .e2k": POINT / LINE ... COLUMN "2" "2" 1 and the
  STORIES - IN SEQUENCE FROM TOP block, file parsed top to bottom
  https://manual.karamba3d.com/3-in-depth-component-reference/3.7-export/3.8.5-export-model-to-etabs-.e2k
- ETABS 20.1.0 export (public GitHub: udaytharu/Aman-portfolio-website,
  resources/ETABS/Loads/2.Etabs File_Before Design Check.e2k): CONTROLS, STORY, GRIDSYSTEM / GRID,
  MATERIAL (TYPE / SYMTYPE / FY lines), POINT, LINE COLUMN|BEAM, POINTASSIGN RESTRAINT,
  LINEASSIGN, LOADPATTERN, SEISMIC "User Coefficient", LOADCASE, COMBO ... LOADCASE ... SF.
- ETABS 23.1.1 export (public GitHub: thomasjlittle/keepTABS, frontend/demo_viewer/models/
  Hack_v06.e2k): UNITS "KIP" "IN" "F", FRAMESECTION ... SHAPE "W14X500" FILE "AISC16" (library
  shapes by name), MATERIAL "A992Fy50", LINEASSIGN ... ANG 90 / RELEASE "PINNED", COMBO TYPE
  "Linear Add".

Subset written (in this order):
  $ PROGRAM INFORMATION   PROGRAM "ETABS" VERSION  (target-format declaration only)
  $ CONTROLS              UNITS "KIP" "FT" "F", TITLE2, PREFERENCE MERGETOL
  $ STORIES - IN SEQUENCE FROM TOP   STORY "n" HEIGHT h [MASTERSTORY "Yes" | SIMILARTO "m"]; STORY "Base" ELEV 0
  $ GRIDS                 GRIDSYSTEM "G1" TYPE "CARTESIAN"; GRID "G1" LABEL DIR COORD VISIBLE BUBBLELOC
  $ MATERIAL PROPERTIES   MATERIAL TYPE/GRADE/WEIGHTPERVOLUME; SYMTYPE/E/U/A; FY/FU/FYE/FUE (kip, ft)
  $ FRAME SECTIONS        FRAMESECTION "W18X40" MATERIAL "A992Fy50" SHAPE "W18X40" [FILE "AISC16"]
  $ POINT COORDINATES     POINT "label" x y   (plan coordinates; the story comes from the line/assign)
  $ LINE CONNECTIVITIES   LINE "C1" COLUMN "p" "p" 1 | LINE "B1" BEAM "pi" "pj" 0 | LINE "D1" BRACE "pi" "pj" 1
  $ POINT ASSIGNS         POINTASSIGN "p" "Base" RESTRAINT "UX UY UZ [RX RY RZ]"
  $ LINE ASSIGNS          LINEASSIGN "label" "story" SECTION "s" [ANG 90] [RELEASE "PINNED"] MINNUMSTA ...
  $ LOAD PATTERNS         LOADPATTERN "n" TYPE "t" SELFWEIGHT k; SEISMIC "EQX" "User Coefficient" ...
  $ LOAD CASES            LOADCASE "n" TYPE "Linear Static" INITCOND "PRESET"; LOADCASE "n" LOADPAT "p" SF 1
  $ LOAD COMBINATIONS     COMBO "n" TYPE "Linear Add"; COMBO "n" DESIGN "Steel" COMBOTYPE "Strength";
                          COMBO "n" LOADCASE "c" SF f
  END / $ END OF MODEL FILE

Not written: area objects, diaphragms, frame/area loads (gravity and wind story forces are NOT
applied; EQX/EQY carry the ELF Cs and k through SEISMIC "User Coefficient"), mass source,
design preferences. Inferred, not seen in a public example: the BRACE connectivity line (the
trailing integer read as for COLUMN: the I-end is that many stories below the J-end story),
the load pattern TYPE strings "Superimposed Dead" and "Roof Live" (ETABS UI names), and units of
KIP-FT for the whole file (the examples use KIP-IN and N-MM).
"""
from __future__ import annotations

import shlex

PROGRAM_VERSION = "23.1.1"     # the version string of the newest public export used as reference


def _f(x: float) -> str:
    s = f"{float(x):.6f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def _q(s: str) -> str:
    if '"' in s:
        raise ValueError(f"e2k names cannot contain double quotes: {s!r}")
    return f'"{s}"'


def write_e2k(objs, path: str, title: str = "calc-graph model", note: str = "") -> dict:
    """Write the objects of one adapter build (etabs.build_objects) as an .e2k text model."""
    by = {}
    for o in objs:
        by.setdefault(o.kind, []).append(o)
    L: list[str] = []
    add = L.append
    add("$ File written by the calc-graph prototype e2k writer - NOT exported, saved or opened by ETABS")
    if note:
        add(f"$ {note}")
    add(" ")
    add("$ PROGRAM INFORMATION")
    add(f'  PROGRAM  "ETABS"  VERSION {_q(PROGRAM_VERSION)}  ')
    add("")
    add("$ CONTROLS")
    add('  UNITS  "KIP"  "FT"  "F"  ')
    add(f"  TITLE2  {_q(title)}  ")
    add("  PREFERENCE  MERGETOL 0.01")
    add("")
    add("$ STORIES - IN SEQUENCE FROM TOP")
    sts = sorted(by.get("story", []), key=lambda o: -o.props["elevation_ft"])
    master = sts[0].label if sts else None
    for o in sts:
        if o.label == "Base":
            add(f'  STORY "Base"  ELEV {_f(o.props["elevation_ft"])} ')
        elif o.label == master:
            add(f'  STORY {_q(o.label)}  HEIGHT {_f(o.props["height_ft"])} MASTERSTORY "Yes"  ')
        else:
            add(f'  STORY {_q(o.label)}  HEIGHT {_f(o.props["height_ft"])} SIMILARTO {_q(master)}  ')
    add("")
    add("$ GRIDS")
    add('  GRIDSYSTEM "G1"  TYPE "CARTESIAN"  BUBBLESIZE 5 ')
    for o in by.get("grid", []):
        loc = "End" if o.props["dir"] == "X" else "Start"
        add(f'  GRID "G1"  LABEL {_q(o.label)}  DIR "{o.props["dir"]}"  COORD {_f(o.props["coord_ft"])} VISIBLE "Yes"  BUBBLELOC "{loc}"  ')
    add("")
    add("$ MATERIAL PROPERTIES")
    for o in by.get("material", []):
        p = o.props
        add(f'  MATERIAL  {_q(o.label)}    TYPE "Steel"    GRADE {_q(p["grade"])}    WEIGHTPERVOLUME {_f(p["weight_kcf"])}')
        add(f'  MATERIAL  {_q(o.label)}    SYMTYPE "Isotropic"  E {_f(p["E_ksi"] * 144)}  U {_f(p["nu"])}  A {p["alpha_per_F"]:.1E}')
        add(f'  MATERIAL  {_q(o.label)}  FY {_f(p["Fy_ksi"] * 144)}  FU {_f(p["Fu_ksi"] * 144)} FYE {_f(p["Fye_ksi"] * 144)}  FUE {_f(p["Fue_ksi"] * 144)}')
    add("")
    add("$ FRAME SECTIONS")
    for i, o in enumerate(by.get("section", [])):
        tail = f'  FILE {_q(o.props["library"])}' if i == 0 else ""
        add(f'  FRAMESECTION  {_q(o.label)}  MATERIAL {_q(o.props["material"])}  SHAPE {_q(o.props["shape"])}{tail}  ')
    add("")
    add("$ POINT COORDINATES")
    pts = {}
    for o in by.get("point", []):
        pts.setdefault(o.label, (o.props["x_ft"], o.props["y_ft"]))
    for lab in sorted(pts, key=int):
        add(f'  POINT {_q(lab)}  {_f(pts[lab][0])} {_f(pts[lab][1])} ')
    add("")
    add("$ LINE CONNECTIVITIES")
    lines: dict[str, tuple] = {}
    for o in by.get("frame", []):
        p = o.props
        conn = (p["etabs_type"], p["point_i"], p["point_j"], p["stories_below_i"])
        if lines.setdefault(o.label, conn) != conn:
            raise ValueError(f"frame label {o.label} has different connectivity on different stories: "
                             f"{lines[o.label]} vs {conn} ({o.element_id} @ {o.story})")
    for lab, (t, pi, pj, n) in lines.items():
        add(f'  LINE  {_q(lab)}  {t}  {_q(pi)}  {_q(pj)}  {n}')
    add("")
    add("$ POINT ASSIGNS")
    for o in by.get("point", []):
        if o.story == "Base" and any(o.props["restraint"]):
            dofs = [d for d, r in zip(("UX", "UY", "UZ", "RX", "RY", "RZ"), o.props["restraint"]) if r]
            add(f'  POINTASSIGN  {_q(o.label)}  "Base"  RESTRAINT "{" ".join(dofs)}"  ')
    add("")
    add("$ LINE ASSIGNS")
    for o in by.get("frame", []):
        p = o.props
        s = f'  LINEASSIGN  {_q(o.label)}  {_q(o.story)}  SECTION {_q(p["section"])}  '
        if p.get("angle_deg"):
            s += f'ANG  {_f(p["angle_deg"])} '
        if p.get("release"):
            s += f'RELEASE {_q(p["release"])}  '
        s += 'MINNUMSTA 3 AUTOMESH "YES"  MESHATINTERSECTIONS "YES"  '
        add(s)
    add("")
    add("$ LOAD PATTERNS")
    pats = by.get("load_pattern", [])
    for o in pats:
        add(f'  LOADPATTERN {_q(o.label)}  TYPE  {_q(o.props["type"])}  SELFWEIGHT  {_f(o.props["self_weight"])}')
    top = sts[0].label if sts else "Story1"
    for o in pats:
        p = o.props
        if p.get("method") == "User Coefficient":
            d = p["dir"]
            add(f'  SEISMIC {_q(o.label)}  "User Coefficient"    DIR "{d} {d}+ECC {d}-ECC"  ECC {_f(p["ecc"])}  '
                f'TOPSTORY {_q(top)}    BOTTOMSTORY "Base"    SHEARCOEFF {_f(p["shear_coeff"])}  HEIGHTEXPONENT {_f(p["height_exponent"])}')
    add("")
    add("$ LOAD CASES")
    for o in by.get("load_case", []):
        p = o.props
        if p["type"].startswith("Modal"):
            add(f'  LOADCASE {_q(o.label)}  TYPE  "Modal - Eigen"  INITCOND  "PRESET"  ')
            add(f'  LOADCASE {_q(o.label)}  MAXMODES  {p.get("max_modes", 12)} MINMODES  1 EIGENSHIFTFREQ  0 EIGENCUTOFF  0 EIGENTOL  1E-09 ')
            continue
        add(f'  LOADCASE {_q(o.label)}  TYPE  "Linear Static"  INITCOND  "PRESET"  ')
        for pat, sf in p["loads"]:
            add(f'  LOADCASE {_q(o.label)}  LOADPAT  {_q(pat)}  SF  {_f(sf)} ')
    add("")
    add("$ LOAD COMBINATIONS")
    for o in by.get("combo", []):
        p = o.props
        add(f'  COMBO {_q(o.label)}  TYPE "Linear Add"  ')
        add(f'  COMBO {_q(o.label)}  DESIGN "{p["design"]}"  COMBOTYPE "{p["combo_type"]}"  ')
        for case, sf in p["terms"]:
            add(f'  COMBO {_q(o.label)}  LOADCASE {_q(case)}  SF {_f(sf)} ')
    add("")
    add("  END")
    add("$ END OF MODEL FILE")
    text = "\n".join(L) + "\n"
    with open(path, "w", newline="\r\n") as fh:      # ETABS exports use CRLF line ends
        fh.write(text)
    return {"lines": len(L), "points": len(pts), "line_labels": len(lines), "frames": len(by.get("frame", [])),
            "sections": len(by.get("section", [])), "combos": len(by.get("combo", []))}


# ------------------------------------------------------------------ reader
def _num(s: str):
    try:
        return float(s)
    except ValueError:
        return s


def _kv(tokens: list[str]) -> dict:
    out = {}
    i = 0
    while i + 1 < len(tokens):
        out[tokens[i].upper()] = _num(tokens[i + 1])
        i += 2
    return out


def read_e2k(path: str) -> dict:
    """Parse the .e2k subset above. Unknown sections and keywords are skipped, so a real ETABS
    export of the same subset parses too. Units are returned, not converted."""
    m = {"program": None, "units": None, "title": None, "stories": [], "grids": [], "materials": {}, "sections": {},
         "points": {}, "lines": {}, "point_assigns": [], "line_assigns": [], "load_patterns": {}, "seismic": {},
         "load_cases": {}, "combos": {}, "skipped_sections": []}
    section = None
    with open(path, encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            line = raw.strip()
            if not line:
                continue
            if line.startswith("$"):
                section = line[1:].strip().upper()
                known = ("PROGRAM INFORMATION", "CONTROLS", "STORIES", "GRIDS", "MATERIAL PROPERTIES", "FRAME SECTIONS",
                         "POINT COORDINATES", "LINE CONNECTIVITIES", "POINT ASSIGNS", "LINE ASSIGNS", "LOAD PATTERNS",
                         "LOAD CASES", "LOAD COMBINATIONS", "END OF MODEL FILE", "FILE ")
                if not section.startswith(known) and section not in m["skipped_sections"]:
                    m["skipped_sections"].append(section)
                continue
            try:
                t = shlex.split(line, posix=True)
            except ValueError:
                continue
            if not t:
                continue
            kw = t[0].upper()
            if kw == "PROGRAM":
                m["program"] = {"name": t[1], **_kv(t[2:])}
            elif kw == "UNITS" and m["units"] is None:
                m["units"] = t[1:4]
            elif kw == "TITLE2":
                m["title"] = t[1]
            elif kw == "STORY":
                m["stories"].append({"name": t[1], **_kv(t[2:])})
            elif kw == "GRID":
                kv = _kv(t[2:])
                lab = t[t.index("LABEL") + 1] if "LABEL" in t else None     # keep "1" a string
                m["grids"].append({"system": t[1], "label": lab, "dir": kv.get("DIR"), "coord": kv.get("COORD")})
            elif kw == "MATERIAL":
                m["materials"].setdefault(t[1], {}).update(_kv(t[2:]))
            elif kw == "FRAMESECTION":
                m["sections"].setdefault(t[1], {}).update(_kv(t[2:]))
            elif kw == "POINT" and section == "POINT COORDINATES":
                m["points"][t[1]] = tuple(float(v) for v in t[2:])
            elif kw == "LINE" and section == "LINE CONNECTIVITIES":
                m["lines"][t[1]] = {"type": t[2].upper(), "pi": t[3], "pj": t[4], "n": int(float(t[5])) if len(t) > 5 else 0}
            elif kw == "POINTASSIGN":
                m["point_assigns"].append({"label": t[1], "story": t[2], **_kv(t[3:])})
            elif kw == "LINEASSIGN":
                kv = _kv(t[3:])
                m["line_assigns"].append({"label": t[1], "story": t[2], "section": kv.get("SECTION"),
                                          "release": kv.get("RELEASE", ""), "ang": kv.get("ANG", 0.0), **kv})
            elif kw == "LOADPATTERN":
                m["load_patterns"][t[1]] = _kv(t[2:])
            elif kw == "SEISMIC":
                m["seismic"][t[1]] = {"method": t[2], **_kv(t[3:])}
            elif kw == "LOADCASE":
                lc = m["load_cases"].setdefault(t[1], {"loads": []})
                kv = _kv(t[2:])
                if "LOADPAT" in kv:
                    lc["loads"].append((kv["LOADPAT"], kv.get("SF", 1.0)))
                else:
                    lc.update(kv)
            elif kw == "COMBO":
                cb = m["combos"].setdefault(t[1], {"terms": []})
                kv = _kv(t[2:])
                for k in ("LOADCASE", "LOADCOMBO", "LOAD"):
                    if k in kv:
                        cb["terms"].append((kv[k], kv.get("SF", 1.0), k))
                        break
                else:
                    cb.update(kv)
    return m


def story_elevations(parsed: dict) -> dict[str, float]:
    """Story name -> elevation from the STORIES block (listed top first, Base with ELEV)."""
    sts = parsed["stories"]
    base = next((s for s in sts if "ELEV" in s), {"name": "Base", "ELEV": 0.0})
    elev = {base["name"]: float(base["ELEV"])}
    z = elev[base["name"]]
    for s in reversed([s for s in sts if "ELEV" not in s]):
        z += float(s["HEIGHT"])
        elev[s["name"]] = z
    return elev


def frame_segments(parsed: dict) -> list[dict]:
    """One segment per LINEASSIGN: {label, story, type, section, release, i: (x,y,z), j: (x,y,z)}.
    The J end sits at the assigned story; the I end `n` stories below (COLUMN / BRACE)."""
    elev = story_elevations(parsed)
    order = sorted(elev, key=elev.get)
    out = []
    for a in parsed["line_assigns"]:
        ln = parsed["lines"].get(a["label"])
        if not ln:
            continue
        sj = a["story"]
        si = order[order.index(sj) - ln["n"]] if ln["n"] else sj
        pi, pj = parsed["points"][ln["pi"]], parsed["points"][ln["pj"]]
        out.append({"label": a["label"], "story": sj, "type": ln["type"], "section": a["section"], "release": a["release"],
                    "i": (pi[0], pi[1], elev[si]), "j": (pj[0], pj[1], elev[sj])})
    return out
