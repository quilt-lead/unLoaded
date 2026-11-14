"""Per-set profiles: everything the drawing-set and calc-package readers know about ONE set's
conventions (title block, sheet numbering, grid bubbles, calc sheet ids, section map, software
detectors, level cues, symbol legends), declared in a YAML file instead of code.

    calcgraph/profiles/default.yaml  generic conventions; every field is set here (committed)
    calcgraph/profiles/<id>.yaml     committed set profiles (synthetic sets only)
    data/profiles/<id>.yaml          LOCAL set profiles (gitignored) - a profile for a real,
                                     copyrighted set names its firm / stamp / permit strings, so
                                     it never enters git; $CALCGRAPH_PROFILES overrides the dir.
                                     The code runs without any of these (default applies).
Every set profile says `extends: default` + only what differs for that set.

Loading deep-merges the override onto its parent (mappings merge key by key; lists and scalars
replace) and validates the result against `Profile` (extra keys forbidden, every field required,
regexes compiled), so a typo or a missing field fails at load, not as a silent miss mid-ingest.

Which profile a document gets (`for_paths`): $CALCGRAPH_PROFILE if set, else the one profile whose
`match.filename_globs` hit a document's file name, else `default`. Two profiles matching the same
documents is an error.
"""
from __future__ import annotations

import fnmatch
import os
import re
from functools import lru_cache
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, PrivateAttr, field_validator, model_validator

PROFILE_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(PROFILE_DIR, "..", "..", ".."))


def _dirs() -> list[str]:
    return [PROFILE_DIR, os.environ.get("CALCGRAPH_PROFILES", os.path.join(_ROOT, "data", "profiles"))]


def _path(pid: str) -> str:
    hits = [os.path.join(d, f"{pid}.yaml") for d in _dirs() if os.path.isfile(os.path.join(d, f"{pid}.yaml"))]
    if len(hits) > 1:
        raise ValueError(f"profile {pid!r} defined twice: {hits}")
    if not hits:
        raise FileNotFoundError(f"no profile {pid!r} in {_dirs()}")
    return hits[0]

# plan-symbol kinds the vector classifier in connections.py can recognise; a legend may only map onto these
SYMBOL_KINDS = ("mrf", "moment_cantilever", "drag", "stiffener", "kicker")


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)


class XPos(_M):
    """An x position on a sheet: absolute PDF points, or a fraction of the page width."""
    pt: int | float | None = None     # int kept as int: output JSON stays byte-identical
    frac: float | None = None

    @model_validator(mode="after")
    def _one(self):
        if (self.pt is None) == (self.frac is None):
            raise ValueError("give exactly one of pt / frac")
        return self

    def at(self, width: float) -> float:
        return self.pt if self.pt is not None else self.frac * width


# ------------------------------------------------------------------ drawings

class TitleBlock(_M):
    x_min: XPos                       # title-block words sit right of this; also the drawing-area cutoff when no notes column
    sheet_number_regex: re.Pattern    # the sheet number = the TALLEST word in the title block matching this
    title_window_above_pt: float      # sheet title = words this far above the sheet number ...
    title_gap_pt: float               # ... and at least this far above it ...
    title_min_height_pt: float        # ... at least this tall, rows binned by baseline
    title_row_bin_pt: float
    title_strip_regex: re.Pattern     # label text removed from the front of the title


class NotesColumn(_M):
    heading_word: str                 # plan-notes heading word ("NOTES" of "FRAMING PLAN NOTES")
    x_min: XPos                       # the heading sits right of this and left of the title block
    heading_line_span_pt: float       # words on the heading's baseline within this span start the column
    margin_pt: float                  # drawing area ends this far left of the column
    sheet_kinds: list[str]            # only these sheet kinds have a notes column


SHEET_KINDS = ("foundation", "framing", "smf", "wall", "stair", "elevator", "trellis", "notes", "details", "other")


class SheetKindRule(_M):
    contains: str                     # upper-case substring of the sheet title
    kind: str

    @field_validator("kind")
    @classmethod
    def _known(cls, v):
        if v not in SHEET_KINDS:
            raise ValueError(f"sheet kind {v!r} is not one the readers know: {SHEET_KINDS}")
        return v


class Levels(_M):
    foundation_kinds: list[str]
    foundation_label: str
    level_regex: re.Pattern           # group 1 = level number
    level_label: str                  # "{n}" is replaced by the number
    level_kinds: list[str]
    roof_word: str
    roof_label: str
    roof_kinds: list[str]


class Grid(_M):
    label_regex: re.Pattern
    bubble_height_pt: tuple[float, float]   # bubble label text height range
    pair_axis_tol_pt: float                 # the two bubbles of one line share x (or y) within this
    pair_min_sep_pt: float                  # and are at least this far apart
    numbers_run: Literal["columns", "rows"]  # numbered grid lines are vertical (columns) or horizontal (rows)


