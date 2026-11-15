"""Harborview loading calcs: gravity, wind, seismic and load combinations (sheets S-001 to S-004).

They design no element. They feed other calcs, which cite them by sheet number ("Gravity loads per S-001");
the engine's calcdeps rule 3 (calc reference) turns each citation into a calc -> calc edge. The loading calcs
also cite each other: S-001 -> S-003 (seismic weight), S-001 / S-002 / S-003 -> S-004 (combinations).

Numbers come from the model: the floor plates (slab extents and heights) give floor areas, the building width
in each direction and the storey heights, so the rev 2 reissue (Rev B, the L06 vertical addition) carries one
more floor, a taller building, more seismic weight and larger storey forces. ASCE 7-22. Plausible, not a design.

Rules the text keeps: no element marks, no section sizes and no page numbers (they would make links or page
references); a sheet number is written only where the calc takes that calc's output as input, with no "to"
before it on the line (a "to" would reverse the edge); no calc-title keywords in a heading.
"""
from __future__ import annotations

from dataclasses import dataclass

from .model import Calc, Document, Model

FT = 3.28084
ASCE = "ASCE 7-22"


@dataclass(frozen=True)
class Spec:
    sheet: str
    family: str
    name: str
    summary: str


SPECS = [
    Spec("S-001", "gravity", "Gravity Load Criteria",
         "Dead, superimposed dead, live and snow loads; floor weights for the lateral system."),
    Spec("S-002", "wind", "Wind Load Analysis",
         "Directional procedure (MWFRS), Exposure D; storey forces in both plan directions."),
    Spec("S-003", "seismic", "Seismic Load Analysis",
         "Equivalent lateral force procedure, SDC C; base shear and its vertical distribution."),
    Spec("S-004", "combos", "Load Combination Criteria",
         "LRFD strength combinations; governing lateral storey shears for the lateral system."),
]
SHEET = {s.family: s.sheet for s in SPECS}
# rev 1 loading calcs come before every design calc; rev 2 reissues them ahead of the L06 design reissues
DATES = {"Rev A": "2026-09-10", "Rev B": "2026-11-03"}

# design calc families -> the loading sheets they take loads from (the lines are written in calc_pdf.basis)
CITES: dict[str, list[tuple[str, list[str]]]] = {
    "slab": [("Gravity loads per", ["gravity"]), ("Diaphragm forces per", ["seismic", "wind"])],
    "girder": [("Gravity loads per", ["gravity"])],
    "infill": [("Gravity loads per", ["gravity"])],
    "colstack": [("Axial loads (live load reduction per ASCE 7-22 4.7) per", ["gravity"])],
    "brace": [("Storey shears per", ["wind", "seismic"]), ("Strength combinations per", ["combos"])],
    "corewall": [("Storey shears per", ["wind", "seismic"]), ("Strength combinations per", ["combos"])],
    "baseplate": [("Uplift combinations (0.9D + 1.0E) per", ["combos"])],
    "pilecap": [("Strength combinations and overturning per", ["combos"])],
    "caisson": [("Strength combinations per", ["combos"])],
}


def calc_id(family: str) -> str:
    return f"load-{family}"


def documents(rev: int) -> list[Document]:
    """The four loading documents of a model revision: Rev A in rev 1, Rev B in rev 2 (the L06 addition)."""
    r = "Rev A" if rev == 1 else "Rev B"
    out = []
    for s in SPECS:
        title = f"{s.sheet} {s.name}"
        c = Calc(id=calc_id(s.family), doc=calc_id(s.family), title=title, family=s.family, cat="Loading", code=ASCE,
                 rev=r, date=DATES[r], summary=s.summary, elements=[])
        out.append(Document(key=calc_id(s.family), title=title, rev=r, date=DATES[r], calcs=[c]))
    return out


# ---------------------------------------------------------------- the building, from the model


