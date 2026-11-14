"""ETABS text model (.e2k) writer and reader for the analysis adapters.

The writer emits the ETABS .e2k keyword syntax for a SUBSET of the format; the reader parses
that subset back (and tolerates the extra sections/keywords real ETABS exports carry by
ignoring them). Files written here are not exported by ETABS: the header says so.

Syntax sources (public examples, read 2026-11-14; only the keyword syntax is used, no text copied):
- Karamba3D manual, "Export model to ETABS .e2k": POINT / LINE ... COLUMN "2" "2" 1 and the
  STORIES - IN SEQUENCE FROM TOP block, file parsed top to bottom
  https://manual.karamba3d.com/3-in-depth-component-reference/3.7-export/3.8.5-export-model-to-etabs-.e2k
- ETABS 20.1.0 export (public GitHub: udaytharu/Aman-portfolio-website, resources/ETABS/Loads/):
  CONTROLS, STORY, GRIDSYSTEM / GRID, MATERIAL, POINT, LINE COLUMN|BEAM, POINTASSIGN RESTRAINT,
  LINEASSIGN, DIAPHRAGM "D1" TYPE RIGID, AREA ... FLOOR 4, AREAASSIGN ... DIAPH, LOADPATTERN,
  SEISMIC "User Coefficient" DIR "X X+ECC X-ECC" ECC, LINELOAD / AREALOAD TYPE "UNIFF" DIR "GRAV",
  MASSSOURCE / MASSSOURCELOAD, LOADCASE, COMBO ... LOADCASE ... SF.
- ETABS 23.1.1 export (public GitHub: thomasjlittle/keepTABS, frontend/demo_viewer/models/
  Hack_v06.e2k): UNITS "KIP" "IN" "F", FRAMESECTION ... SHAPE ... FILE "AISC16", MATERIAL TYPE
  "Concrete" ... FC, SHELLPROP PROPTYPE "Slab" MODELINGTYPE "Membrane", COMBO TYPE "Linear Add".
- ETABS 21.0.1 file (same repo, fixtures/demo/after.e2k): LOADPATTERN TYPE "Super Dead",
  POINTLOAD ... TYPE "FORCE" LC ... FX FY FZ, POINTASSIGN ... DIAPH "D1", COMBO TYPE "Envelope"
  with LOADCOMBO terms, AREAASSIGN ... DIAPH ... OBJMESHTYPE "DEFAULT".
- ETABS 2016 export (public GitHub: skyran1278/thesis, Models/): MASSSOURCE INCLUDEELEMENTS "No"
  INCLUDEADDEDMASS "No" INCLUDELOADS "Yes"; LOADPATTERN TYPE "Other"; COMBO ... LOADCOMBO.
- ETABS 20 concrete material with WEIGHTPERVOLUME 0 (Hack_v06.e2k "6Ksi").
- Seen on the real ETABS 23.3.2 import of the previous file (2026-11-14): TYPE "Superimposed
  Dead" is read as "Other"; no diaphragm assignment leaves the gravity framing untied.

Subset written (in this order):
  $ PROGRAM INFORMATION   PROGRAM "ETABS" VERSION  (target-format declaration only)
  $ CONTROLS              UNITS "KIP" "FT" "F" (every number in the file is kip, ft, deg F), TITLE2, MERGETOL
  $ STORIES - IN SEQUENCE FROM TOP
  $ GRIDS
  $ DIAPHRAGM NAMES       DIAPHRAGM "D1" TYPE RIGID
  $ MATERIAL PROPERTIES   steel (A992Fy50 / A500GrC) + the zero-weight deck concrete
  $ FRAME SECTIONS        AISC16 library shapes by name
  $ SLAB PROPERTIES       SHELLPROP ... PROPTYPE "Slab" MODELINGTYPE "Membrane" (one per deck level)
  $ POINT COORDINATES
  $ LINE CONNECTIVITIES   LINE "C1" COLUMN | BEAM | BRACE
  $ AREA CONNECTIVITIES   AREA "F1" FLOOR 4 "p" "p" "p" "p" 0 0 0 0
  $ POINT ASSIGNS         RESTRAINT at Base; DIAPH "D1" on every point above Base
  $ LINE ASSIGNS
  $ AREA ASSIGNS          SECTION, DIAPH "D1", OBJMESHTYPE "DEFAULT"
  $ LOAD PATTERNS         LOADPATTERN; SEISMIC "User Coefficient" one eccentricity per pattern
                          (EQX+ecc DIR "X+ECC", EQX-ecc DIR "X-ECC"); the mass-only pattern
  $ POINT OBJECT LOADS    POINTLOAD (wind story forces)
  $ FRAME OBJECT LOADS    LINELOAD TYPE "UNIFF" DIR "GRAV" (perimeter walls)
  $ SHELL OBJECT LOADS    AREALOAD TYPE "UNIFF" DIR "GRAV" (area D, L, Lr, seismic allowances)
  $ MASS SOURCE           loads only (SDL + the mass-only pattern), lateral, lumped at stories
  $ LOAD CASES            Modal; one linear static case per pattern (EQX -> EQX+ecc, EQX-ecc)
  $ LOAD COMBINATIONS     "EQX" / "EQY" = Envelope of the +/-ecc cases; the design combos take
                          them as LOADCOMBO terms, every other term as LOADCASE
  END / $ END OF MODEL FILE

Accidental eccentricity: the design envelopes +/-5% torsion (synth.v2.lateral.distribute). One
pattern with DIR "X X+ECC X-ECC" makes ETABS build a multi-step case whose steps a combo treats
in a way we have not seen; so each eccentricity is its own pattern + case, and the case name the
design combos use ("EQX") becomes an Envelope combo of the two - a design combo that adds it
gets the worse of +/-ecc per result, as the design does.

Not written: design preferences, live load reduction, P-delta, auto wind. Inferred, not seen in
a public example: the BRACE connectivity line (trailing integer as for COLUMN) and a single
eccentric direction DIR "X+ECC" (the token as it appears inside the multi-direction list).
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


def ecc_patterns(objs) -> dict[str, list[tuple[str, str]]]:
    """{design seismic pattern: [(ETABS pattern / case name, DIR token), ...]} for every User
    Coefficient pattern with an accidental eccentricity: EQX -> [("EQX+ecc", "X+ECC"), ("EQX-ecc", "X-ECC")]."""
    out = {}
    for o in objs:
        p = o.props
        if o.kind == "load_pattern" and p.get("method") == "User Coefficient" and p.get("ecc"):
            d = p["dir"]
            out[o.label] = [(f"{o.label}+ecc", f"{d}+ECC"), (f"{o.label}-ecc", f"{d}-ECC")]
    return out


def etabs_load_names(objs) -> dict[str, list[str]]:
    """The load pattern, load case and combo names write_e2k emits for `objs` (the one place the
    eccentricity split and the mass-only patterns are expanded; roundtrip counts use it too)."""
    ecc = ecc_patterns(objs)
    pats, cases, combos = [], [], []
    for o in objs:
        if o.kind == "load_pattern":
            pats += [n for n, _ in ecc[o.label]] if o.label in ecc else [o.label]
        elif o.kind == "mass_source":
            pats += [x["name"] for x in o.props.get("extra_patterns", [])]
        elif o.kind == "load_case":
            cases += [n for n, _ in ecc[o.label]] if o.label in ecc else [o.label]
        elif o.kind == "combo":
            combos.append(o.label)
    return {"patterns": pats, "cases": cases, "combos": list(ecc) + combos}


def write_e2k(objs, path: str, title: str = "calc-graph model", note: str = "") -> dict:
    """Write the objects of one adapter build (etabs.build_objects) as an .e2k text model."""
    by = {}
    for o in objs:
        by.setdefault(o.kind, []).append(o)
    ecc = ecc_patterns(objs)
    L: list[str] = []
    add = L.append
    add("$ File written by the calc-graph prototype e2k writer - not exported or saved by ETABS")
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
    add("$ DIAPHRAGM NAMES")
    for o in by.get("diaphragm", []):
        add(f'  DIAPHRAGM {_q(o.label)}    TYPE {o.props["type"]}')
    add("")
    add("$ MATERIAL PROPERTIES")
    for o in by.get("material", []):
        p = o.props
        add(f'  MATERIAL  {_q(o.label)}    TYPE "Steel"    GRADE {_q(p["grade"])}    WEIGHTPERVOLUME {_f(p["weight_kcf"])}')
        add(f'  MATERIAL  {_q(o.label)}    SYMTYPE "Isotropic"  E {_f(p["E_ksi"] * 144)}  U {_f(p["nu"])}  A {p["alpha_per_F"]:.1E}')
        add(f'  MATERIAL  {_q(o.label)}  FY {_f(p["Fy_ksi"] * 144)}  FU {_f(p["Fu_ksi"] * 144)} FYE {_f(p["Fye_ksi"] * 144)}  FUE {_f(p["Fue_ksi"] * 144)}')
    seen = set()
    for o in by.get("shell_prop", []):
        m = o.props["material_props"]
        if m["name"] in seen:
            continue
        seen.add(m["name"])
        add(f'  MATERIAL  {_q(m["name"])}    TYPE {_q(m["type"])}    GRADE {_q(m["grade"])}    WEIGHTPERVOLUME {_f(m["weight_kcf"])}')
        add(f'  MATERIAL  {_q(m["name"])}    SYMTYPE "Isotropic"  E {_f(m["E_ksi"] * 144)}  U {_f(m["nu"])}  A {m["alpha_per_F"]:.1E}')
        add(f'  MATERIAL  {_q(m["name"])}    FC {_f(m["fc_ksi"] * 144)}')
    add("")
    add("$ FRAME SECTIONS")
    for i, o in enumerate(by.get("section", [])):
        tail = f'  FILE {_q(o.props["library"])}' if i == 0 else ""
        add(f'  FRAMESECTION  {_q(o.label)}  MATERIAL {_q(o.props["material"])}  SHAPE {_q(o.props["shape"])}{tail}  ')
    add("")
    add("$ SLAB PROPERTIES")
    for o in by.get("shell_prop", []):
        p = o.props
        add(f'  SHELLPROP  {_q(o.label)}  PROPTYPE  {_q(p["prop_type"])}  MATERIAL {_q(p["material"])}  '
            f'MODELINGTYPE {_q(p["modeling"])}  SLABTYPE {_q(p["slab_type"])}  SLABTHICKNESS {_f(p["thickness_ft"])} ')
    add("")
    add("$ POINT COORDINATES")
    pts = {}
    for o in by.get("point", []):
        pts.setdefault(o.label, (o.props["x_ft"], o.props["y_ft"]))
    for o in by.get("area", []):                 # corners that frame nothing (a moved column's old grid point)
        for lab, xy in zip(o.props["points"], o.props["xy"]):
            pts.setdefault(lab, tuple(xy))
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
    add("$ AREA CONNECTIVITIES")
    areas: dict[str, tuple] = {}
    for o in by.get("area", []):
        conn = tuple(o.props["points"])
        if areas.setdefault(o.label, conn) != conn:
            raise ValueError(f"area label {o.label} has different corners on different stories")
    for lab, conn in areas.items():
        add(f'  AREA {_q(lab)}  FLOOR  {len(conn)}  ' + "  ".join(_q(c) for c in conn) + "  " + "  ".join("0" * len(conn)) + "  ")
    add("")
    add("$ POINT ASSIGNS")
    for o in by.get("point", []):
        s = ""
        if o.story == "Base" and any(o.props["restraint"]):
            dofs = [d for d, r in zip(("UX", "UY", "UZ", "RX", "RY", "RZ"), o.props["restraint"]) if r]
            s += f'RESTRAINT "{" ".join(dofs)}"  '
        if o.props.get("diaphragm"):
            s += f'DIAPH {_q(o.props["diaphragm"])}  '
        if s:
            add(f'  POINTASSIGN  {_q(o.label)}  {_q(o.story)}  {s}')
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
    add("$ AREA ASSIGNS")
    for o in by.get("area", []):
        p = o.props
        add(f'  AREAASSIGN  {_q(o.label)}  {_q(o.story)}  SECTION {_q(p["section"])}  DIAPH {_q(p["diaphragm"])}  '
            f'OBJMESHTYPE {_q(p["mesh"])}  ')
    add("")
    add("$ LOAD PATTERNS")
    pats = by.get("load_pattern", [])
    for o in pats:
        for name, _ in ecc.get(o.label, [(o.label, None)]):
            add(f'  LOADPATTERN {_q(name)}  TYPE  {_q(o.props["type"])}  SELFWEIGHT  {_f(o.props["self_weight"])}')
    for ms in by.get("mass_source", []):
        for x in ms.props.get("extra_patterns", []):
            add(f'  LOADPATTERN {_q(x["name"])}  TYPE  {_q(x["type"])}  SELFWEIGHT  {_f(x["self_weight"])}')
    top = sts[0].label if sts else "Story1"
    for o in pats:
        p = o.props
        if p.get("method") != "User Coefficient":
            continue
        for name, d in ecc.get(o.label, [(o.label, p["dir"])]):
            add(f'  SEISMIC {_q(name)}  "User Coefficient"    DIR "{d}"  ECC {_f(p.get("ecc", 0))}  '
                f'TOPSTORY {_q(top)}    BOTTOMSTORY "Base"    SHEARCOEFF {_f(p["shear_coeff"])}  HEIGHTEXPONENT {_f(p["height_exponent"])}')
    add("")
    add("$ POINT OBJECT LOADS")
    for o in by.get("point", []):
        for pat, (fx, fy, fz) in (o.props.get("point_loads") or {}).items():
            add(f'  POINTLOAD  {_q(o.label)}  {_q(o.story)}  TYPE "FORCE"  LC {_q(pat)}  FX {_f(fx)}  FY {_f(fy)}  FZ {_f(fz)}')
    add("")
    add("$ FRAME OBJECT LOADS")
    for o in by.get("frame", []):
        for pat, w in (o.props.get("line_loads") or {}).items():
            add(f'  LINELOAD  {_q(o.label)}  {_q(o.story)}  TYPE "UNIFF"  DIR "GRAV"  LC {_q(pat)}  FVAL {_f(w)}')
    add("")
    add("$ SHELL OBJECT LOADS")
    for o in by.get("area", []):
        for pat, w in o.props.get("loads_ksf", {}).items():
            add(f'  AREALOAD  {_q(o.label)}  {_q(o.story)}  TYPE "UNIFF"  DIR "GRAV"  LC {_q(pat)}  FVAL {_f(w)}')
    add("")
    add("$ MASS SOURCE")
    yn = lambda b: '"Yes"' if b else '"No"'   # noqa: E731
    for ms in by.get("mass_source", []):
        p = ms.props
        add(f'  MASSSOURCE  {_q(ms.label)}    INCLUDEELEMENTS {yn(p["include_elements"])}    INCLUDEADDEDMASS '
            f'{yn(p["include_added_mass"])}    INCLUDELOADS {yn(p["include_loads"])}    INCLUDEMOVE "No"    '
            f'INCLUDELATERALMASS "Yes"    INCLUDEVERTICALMASS {yn(not p["lateral_only"])}    LUMPATSTORIES '
            f'{yn(p["lump_at_stories"])}    ISDEFAULT "Yes"  ')
        for pat, sf in p["loads"]:
            add(f'  MASSSOURCELOAD  {_q(ms.label)}  {_q(pat)}  {_f(sf)} ')
    add("")
    add("$ LOAD CASES")
    for o in by.get("load_case", []):
        p = o.props
        if p["type"].startswith("Modal"):
            add(f'  LOADCASE {_q(o.label)}  TYPE  "Modal - Eigen"  INITCOND  "PRESET"  ')
            add(f'  LOADCASE {_q(o.label)}  MAXMODES  {p.get("max_modes", 12)} MINMODES  1 EIGENSHIFTFREQ  0 EIGENCUTOFF  0 EIGENTOL  1E-09 ')
            continue
        if o.label in ecc:                       # a seismic case: one case per eccentricity
            if [pat for pat, _ in p["loads"]] != [o.label]:
                raise ValueError(f"seismic case {o.label} must load only its own pattern to be split by eccentricity")
            for name, _ in ecc[o.label]:
                add(f'  LOADCASE {_q(name)}  TYPE  "Linear Static"  INITCOND  "PRESET"  ')
                add(f'  LOADCASE {_q(name)}  LOADPAT  {_q(name)}  SF  {_f(p["loads"][0][1])} ')
            continue
        add(f'  LOADCASE {_q(o.label)}  TYPE  "Linear Static"  INITCOND  "PRESET"  ')
        for pat, sf in p["loads"]:
            add(f'  LOADCASE {_q(o.label)}  LOADPAT  {_q(pat)}  SF  {_f(sf)} ')
    add("")
    add("$ LOAD COMBINATIONS")
    for name, parts in ecc.items():              # "EQX" = the worse of +/- accidental eccentricity
        add(f'  COMBO {_q(name)}  TYPE "Envelope"  ')
        for case, _ in parts:
            add(f'  COMBO {_q(name)}  LOADCASE {_q(case)}  SF 1 ')
    for o in by.get("combo", []):
        p = o.props
        add(f'  COMBO {_q(o.label)}  TYPE "Linear Add"  ')
        add(f'  COMBO {_q(o.label)}  DESIGN "{p["design"]}"  COMBOTYPE "{p["combo_type"]}"  ')
        for case, sf in p["terms"]:
            kw = "LOADCOMBO" if case in ecc else "LOADCASE"
            add(f'  COMBO {_q(o.label)}  {kw} {_q(case)}  SF {_f(sf)} ')
    add("")
    add("  END")
    add("$ END OF MODEL FILE")
    text = "\n".join(L) + "\n"
    with open(path, "w", newline="\r\n") as fh:      # ETABS exports use CRLF line ends
        fh.write(text)
    names = etabs_load_names(objs)
    return {"lines": len(L), "points": len(pts), "line_labels": len(lines), "frames": len(by.get("frame", [])),
            "areas": len(by.get("area", [])), "area_labels": len(areas), "sections": len(by.get("section", [])),
            "load_patterns": len(names["patterns"]), "load_cases": len(names["cases"]), "combos": len(names["combos"])}


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
         "load_cases": {}, "combos": {}, "diaphragms": {}, "shell_props": {}, "areas": {}, "area_assigns": [],
         "point_loads": [], "line_loads": [], "area_loads": [], "mass_sources": {}, "skipped_sections": []}
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
                         "LOAD CASES", "LOAD COMBINATIONS", "END OF MODEL FILE", "FILE ", "DIAPHRAGM NAMES",
                         "SLAB PROPERTIES", "DECK PROPERTIES", "AREA CONNECTIVITIES", "AREA ASSIGNS",
                         "POINT OBJECT LOADS", "FRAME OBJECT LOADS", "SHELL OBJECT LOADS", "MASS SOURCE")
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
            elif kw == "DIAPHRAGM":
                m["diaphragms"][t[1]] = _kv(t[2:])
            elif kw == "SHELLPROP":
                m["shell_props"].setdefault(t[1], {}).update(_kv(t[2:]))
            elif kw == "AREA" and section == "AREA CONNECTIVITIES":
                n = int(float(t[3]))
                m["areas"][t[1]] = {"type": t[2].upper(), "points": t[4:4 + n]}
            elif kw == "AREAASSIGN":
                m["area_assigns"].append({"label": t[1], "story": t[2], **_kv(t[3:])})
            elif kw == "POINTLOAD":
                m["point_loads"].append({"label": t[1], "story": t[2], **_kv(t[3:])})
            elif kw == "LINELOAD":
                m["line_loads"].append({"label": t[1], "story": t[2], **_kv(t[3:])})
            elif kw == "AREALOAD":
                m["area_loads"].append({"label": t[1], "story": t[2], **_kv(t[3:])})
            elif kw == "MASSSOURCE":
                m["mass_sources"].setdefault(t[1], {"loads": []}).update(_kv(t[2:]))
            elif kw == "MASSSOURCELOAD":
                m["mass_sources"].setdefault(t[1], {"loads": []})["loads"].append((t[2], float(t[3])))
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


def _poly_area(xy: list[tuple[float, float]]) -> float:
    return abs(sum(xa * yb - xb * ya for (xa, ya), (xb, yb) in zip(xy, xy[1:] + xy[:1]))) / 2


def load_summary(parsed: dict, section_area_ft2) -> dict:
    """What ETABS will see as loads and mass in a parsed .e2k (units of the file; ours: kip, ft).

    section_area_ft2(shape name) -> cross-section area, so frame self weight = area x the
    material's WEIGHTPERVOLUME x length, as ETABS computes it. A column / brace segment's self
    weight is split half to each end story (how ETABS lumps it); beams and areas sit at their story.
    Returns {"vertical": {story: {pattern: kip down}}, "lateral": {pattern: {story: [FX, FY]}},
    "mass_weight": {story: kip} (the default mass source), "seismic": {pattern: {W, V, Fx}},
    "stories": [names bottom up], "areas_by_story": {story: n}, "diaphragm_points": {story: n}}."""
    elev = story_elevations(parsed)
    order = sorted(elev, key=elev.get)
    vert: dict[str, dict[str, float]] = {s: {} for s in order}
    lat: dict[str, dict[str, list[float]]] = {}
    selfw: dict[str, float] = {s: 0.0 for s in order}

    def addv(story, pat, v):
        vert[story][pat] = vert[story].get(pat, 0.0) + v

    sw_pats = {n: float(p.get("SELFWEIGHT", 0) or 0) for n, p in parsed["load_patterns"].items()}
    segs = frame_segments(parsed)
    seglen = {}
    for sg in segs:
        L = sum((a - b) ** 2 for a, b in zip(sg["i"], sg["j"])) ** 0.5
        seglen[(sg["label"], sg["story"])] = L
        sec = parsed["sections"].get(sg["section"], {})
        gam = float(parsed["materials"].get(sec.get("MATERIAL"), {}).get("WEIGHTPERVOLUME", 0) or 0)
        w = section_area_ft2(sec.get("SHAPE", sg["section"])) * gam * L
        zi, zj = sg["i"][2], sg["j"][2]
        si = next(s for s in order if abs(elev[s] - zi) < 1e-6)
        if si == sg["story"]:
            selfw[si] += w
        else:
            selfw[si] += w / 2
            selfw[sg["story"]] += w / 2
    area_xy = {lab: [parsed["points"][p][:2] for p in a["points"]] for lab, a in parsed["areas"].items()}
    area_ft2 = {lab: _poly_area(xy) for lab, xy in area_xy.items()}
    for a in parsed["area_assigns"]:
        sp = parsed["shell_props"].get(a.get("SECTION"), {})
        gam = float(parsed["materials"].get(sp.get("MATERIAL"), {}).get("WEIGHTPERVOLUME", 0) or 0)
        selfw[a["story"]] += gam * float(sp.get("SLABTHICKNESS", 0) or 0) * area_ft2[a["label"]]
    for pat, k in sw_pats.items():
        if k:
            for s in order:
                if selfw[s]:
                    addv(s, pat, k * selfw[s])
    for ld in parsed["area_loads"]:
        if str(ld.get("DIR", "GRAV")).upper() == "GRAV" and str(ld.get("TYPE", "UNIFF")).upper() == "UNIFF":
            addv(ld["story"], ld["LC"], float(ld["FVAL"]) * area_ft2[ld["label"]])
    for ld in parsed["line_loads"]:
        if str(ld.get("DIR", "GRAV")).upper() == "GRAV" and str(ld.get("TYPE", "UNIFF")).upper() == "UNIFF":
            addv(ld["story"], ld["LC"], float(ld["FVAL"]) * seglen[(ld["label"], ld["story"])])
    for ld in parsed["point_loads"]:
        fz = float(ld.get("FZ", 0) or 0)
        if fz:
            addv(ld["story"], ld["LC"], -fz)
        f = lat.setdefault(ld["LC"], {}).setdefault(ld["story"], [0.0, 0.0])
        f[0] += float(ld.get("FX", 0) or 0)
        f[1] += float(ld.get("FY", 0) or 0)
    ms = next((v for v in parsed["mass_sources"].values() if str(v.get("ISDEFAULT", "")).lower() == "yes"),
              next(iter(parsed["mass_sources"].values()), None))
    mass = {s: 0.0 for s in order}
    if ms is None or str(ms.get("INCLUDEELEMENTS", "Yes")).lower() == "yes":
        for s in order:
            mass[s] += selfw[s]
    if ms is not None and str(ms.get("INCLUDELOADS", "No")).lower() == "yes":
        for pat, sf in ms["loads"]:
            for s in order:
                mass[s] += sf * vert[s].get(pat, 0.0)
    seis = {}
    for name, sp in parsed["seismic"].items():
        if sp.get("method") != "User Coefficient":
            continue
        bot = sp.get("BOTTOMSTORY", order[0])
        top = sp.get("TOPSTORY", order[-1])
        lv = [s for s in order if elev[bot] < elev[s] <= elev[top]]
        W = sum(mass[s] for s in lv)
        V = float(sp["SHEARCOEFF"]) * W
        k = float(sp.get("HEIGHTEXPONENT", 1))
        den = sum(mass[s] * (elev[s] - elev[bot]) ** k for s in lv) or 1.0
        seis[name] = {"W": W, "V": V, "dir": sp.get("DIR"), "ecc": sp.get("ECC"),
                      "Fx": {s: V * mass[s] * (elev[s] - elev[bot]) ** k / den for s in lv}}
    dpts = {}
    for a in parsed["point_assigns"]:
        if a.get("DIAPH"):
            dpts[a["story"]] = dpts.get(a["story"], 0) + 1
    abys = {}
    for a in parsed["area_assigns"]:
        abys[a["story"]] = abys.get(a["story"], 0) + 1
    return {"vertical": vert, "lateral": lat, "self_weight": selfw, "mass_weight": mass, "seismic": seis,
            "stories": order, "areas_by_story": abys, "diaphragm_points": dpts}