class Tags(_M):
    foundation_mark_regex: re.Pattern
    smf_regex: re.Pattern
    role_words: list[str]
    split_sizes_regex: re.Pattern            # zero-width split of two sizes printed as one word
    timber_kinds: list[str]                  # sheet kinds where "8x10" is a timber size
    mark_kinds: list[str]                    # sheet kinds where foundation marks are tags
    smf_kinds: list[str]                     # sheet kinds where SMF markers are tags
    sfrs_prefix: str                         # a size printed with this prefix is part of the SFRS


class FootingSchedule(_M):
    kinds: list[str]
    mark_regex: re.Pattern
    row_tol_pt: float
    row_width_pt: float


class DetailCategory(_M):
    prefix: str                              # sheet-number prefix
    category: str


class Details(_M):
    type_sheet_regex: re.Pattern             # sheets whose details are connection TYPES
    number_height_pt: tuple[float, float]    # detail number text height (inclusive)
    title_height_pt: tuple[float, float]     # detail title words: lo <= h < hi
    x_max: XPos                              # detail numbers sit left of this
    categories: list[DetailCategory]         # first prefix match wins, else "other"
    other_sheet_connection_regex: re.Pattern  # a detail on another sheet is a connection type when its title matches
    connection_title_regex: re.Pattern       # is_connection
    spec_regex: re.Pattern                   # bolt / weld / plate lines kept as the type's spec
    text_ref_regex: re.Pattern               # detail reference in text; group 1 = label, group 2 = sheet

    @field_validator("text_ref_regex")
    @classmethod
    def _two_groups(cls, v):
        if v.groups < 2:
            raise ValueError("text_ref_regex needs group 1 = detail label, group 2 = sheet number")
        return v


class LegendEntry(_M):
    phrase: str                              # upper-case text in the legend line
    kind: str
    name: str

    @field_validator("kind")
    @classmethod
    def _known(cls, v):
        if v not in SYMBOL_KINDS:
            raise ValueError(f"symbol kind {v!r} is not one the classifier recognises: {SYMBOL_KINDS}")
        return v


class SymbolLegend(_M):
    sheet_kinds: list[str]
    line_prefix: str                         # legend lines start with this ("INDICATES ...")
    entries: list[LegendEntry]


class Drawings(_M):
    title_block: TitleBlock
    notes_column: NotesColumn
    sheet_kinds: list[SheetKindRule]
    no_tag_kinds: list[str]                  # sheets of these kinds are listed but carry no tags
    levels: Levels
    grid: Grid
    tags: Tags
    footing_schedule: FootingSchedule
    details: Details
    symbol_legend: SymbolLegend
    drawing_area_margin_pt: float            # plan symbols are searched inside the page minus this margin


# ------------------------------------------------------------------ calcs

class Region(_M):
    x_min: float | None = None
    x_max: float | None = None
    y_min: float | None = None
    y_max: float | None = None

    def holds(self, w) -> bool:
        return ((self.x_min is None or w[0] > self.x_min) and (self.x_max is None or w[0] < self.x_max)
                and (self.y_min is None or w[1] > self.y_min) and (self.y_max is None or w[1] < self.y_max))


class PageId(_M):
    regex: re.Pattern                        # the engineer's calc sheet number
    exclude: list[str]                       # words that match the regex but are not ids (material grades)
    regions: list[Region]                    # tried in order; first region with a candidate wins


class Span(_M):
    lo: float
    hi: float


class PadTitle(_M):
    marker_line: str                         # a line with this exact text marks the firm's calc pad
    heading_min_size: float
    heading_y: Span
    subject_y: Span
    subject_x: Span


class Risa3dTitle(_M):
    marker_line: str
    x_max: float
    y: Span
    min_size: float


class Title(_M):
    table_title_min_size: float
    table_title_x_max: float
    design_heads: list[str]                  # Enercalc member-design heads put before the DESCRIPTION value
    description_prefix: str
    risa3d: Risa3dTitle
    big_line_skip: list[str]                 # upper-case lines never taken as a big title
    pad: PadTitle
    field_keys: list[str]                    # "Model:" style fields whose value is the title


class SoftwareRule(_M):
    all: list[re.Pattern]                    # every regex must match the page text
    sheet_id_first: list[str] | None = None  # and the page id must start with one of these


class SoftwareDetector(_M):
    name: str
    any: list[SoftwareRule]


class Section(_M):
    title: str
    record_type: str | None = None           # whole-page record type for this section's pages ...
    record_sheet_regex: re.Pattern | None = None  # ... whose sheet id matches this
    subtotal_row_prefix: str | None = None   # a table row starting with this is the page's subtotal


class RunRule(_M):
    section: str
    software: str | None = None
    run: str