@dataclass
class Floor:
    level: str
    z_ft: float       # height of the floor above grade
    area: float       # sq ft
    trib_ft: float    # storey height tributary to this floor (half above + half below; roof: half + parapet)
    roof: bool


class Building:
    def __init__(self, m: Model):
        slabs = sorted((e for e in m.elements if e.kind == "slab"), key=lambda e: e.geom["bbox"]["max"][2])
        self.floors: list[Floor] = []
        zs = [s.geom["bbox"]["max"][2] * FT for s in slabs]
        for k, s in enumerate(slabs):
            mn, mx = s.geom["bbox"]["min"], s.geom["bbox"]["max"]
            below = zs[k] - (zs[k - 1] if k else 0.0)
            above = zs[k + 1] - zs[k] if k + 1 < len(zs) else 0.0
            roof = k == len(slabs) - 1
            self.floors.append(Floor(s.storey, zs[k], (mx[0] - mn[0]) * (mx[1] - mn[1]) * FT * FT,
                                     below / 2 + (above / 2 if not roof else 3.0), roof))
        mn, mx = slabs[0].geom["bbox"]["min"], slabs[0].geom["bbox"]["max"]
        self.ew_ft = (mx[0] - mn[0]) * FT    # plan length along x (east-west)
        self.ns_ft = (mx[1] - mn[1]) * FT    # plan length along y (north-south)
        self.perimeter = 2 * (self.ew_ft + self.ns_ft)
        self.hn = self.floors[-1].z_ft

    # gravity (psf)
    SLAB, FRAMING, SDL, PARTITION, ROOF_SDL, MECH, CLADDING = 52.0, 10.0, 15.0, 10.0, 20.0, 15.0, 25.0
    LL_OFFICE, LL_PARTITION, LL_CORRIDOR, LL_LOBBY, LL_MECH, LR = 50.0, 15.0, 80.0, 100.0, 125.0, 20.0
    PG, CE, CT, IS = 25.0, 0.9, 1.0, 1.0

    def floor_dead_psf(self, f: Floor) -> float:
        return self.SLAB + self.FRAMING + (self.ROOF_SDL + self.MECH if f.roof else self.SDL + self.PARTITION)

    def weight_k(self, f: Floor) -> float:
        """Seismic weight of a floor (kips): floor dead load incl. the seismic partition allowance + cladding."""
        clad = self.CLADDING * self.perimeter * f.trib_ft
        return (self.floor_dead_psf(f) * f.area + clad) / 1000.0

    @property
    def snow_psf(self) -> float:
        return max(0.7 * self.CE * self.CT * self.IS * self.PG, 20.0 * self.IS)   # ASCE 7-22 7.3-1, min 7.3.4

    # wind
    V, KD, KZT, KE, G, ALPHA, ZG = 115.0, 0.85, 1.0, 1.0, 0.85, 11.5, 700.0

    def kz(self, z: float) -> float:
        return 2.41 * (max(z, 15.0) / self.ZG) ** (2 / self.ALPHA)   # ASCE 7-22 Table 26.10-1 note, Exposure D

    def qz(self, z: float) -> float:
        return 0.00256 * self.kz(z) * self.KZT * self.KE * self.V ** 2

    @staticmethod
    def cp_leeward(l_over_b: float) -> float:
        if l_over_b <= 1:
            return -0.5
        if l_over_b >= 4:
            return -0.2
        if l_over_b <= 2:
            return -0.5 + 0.2 * (l_over_b - 1)
        return -0.3 + 0.1 * (l_over_b - 2) / 2

    def wind_forces(self, width: float, depth: float) -> list[float]:
        """Storey forces (kips) for wind on a face `width` ft wide, the building `depth` ft deep along the wind."""
        qh = self.qz(self.hn)
        lee = abs(qh * self.KD * self.G * self.cp_leeward(depth / width))
        return [(self.qz(f.z_ft) * self.KD * self.G * 0.8 + lee) * f.trib_ft * width / 1000.0 for f in self.floors]

    # seismic
    SDS, SD1, R, OMEGA, CD, IE, CT_P, X = 0.40, 0.20, 3.25, 2.0, 3.25, 1.0, 0.02, 0.75

    @property
    def ta(self) -> float:
        return self.CT_P * self.hn ** self.X

    @property
    def cs(self) -> float:
        cs = self.SDS / (self.R / self.IE)
        return max(min(cs, self.SD1 / (self.ta * self.R / self.IE)), 0.044 * self.SDS * self.IE, 0.01)

    @property
    def k(self) -> float:
        t = self.ta
        return 1.0 if t <= 0.5 else 2.0 if t >= 2.5 else 1.0 + (t - 0.5) / 2.0

    def seismic_forces(self) -> tuple[float, float, list[float]]:
        w = [self.weight_k(f) for f in self.floors]
        v = self.cs * sum(w)
        wh = [wi * f.z_ft ** self.k for wi, f in zip(w, self.floors)]
        return sum(w), v, [v * x / sum(wh) for x in wh]


