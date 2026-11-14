"""Units: every quantity in the schema carries its unit.

A tiny explicit layer instead of `pint`: the schema needs ~30 structural units and
dimension checking, and pint would add a dependency (plus lockfile churn) for that.
Each unit is a factor to SI base (m, N, rad) and a dimension vector (L, F, A).

Rules this module enforces (they raise, never coerce silently):
- an unknown unit string is rejected (`UnknownUnit`)
- converting or adding across dimensions is rejected (`UnitMismatch`), e.g. kip -> ft
- a `Quantity` always has a unit; a dimensionless value says so with unit "1"

`unit_from_key()` reads the unit a source declares in a field name or table header
("max_start_reaction_k", "length_ft", "PreDL[ksf]", "Magnitude[k,k-ft]") so adapters
never guess one.
"""
from __future__ import annotations

import math
import re
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict


class UnknownUnit(ValueError):
    pass


class UnitMismatch(ValueError):
    pass


# dimension vector: (length, force, angle)
Dim = tuple[int, int, int]
LENGTH: Dim = (1, 0, 0)
AREA: Dim = (2, 0, 0)
VOLUME: Dim = (3, 0, 0)
FORCE: Dim = (0, 1, 0)
MOMENT: Dim = (1, 1, 0)
LINE_LOAD: Dim = (-1, 1, 0)
PRESSURE: Dim = (-2, 1, 0)
DENSITY: Dim = (-3, 1, 0)
ANGLE: Dim = (0, 0, 1)
NONE: Dim = (0, 0, 0)

FT = 0.3048
INCH = 0.0254
LBF = 4.4482216152605
KIP = 1000 * LBF

# name -> (factor to SI base, dimension). Names are the canonical spellings.
UNITS: dict[str, tuple[float, Dim]] = {
    "1": (1.0, NONE),
    "percent": (0.01, NONE),
    # length
    "m": (1.0, LENGTH), "mm": (1e-3, LENGTH), "cm": (1e-2, LENGTH),
    "ft": (FT, LENGTH), "in": (INCH, LENGTH),
    "pt": (INCH / 72, LENGTH),  # PDF point, paper length (a sheet frame is still a separate type)
    # area / volume
    "m2": (1.0, AREA), "ft2": (FT * FT, AREA), "in2": (INCH * INCH, AREA),
    "m3": (1.0, VOLUME), "ft3": (FT ** 3, VOLUME), "yd3": ((3 * FT) ** 3, VOLUME), "in3": (INCH ** 3, VOLUME),
    # force
    "N": (1.0, FORCE), "kN": (1e3, FORCE), "lbf": (LBF, FORCE), "kip": (KIP, FORCE),
    # moment
    "N*m": (1.0, MOMENT), "kN*m": (1e3, MOMENT), "kip*ft": (KIP * FT, MOMENT), "kip*in": (KIP * INCH, MOMENT),
    "lbf*ft": (LBF * FT, MOMENT),
    # line load
    "N/m": (1.0, LINE_LOAD), "kN/m": (1e3, LINE_LOAD), "plf": (LBF / FT, LINE_LOAD), "klf": (KIP / FT, LINE_LOAD),
    # pressure / stress
    "Pa": (1.0, PRESSURE), "kPa": (1e3, PRESSURE), "MPa": (1e6, PRESSURE),
    "psf": (LBF / FT ** 2, PRESSURE), "ksf": (KIP / FT ** 2, PRESSURE),
    "psi": (LBF / INCH ** 2, PRESSURE), "ksi": (KIP / INCH ** 2, PRESSURE),
    # density
    "pcf": (LBF / FT ** 3, DENSITY), "kN/m3": (1e3, DENSITY),
    # angle
    "rad": (1.0, ANGLE), "deg": (math.pi / 180, ANGLE),
}

# spellings found in sources -> canonical
ALIASES: dict[str, str] = {
    "k": "kip", "kips": "kip", "kip": "kip", "lb": "lbf", "lbs": "lbf", "#": "lbf",
    "feet": "ft", "foot": "ft", "'": "ft", "inch": "in", "inches": "in", '"': "in",
    "k-ft": "kip*ft", "kft": "kip*ft", "k*ft": "kip*ft", "kip-ft": "kip*ft", "ft-k": "kip*ft", "ft*k": "kip*ft",
    "k-in": "kip*in", "kip-in": "kip*in", "in-k": "kip*in", "lb-ft": "lbf*ft", "ft-lb": "lbf*ft",
    "kn-m": "kN*m", "knm": "kN*m", "nm": "N*m",
    "k/ft": "klf", "kip/ft": "klf", "lb/ft": "plf", "#/ft": "plf",
    "k/ft2": "ksf", "k/ft^2": "ksf", "lb/ft2": "psf", "lb/ft^2": "psf", "#/ft2": "psf",
    "k/in2": "ksi", "lb/in2": "psi", "sf": "ft2", "sqft": "ft2", "sq ft": "ft2", "cy": "yd3",
    "degrees": "deg", "degree": "deg", "°": "deg", "%": "percent", "": "1", "-": "1",
}