class ConnectionRule(_M):
    id: str
    regex: re.Pattern
    what: str
    designs_connection: bool


class Label(_M):
    kind: str
    regex: re.Pattern


class Calcs(_M):
    page_id: PageId
    banner_regex: re.Pattern
    boilerplate: list[str]                   # alternatives of one case-insensitive whole-line regex
    continued_regex: re.Pattern
    stamp_text_regex: re.Pattern | None      # stamp text overprinted on every page, removed from table rows
    stamp_colors: list[int]                  # span colours of that stamp, dropped from characters
    comment_colors: dict[int, str]           # span colour -> name of engineer commentary
    labels: list[Label]
    drawing_ref_regex: re.Pattern            # group 1 = detail, group 2 = sheet
    title: Title
    level_regex: re.Pattern                  # group 1 = "Level N" or "Roof"
    toc_min_leaders: int
    software: list[SoftwareDetector]         # first detector with a matching rule wins
    fallback_software: str
    sections: dict[str, Section]
    sketch_sections: list[str] | None        # rotated plan sketches (no tables) of these sections ...
    sketch_software: list[str]               # ... from this software are model sketches
    run_rules: list[RunRule]                 # main package: (section, software) -> run, first match wins
    software_runs: dict[str, str]            # else software -> run, else software lower-cased
    runs: dict[str, str]                     # run id -> description
    run_footers: list[tuple[str, str]]       # (run id, footer text marking a RISA table page)
    skip_titles: list[str]                   # page titles that are not calcs (cover)
    lowest_framed_level: str | None          # RISA floor whose points name the footings; null = lowest floor elevation
    area_load_sketches: str | None           # sheets where area-load polygons are drawn (named in rule text)
    sketch_bubble_regex: re.Pattern
    note_grid_ref_regex: re.Pattern          # "@ C.8/4" in a note: group 1 letter grid, group 2 number grid
    model_axes_note: str
    connection_rules: list[ConnectionRule]

    _boiler: re.Pattern = PrivateAttr()

    def model_post_init(self, _ctx) -> None:
        self._boiler = re.compile("^(" + "|".join(self.boilerplate) + ")$", re.I)

    @property
    def boilerplate_rx(self) -> re.Pattern:
        return self._boiler


class Positional(_M):
    column_sheet: str | None                 # null = the first foundation-kind sheet
    beam_sheets: dict[str, str] | None       # sheet -> calc level; null = framing sheets with a level


class Match(_M):
    filename_globs: list[str]


class Profile(_M):
    id: str
    name: str
    extends: str | None = None
    match: Match
    drawings: Drawings
    calcs: Calcs
    positional: Positional


# ------------------------------------------------------------------ loading

def _merge(base, over):
    # an x position ({pt} / {frac}) is one value: an override replaces it whole
    if isinstance(base, dict) and isinstance(over, dict) and not set(over) <= {"pt", "frac"}:
        out = dict(base)
        for k, v in over.items():
            out[k] = _merge(base[k], v) if k in base else v
        return out
    return over


def _raw(pid: str, seen: tuple = ()) -> dict:
    if pid in seen:
        raise ValueError(f"profile extends cycle: {' -> '.join(seen + (pid,))}")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,60}", pid):
        raise ValueError(f"bad profile id {pid!r}")
    path = _path(pid)
    with open(path) as fh:
        data = yaml.safe_load(fh) or {}
    if data.get("id") != pid:
        raise ValueError(f"{path}: id {data.get('id')!r} must equal the file name {pid!r}")
    parent = data.get("extends")
    if parent:
        base = _raw(parent, seen + (pid,))
        base = {k: v for k, v in base.items() if k not in ("id", "name", "extends", "match")}
        data = _merge(base, data)
    return data


@lru_cache(maxsize=None)
def load(pid: str) -> Profile:
    return Profile.model_validate(_raw(pid))


def available() -> list[str]:
    return sorted({f[:-5] for d in _dirs() if os.path.isdir(d) for f in os.listdir(d) if f.endswith(".yaml")})


def for_paths(*paths: str | None) -> Profile:
    env = os.environ.get("CALCGRAPH_PROFILE")
    if env:
        return load(env)
    names = [os.path.basename(p) for p in paths if p]
    hits = []
    for pid in available():
        pf = load(pid)
        if any(fnmatch.fnmatchcase(n, g) for n in names for g in pf.match.filename_globs):
            hits.append(pid)
    if len(hits) > 1:
        raise ValueError(f"documents {names} match several profiles: {hits}")
    return load(hits[0] if hits else "default")


def resolve(profile: Profile | str | None, *paths: str | None) -> Profile:
    if isinstance(profile, Profile):
        return profile
    if isinstance(profile, str):
        return load(profile)
    return for_paths(*paths)
