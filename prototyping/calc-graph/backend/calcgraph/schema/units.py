"""Units: every quantity in the schema carries its unit, on `pint`.

pint owns the unit algebra (its definitions of the foot, inch, pound-force, pascal ...) and
the conversions. This module is the thin layer the schema needs on top of it, with the
public API the callers and contract checks rely on unchanged:

- a CLOSED vocabulary of ~45 structural units with canonical spellings ("kip*ft", "ksf") and
  the spellings found in sources (`ALIASES`); anything else is rejected (`UnknownUnit`), so a
  source cannot smuggle an arbitrary pint expression into the schema
- converting or adding across dimensions is rejected (`UnitMismatch`), e.g. kip -> ft; pint's
  `DimensionalityError` is translated, never leaked
- angle is its own dimension here (pint treats radian as dimensionless; a degree added to a
  ratio would pass there) so rad/deg only convert among themselves
- a `Quantity` always has a unit; a dimensionless value says so with unit "1"

`unit_from_key()` reads the unit a source declares in a field name or table header
("max_start_reaction_k", "length_ft", "PreDL[ksf]", "Magnitude[k,k-ft]") so adapters
never guess one.
"""
from __future__ import annotations

import math
import re
from functools import lru_cache
from typing import Annotated

import pint
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

# 1 ft in metres (exact; pint's `foot` is the same definition). Used by schema/frames.py.
FT = 0.3048

# canonical name -> pint expression. Names are the canonical spellings.
UNITS: dict[str, str] = {
    "1": "dimensionless",
    "percent": "0.01",
    # length
    "m": "meter", "mm": "millimeter", "cm": "centimeter", "ft": "foot", "in": "inch",
    "pt": "inch / 72",  # PDF point, paper length (a sheet frame is still a separate type)
    # area / volume
    "m2": "meter ** 2", "ft2": "foot ** 2", "in2": "inch ** 2",
    "m3": "meter ** 3", "ft3": "foot ** 3", "yd3": "yard ** 3", "in3": "inch ** 3",
    # force
    "N": "newton", "kN": "kilonewton", "lbf": "pound_force", "kip": "1000 * pound_force",
    # moment
    "N*m": "newton * meter", "kN*m": "kilonewton * meter", "kip*ft": "1000 * pound_force * foot",
    "kip*in": "1000 * pound_force * inch", "lbf*ft": "pound_force * foot",
    # line load
    "N/m": "newton / meter", "kN/m": "kilonewton / meter", "plf": "pound_force / foot",
    "klf": "1000 * pound_force / foot",
    # pressure / stress
    "Pa": "pascal", "kPa": "kilopascal", "MPa": "megapascal",
    "psf": "pound_force / foot ** 2", "ksf": "1000 * pound_force / foot ** 2",
    "psi": "pound_force / inch ** 2", "ksi": "1000 * pound_force / inch ** 2",
    # density
    "pcf": "pound_force / foot ** 3", "kN/m3": "kilonewton / meter ** 3",
    # angle (own dimension: see module docstring)
    "rad": "cg_angle", "deg": "pi / 180 * cg_angle",
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
    "degrees": "deg", "degree": "deg", "\u00b0": "deg", "%": "percent", "": "1", "-": "1",
}

# ---------------- the pint registry: a private one, the vocabulary above defined on it ----------------
_ureg = pint.UnitRegistry()
_ureg.define("cg_angle = [cg_angle]")  # radian as a real dimension, not pint's dimensionless one


def _ident(name: str) -> str:
    return "cg_u_" + re.sub(r"\W", "_", name.replace("*", "_x_").replace("/", "_per_"))


for _name, _expr in UNITS.items():
    if _name not in ("1", "rad"):
        _ureg.define(f"{_ident(_name)} = {_expr}")
_ureg.define("cg_u_rad = cg_angle")
assert len({_ident(n) for n in UNITS}) == len(UNITS), "unit names collide once made into identifiers"


@lru_cache(maxsize=None)
def _unit(name: str) -> pint.Unit:
    """The pint unit of a CANONICAL name."""
    return _ureg.dimensionless if name == "1" else getattr(_ureg, _ident(name))


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
    """(length, force, angle) exponents, read off pint's dimensionality of the unit."""
    d = _unit(canonical(unit)).dimensionality
    mass, length, time, angle = (int(d.get(k, 0)) for k in ("[mass]", "[length]", "[time]", "[cg_angle]"))
    if time != -2 * mass:  # every vocabulary unit is a pure length/force/angle product
        raise UnknownUnit(f"{unit!r} is not a length/force/angle unit")
    return (length - mass, mass, angle)


def convert(value: float, src: str, dst: str) -> float:
    s, d = canonical(src), canonical(dst)
    if s == d:
        return value
    ds, dd = dim(s), dim(d)
    if ds != dd:
        raise UnitMismatch(f"cannot convert {s} ({_dname(ds)}) to {d} ({_dname(dd)})")
    return float(_ureg.Quantity(value, _unit(s)).to(_unit(d)).magnitude)


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