def storey_shears(forces: list[float]) -> list[float]:
    """Storey shear below each floor: the sum of the forces at and above it."""
    out, run = [], 0.0
    for f in reversed(forces):
        run += f
        out.append(run)
    return list(reversed(out))


# ---------------------------------------------------------------- the calc pages


def f0(x: float) -> str:
    return f"{x:,.0f}"


def f1(x: float) -> str:
    return f"{x:,.1f}"


def f2(x: float) -> str:
    return f"{x:.2f}"


def f3(x: float) -> str:
    return f"{x:.3f}"


def write(w, lay, calc: Calc):
    """Lay out a loading calc. `w` is the calc_pdf.Writer (basis(), cite_sheets(), the model)."""
    b = Building(w.m)
    {"gravity": gravity, "wind": wind, "seismic": seismic, "combos": combos}[calc.family](w, lay, calc, b)


def gravity(w, lay, calc: Calc, b: Building):
    w.basis(lay, calc, [f"Plan {f1(b.ew_ft)} ft (E-W) x {f1(b.ns_ft)} ft (N-S), {f0(b.floors[0].area)} sf per floor.",
                        f"{len(b.floors)} supported floors including the roof; roof height {f1(b.hn)} ft above grade.",
                        "Risk Category II. Live load reduction per ASCE 7-22 4.7 where the influence area allows."])
    lay.heading("2. Dead and superimposed dead loads (psf)")
    lay.table([200, 70, 70], ["Item", "Floor", "Roof"], [
        ["Composite slab, 6.25 in. total on 3 in. deck", f0(b.SLAB), f0(b.SLAB)],
        ["Structural steel allowance", f0(b.FRAMING), f0(b.FRAMING)],
        ["Ceiling, MEP, finishes (SDL)", f0(b.SDL), f0(b.ROOF_SDL)],
        ["Partitions (seismic weight allowance)", f0(b.PARTITION), "-"],
        ["Rooftop mechanical allowance", "-", f0(b.MECH)],
        ["Total", f0(b.floor_dead_psf(b.floors[0])), f0(b.floor_dead_psf(b.floors[-1]))],
    ])
    lay.line(f"Curtain wall cladding: {f0(b.CLADDING)} psf of wall area, perimeter {f1(b.perimeter)} ft.")
    lay.heading("3. Live loads (psf)")
    lay.table([200, 70, 90], ["Occupancy", "L", "Reducible"], [
        ["Office", f0(b.LL_OFFICE), "yes"],
        ["Partition allowance (office)", f0(b.LL_PARTITION), "no"],
        ["Corridors above the first floor", f0(b.LL_CORRIDOR), "yes"],
        ["Lobbies and the first floor corridors", f0(b.LL_LOBBY), "no"],
        ["Mechanical rooms", f0(b.LL_MECH), "no"],
        ["Roof (Lr)", f0(b.LR), "yes"],
    ])
    lay.heading("4. Snow")
    lay.line(f"pg = {f0(b.PG)} psf, Ce = {b.CE}, Ct = {b.CT}, Is = {b.IS}.")
    lay.line(f"pf = 0.7 Ce Ct Is pg = {f1(0.7 * b.CE * b.CT * b.IS * b.PG)} psf; minimum 20 Is psf: pf = {f1(b.snow_psf)} psf.")
    lay.line("Drift at the rooftop mechanical screen is taken by the roof members.")
    lay.heading("5. Floor weights for the lateral system")
    rows, tot = [], 0.0
    for f in b.floors:
        wk = b.weight_k(f)
        tot += wk
        rows.append([f.level + (" (roof)" if f.roof else ""), f1(f.z_ft), f0(f.area), f0(b.floor_dead_psf(f)),
                     f1(f.trib_ft), f0(wk)])
    rows.append(["Total", "", "", "", "", f0(tot)])
    lay.table([70, 56, 70, 60, 70, 64], ["Floor", "hx ft", "Area sf", "D psf", "Clad ht ft", "wx kips"], rows)
    lay.line("Floor weights above are the seismic weight W; they are carried forward with this sheet.")


