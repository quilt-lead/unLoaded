"""Coordinate frames as explicit types. A coordinate never travels without its frame.

Frames
  SheetPt(doc, page)   PDF points on one page of one document, PyMuPDF page space
                       (origin top-left, y down, unrotated page box). Two pages are two frames.
  BuildingFt(building) plan feet of a building read off its drawings: x east from the first
                       numbered grid line, y north from the last lettered one, z up from the
                       finish-floor datum (the convention plans_to_ifc.py writes the 3D model in)
  ModelM(doc)          world metres of one IFC model file
  CalcModelFt(model)   an analysis model's own coordinates in feet (e.g. RISA plan Z/X). The
                       2021 calc model and the 2023 drawings do NOT share a frame; there is no
                       registration between them, and asking for one raises NoRegistration.

Converters exist only where a measured relation exists: SheetCalibration (sheet -> building,
piecewise linear between the sheet's own grid bubbles, as plans_to_ifc.Frame.mapper does) and
ModelRegistration (building feet -> IFC metres for a model written from that building frame).
Mixing frames in any operation raises FrameMismatch.
"""
from __future__ import annotations

import math
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .units import FT


class FrameMismatch(ValueError):
    pass


class NoRegistration(ValueError):
    pass


class _Frame(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class SheetPt(_Frame):
    kind: Literal["sheet_pt"] = "sheet_pt"
    doc_sha: str = Field(min_length=64, max_length=64)
    page: int = Field(ge=1, description="1-based page number")
    sheet: str | None = Field(default=None, description="sheet number printed on the page, if any (label only)")

    def key(self) -> tuple:
        return (self.kind, self.doc_sha, self.page)


class BuildingFt(_Frame):
    kind: Literal["building_ft"] = "building_ft"
    building: str = Field(description="building / set id the grid belongs to")

    def key(self) -> tuple:
        return (self.kind, self.building)


class ModelM(_Frame):
    kind: Literal["model_m"] = "model_m"
    doc_sha: str = Field(min_length=64, max_length=64)

    def key(self) -> tuple:
        return (self.kind, self.doc_sha)


class CalcModelFt(_Frame):
    kind: Literal["calc_model_ft"] = "calc_model_ft"
    model: str = Field(description="analysis model id, e.g. the RISA file name")

    def key(self) -> tuple:
        return (self.kind, self.model)


Frame = Annotated[Union[SheetPt, BuildingFt, ModelM, CalcModelFt], Field(discriminator="kind")]


def same_frame(a, b) -> bool:
    # the printed sheet label is not part of a sheet frame's identity
    return a.key() == b.key()


def require_frame(have, want, what: str = "value") -> None:
    if not same_frame(have, want):
        raise FrameMismatch(f"{what} is in {_desc(have)}, expected {_desc(want)}")


def _desc(f) -> str:
    if isinstance(f, SheetPt):
        return f"SheetPt(doc {f.doc_sha[:10]}.., page {f.page})"
    if isinstance(f, BuildingFt):
        return f"BuildingFt({f.building})"
    if isinstance(f, ModelM):
        return f"ModelM(doc {f.doc_sha[:10]}..)"
    if isinstance(f, CalcModelFt):
        return f"CalcModelFt({f.model})"
    return repr(f)


class Point2(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    frame: Frame
    x: float
    y: float

    def dist(self, other: "Point2") -> float:
        require_frame(other.frame, self.frame, "point")
        return math.hypot(self.x - other.x, self.y - other.y)


class Point3(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    frame: Frame
    x: float
    y: float
    z: float

    def dist(self, other: "Point3") -> float:
        require_frame(other.frame, self.frame, "point")
        return math.dist((self.x, self.y, self.z), (other.x, other.y, other.z))


class BBox(BaseModel):
    """Axis-aligned box in a frame (x0 <= x1, y0 <= y1)."""
    model_config = ConfigDict(frozen=True, extra="forbid")
    frame: Frame
    x0: float
    y0: float
    x1: float
    y1: float

    @model_validator(mode="after")
    def _ordered(self):
        if self.x1 < self.x0 or self.y1 < self.y0:
            raise ValueError(f"bbox not ordered: ({self.x0},{self.y0},{self.x1},{self.y1})")
        return self

    def union(self, other: "BBox") -> "BBox":
        require_frame(other.frame, self.frame, "bbox")
        return BBox(frame=self.frame, x0=min(self.x0, other.x0), y0=min(self.y0, other.y0),
                    x1=max(self.x1, other.x1), y1=max(self.y1, other.y1))

    def contains(self, p: Point2) -> bool:
        require_frame(p.frame, self.frame, "point")
        return self.x0 <= p.x <= self.x1 and self.y0 <= p.y <= self.y1


def sheet_bbox(doc_sha: str, page: int, rect, sheet: str | None = None) -> BBox:
    x0, y0, x1, y1 = rect
    return BBox(frame=SheetPt(doc_sha=doc_sha, page=page, sheet=sheet), x0=x0, y0=y0, x1=x1, y1=y1)


# ---------------- converters ----------------
class GridAnchor(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    label: str
    pt: float = Field(description="grid line position on the sheet, PDF points")
    ft: float = Field(description="building coordinate of the grid line, feet")


class SheetCalibration(BaseModel):
    """Sheet points -> building feet for ONE plan sheet, from its own grid bubbles.

    x maps piecewise linearly between the sheet's numbered grid lines; y between its
    lettered ones (measured from the top row, then flipped so north is +y). Outside the
    outermost grid lines the measured scale (kx, ky ft per pt) extrapolates.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")
    sheet: SheetPt
    building: BuildingFt
    cols: list[GridAnchor] = Field(min_length=2)
    rows: list[GridAnchor] = Field(min_length=2, description="ft measured from the top lettered row, south positive")
    kx_ft_per_pt: float
    ky_ft_per_pt: float
    depth_ft: float = Field(description="distance from the top row to the bottom row, ft")
    source: str = ""

    @staticmethod
    def _interp(v: float, pts: list[tuple[float, float]], k: float) -> float:
        pts = sorted(pts)
        if v <= pts[0][0]:
            return pts[0][1] + (v - pts[0][0]) * k
        if v >= pts[-1][0]:
            return pts[-1][1] + (v - pts[-1][0]) * k
        for (p0, f0), (p1, f1) in zip(pts, pts[1:]):
            if p0 <= v <= p1:
                return f0 + (v - p0) / (p1 - p0) * (f1 - f0)
        raise AssertionError("unreachable")

    def to_building(self, p: Point2) -> Point2:
        require_frame(p.frame, self.sheet, "sheet point")
        x = self._interp(p.x, [(a.pt, a.ft) for a in self.cols], self.kx_ft_per_pt)
        y = self.depth_ft - self._interp(p.y, [(a.pt, a.ft) for a in self.rows], self.ky_ft_per_pt)
        return Point2(frame=self.building, x=x, y=y)


class ModelRegistration(BaseModel):
    """Building feet -> IFC world metres for a model written in that building frame."""
    model_config = ConfigDict(frozen=True, extra="forbid")
    building: BuildingFt
    model: ModelM
    m_per_ft: float = FT
    offset_m: tuple[float, float, float] = (0.0, 0.0, 0.0)
    source: str = ""

    def to_model(self, p: Point3) -> Point3:
        require_frame(p.frame, self.building, "building point")
        ox, oy, oz = self.offset_m
        return Point3(frame=self.model, x=p.x * self.m_per_ft + ox, y=p.y * self.m_per_ft + oy,
                      z=p.z * self.m_per_ft + oz)

    def to_building(self, p: Point3) -> Point3:
        require_frame(p.frame, self.model, "model point")
        ox, oy, oz = self.offset_m
        return Point3(frame=self.building, x=(p.x - ox) / self.m_per_ft, y=(p.y - oy) / self.m_per_ft,
                      z=(p.z - oz) / self.m_per_ft)


def register(a, b):
    """There is no generic registration between frames. Raises unless a converter exists."""
    raise NoRegistration(f"no measured registration from {_desc(a)} to {_desc(b)}; use a SheetCalibration or "
                         f"ModelRegistration built from evidence, never an assumed one")