def canonical(unit: str) -> str:
    """Canonical spelling of a unit string, or UnknownUnit."""
    if unit in UNITS:
        return unit
    u = unit.strip()
    if u in UNITS:
        return u
    low = u.lower()
    if low in ALIASES:
        return ALIASES[low]
    for name in UNITS:
        if name.lower() == low:
            return name
    raise UnknownUnit(f"unknown unit {unit!r}")


def dim(unit: str) -> Dim:
    return UNITS[canonical(unit)][1]


def convert(value: float, src: str, dst: str) -> float:
    s, d = canonical(src), canonical(dst)
    fs, ds = UNITS[s]
    fd, dd = UNITS[d]
    if ds != dd:
        raise UnitMismatch(f"cannot convert {s} ({_dname(ds)}) to {d} ({_dname(dd)})")
    return value * fs / fd


def _dname(d: Dim) -> str:
    names = {LENGTH: "length", AREA: "area", VOLUME: "volume", FORCE: "force", MOMENT: "moment",
             LINE_LOAD: "line load", PRESSURE: "pressure", DENSITY: "density", ANGLE: "angle", NONE: "dimensionless"}
    return names.get(d, str(d))


def _check_unit(u: str) -> str:
    return canonical(u)


UnitStr = Annotated[str, AfterValidator(_check_unit)]


class Quantity(BaseModel):
    """A number with its unit. Arithmetic refuses mixed dimensions."""
    model_config = ConfigDict(frozen=True, extra="forbid")
    value: float
    unit: UnitStr

    @property
    def dimension(self) -> Dim:
        return dim(self.unit)

    def to(self, unit: str) -> "Quantity":
        return Quantity(value=convert(self.value, self.unit, unit), unit=canonical(unit))

    def _same(self, other: "Quantity") -> float:
        if not isinstance(other, Quantity):
            raise UnitMismatch(f"cannot combine a Quantity with a bare {type(other).__name__}; give it a unit")
        return convert(other.value, other.unit, self.unit)

    def __add__(self, other: "Quantity") -> "Quantity":
        return Quantity(value=self.value + self._same(other), unit=self.unit)

    def __sub__(self, other: "Quantity") -> "Quantity":
        return Quantity(value=self.value - self._same(other), unit=self.unit)

    def __mul__(self, k: float) -> "Quantity":
        if isinstance(k, Quantity):
            raise UnitMismatch("Quantity x Quantity is not supported by this layer; convert explicitly")
        return Quantity(value=self.value * k, unit=self.unit)

    __rmul__ = __mul__

    def __truediv__(self, k):
        if isinstance(k, Quantity):
            if k.dimension != self.dimension:
                raise UnitMismatch(f"ratio of {self.unit} to {k.unit} is not dimensionless")
            return Quantity(value=self.value / self._same(k), unit="1")
        return Quantity(value=self.value / k, unit=self.unit)

    def __lt__(self, other: "Quantity") -> bool:
        return self.value < self._same(other)

    def __le__(self, other: "Quantity") -> bool:
        return self.value <= self._same(other)

    def __gt__(self, other: "Quantity") -> bool:
        return self.value > self._same(other)

    def __ge__(self, other: "Quantity") -> bool:
        return self.value >= self._same(other)

    def close_to(self, other: "Quantity", rel: float = 1e-9, abs_: float = 0.0) -> bool:
        return math.isclose(self.value, self._same(other), rel_tol=rel, abs_tol=abs_)


def q(value: float, unit: str) -> Quantity:
    return Quantity(value=value, unit=unit)


# ---------------- units declared by a source field name or header ----------------
_HEADER = re.compile(r"\[([^\]]+)\]\s*$")
# suffix tokens a field name may end with -> unit
_SUFFIX = {"k": "kip", "kip": "kip", "kips": "kip", "ft": "ft", "in": "in", "m": "m", "mm": "mm",
           "ksf": "ksf", "psf": "psf", "psi": "psi", "ksi": "ksi", "plf": "plf", "klf": "klf", "kft": "kip*ft",
           "deg": "deg", "pt": "pt", "uc": "1", "ratio": "1", "pcf": "pcf", "sf": "ft2", "ft2": "ft2"}


def unit_from_key(key: str) -> str | None:
    """The unit a field name or a table header DECLARES, else None (never a guess).

    "PreDL[ksf]" -> ksf; "Magnitude[k,k-ft]" -> None (ambiguous: two units declared);
    "max_start_reaction_k" -> kip; "bending_uc" -> "1"; "uc" -> "1"; "size" -> None.
    """
    m = _HEADER.search(key)
    if m:
        inner = m.group(1).strip()
        if "," in inner:
            return None
        try:
            return canonical(inner)
        except UnknownUnit:
            return None
    tok = re.split(r"[_.\s]", key.strip().lower())[-1]
    if key.strip().lower() == "uc":
        return "1"
    return _SUFFIX.get(tok)