def wind(w, lay, calc: Calc, b: Building):
    w.basis(lay, calc, [f"Basic wind speed V = {f0(b.V)} mph (Risk Category II); Exposure D (open water within 600 ft).",
                        f"Kd = {b.KD}, Kzt = {b.KZT}, Ke = {b.KE}, gust effect G = {b.G} (rigid: Ta below 1 s).",
                        "Main wind force resisting system, directional procedure (Ch. 27), enclosed building."])
    lay.heading("2. Velocity pressure")
    rows = [[f.level + (" (roof)" if f.roof else ""), f1(f.z_ft), f3(b.kz(f.z_ft)), f1(b.qz(f.z_ft))] for f in b.floors]
    lay.table([80, 60, 60, 70], ["Floor", "z ft", "Kz", "qz psf"], rows)
    lay.line(f"qh = {f1(b.qz(b.hn))} psf at the roof, h = {f1(b.hn)} ft.")
    for name, width, depth in (("N-S", b.ew_ft, b.ns_ft), ("E-W", b.ns_ft, b.ew_ft)):
        lay.heading(f"{'3' if name == 'N-S' else '4'}. Wind {name}: face {f1(width)} ft, L/B = {f2(depth / width)}")
        lay.line(f"Cp windward 0.80, leeward {f2(b.cp_leeward(depth / width))}; internal pressures cancel on the MWFRS.")
        fx = b.wind_forces(width, depth)
        vx = storey_shears(fx)
        rows = [[f.level + (" (roof)" if f.roof else ""), f1(f.trib_ft), f1(fi), f1(vi)] for f, fi, vi in zip(b.floors, fx, vx)]
        lay.table([80, 70, 70, 80], ["Floor", "Trib ht ft", "Fx kips", "Storey V kips"], rows)
        lay.line(f"Base shear {name}: {f1(vx[0])} kips; overturning moment {f0(sum(fi * f.z_ft for fi, f in zip(fx, b.floors)))} k-ft.")


def seismic(w, lay, calc: Calc, b: Building):
    w.basis(lay, calc, ["Risk Category II, Ie = 1.0; Site Class D (geotechnical report); SDC C.",
                        f"SDS = {f2(b.SDS)}, SD1 = {f2(b.SD1)}.",
                        "Steel ordinary concentrically braced frames with the concrete core:",
                        f"R = {b.R}, Omega0 = {b.OMEGA}, Cd = {b.CD}."])
    w.cite_sheets(lay, calc, "Seismic weight W from", ["gravity"])
    W, V, fx = b.seismic_forces()
    lay.heading("2. Period and base shear")
    lay.line(f"Ta = Ct hn^x = {b.CT_P} x {f1(b.hn)}^{b.X} = {f3(b.ta)} s (Ct = {b.CT_P}, x = {b.X}).")
    lay.line(f"Cs = SDS / (R / Ie) = {f3(b.SDS / b.R)}; upper limit SD1 / (T R / Ie) = {f3(b.SD1 / (b.ta * b.R))}; "
             f"lower limit {f3(0.044 * b.SDS)}.")
    lay.line(f"Cs = {f3(b.cs)}.   W = {f0(W)} kips.   V = Cs W = {f1(V)} kips.")
    lay.heading("3. Vertical distribution")
    lay.line(f"k = {f2(b.k)}; Fx = Cvx V, Cvx = wx hx^k / sum(wi hi^k).")
    vx = storey_shears(fx)
    rows = []
    for f, fi, vi in zip(b.floors, fx, vx):
        rows.append([f.level + (" (roof)" if f.roof else ""), f0(b.weight_k(f)), f1(f.z_ft), f3(fi / V), f1(fi), f1(vi)])
    lay.table([80, 60, 54, 54, 60, 74], ["Floor", "wx kips", "hx ft", "Cvx", "Fx kips", "Storey V kips"], rows)
    lay.heading("4. Diaphragm forces")
    for k, f in enumerate(b.floors):
        wpx = b.weight_k(f)
        ratio = sum(fx[k:]) / sum(b.weight_k(g) for g in b.floors[k:])   # 12.10-1: sum Fi / sum wi at and above
        fpx = min(max(ratio, 0.2 * b.SDS * b.IE), 0.4 * b.SDS * b.IE) * wpx
        lay.line(f"{f.level}: Fpx = {f1(fpx)} kips (bounded 0.2 SDS Ie wpx to 0.4 SDS Ie wpx).")
    lay.line(f"Redundancy rho = 1.0 (SDC C). Drift amplified by Cd = {b.CD}; allowable storey drift 0.020 hsx.")


def combos(w, lay, calc: Calc, b: Building):
    w.basis(lay, calc, ["Strength design (LRFD), ASCE 7-22 2.3.1 and 2.3.6; E = Eh + Ev, Ev = 0.2 SDS D."])
    w.cite_sheets(lay, calc, "Dead, live and snow loads from", ["gravity"])
    w.cite_sheets(lay, calc, "Wind storey forces from", ["wind"])
    w.cite_sheets(lay, calc, "Seismic storey forces from", ["seismic"])
    lay.heading("2. Strength combinations")
    ev = 0.2 * b.SDS
    lay.table([30, 330], ["No.", "Combination"], [
        ["1", "1.4D"],
        ["2", "1.2D + 1.6L + 0.5(Lr or S)"],
        ["3", "1.2D + 1.6(Lr or S) + (L or 0.5W)"],
        ["4", "1.2D + 1.0W + L + 0.5(Lr or S)"],
        ["5", f"(1.2 + {f2(ev)})D + 1.0Eh + L + 0.15S"],
        ["6", "0.9D + 1.0W"],
        ["7", f"(0.9 - {f2(ev)})D + 1.0Eh"],
        ["5o", f"(1.2 + {f2(ev)})D + {b.OMEGA}QE + L + 0.15S   (overstrength: collectors, brace connections)"],
    ])
    lay.heading("3. Governing lateral storey shears (kips)")
    ns = storey_shears(b.wind_forces(b.ew_ft, b.ns_ft))
    ew = storey_shears(b.wind_forces(b.ns_ft, b.ew_ft))
    _, _, fx = b.seismic_forces()
    eq = storey_shears(fx)
    rows = []
    for f, a, c, e in zip(b.floors, ns, ew, eq):
        gov = "Seismic" if e >= max(a, c) else "Wind"
        rows.append([f.level + (" (roof)" if f.roof else ""), f1(a), f1(c), f1(e), gov])
    lay.table([80, 70, 70, 70, 60], ["Below floor", "Wind N-S", "Wind E-W", "Seismic", "Governs"], rows)
    lay.line("Foundations: service combinations D + 0.75L + 0.75(0.6W) and 0.6D + 0.6W for bearing and uplift.")
