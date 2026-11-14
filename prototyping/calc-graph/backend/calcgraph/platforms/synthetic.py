"""ONE deterministic generator of the construction state of the synthetic building.

Input: design.json (synth/v2: elements, relations, records, building). Output: a
`ConstructionState` - submittal packages, RFIs, change events / orders, cost codes and
budget lines, a CPM schedule and a sheet index - every item listing the registry element
ids it concerns. The vendor adapters (procore.py, autodesk_build.py, forma.py) only RESHAPE
this state; they never invent facts of their own, so all platforms agree.

Nothing here is real: project, companies and people are fictional, every figure is an
ESTIMATE from the unit rates in `RATES` (stated, editable assumptions).

The "today" state is not hand-assigned per package. The schedule is computed (CPM, working
days, Mon-Fri, no holidays) and each package's stage is READ OFF the schedule at the data
date, so stages, dates and float are mutually consistent:

    foundations (rebar, concrete, anchor rods) .... poured / set           -> erected
    Level 2 steel, both sequences ................. erected
    Level 3 Seq 1 ................................. delivered, erection under way
    Level 3 Seq 2 ................................. fabricated, not yet shipped
    Roof Seq 1 .................................... approved, in fabrication
    Roof Seq 2 .................................... submitted, under EOR review
    floor deck .................................... approved; Level 2 deck being laid
    roof deck ..................................... submitted;  SFRM ........ draft

Erection sequences: Seq 1 = grid lines 1 through 3 inclusive (line-3 columns, girders and
braces erect with Seq 1), Seq 2 = bays 3-4 and 4-5 up to line 5. A member belongs to the
sequence of its midpoint x. Columns are single 40-ft pieces erected with Level 2.

Normalized `fields` per kind (NormalizedRecord.fields):
  submittal          stage, spec_section, spec_title, package_kind, level, sequence, revision,
                     response, ball_in_court, activity_refs
  rfi                question, answer, ball_in_court, cost_impact, schedule_impact, drawing_number
  change_event       amount_usd, reason, line_items, change_order_refs
  change_order       amount_usd, schedule_days, change_event_ref, co_type
  budget_line        cost_code, quantity, unit, unit_cost_usd, amount_usd, basis
  cost_code          code, division
  schedule_activity  wbs, duration_days, percent_complete, total_float_days, critical,
                     predecessors [{ref, type, lag_days}], early/late start/finish
  sheet              discipline, revision
"""
from __future__ import annotations

import datetime as dt
import hashlib
import math
import random
from dataclasses import dataclass, field

SEED = 20261113
AS_OF = dt.date(2026, 11, 13)          # status date: close of business Friday 13 Nov 2026
PROJECT = {
    "name": "Harbor View Office",
    "number": "HVO-2026-014",
    "address": "1200 Quayside Avenue, Port Calder (fictional)",
    "companies": {
        "gc": "Tidewater Builders (fictional)",
        "steel": "Keelson Steel Fabricators (fictional)",
        "eor": "Northpoint Structural Engineers (fictional)",
        "architect": "Fernwood Architects (fictional)",
        "concrete": "Bedrock Concrete Co. (fictional)",
        "deck": "Ridgeline Deck & Fireproofing (fictional)",
        "owner": "Quayside Partners LLC (fictional)",
    },
    "people": {
        "gc_pm": "Marisol Okafor", "gc_super": "Wen Castellanos", "steel_pm": "Theo Lindqvist",
        "eor": "Priya Raman", "architect": "Jonah Albers", "concrete_pm": "Rosa Lindgren",
        "deck_pm": "Callum Achebe", "owner_rep": "Hana Moreau",
    },
}

# ---------------------------------------------------------------------------------------------
# Unit rates: ASSUMPTIONS for a 2026 US mid-market steel office. Every estimate states them.
RATES = {
    "steel_w_usd_per_ton": 4800.0,      # W shapes, furnished + fabricated + erected (incl. bolts, paint)
    "steel_hss_usd_per_ton": 5600.0,    # HSS braces, furnished + fabricated + erected
    "connection_usd_each": {            # shop + field cost per connection, by detail type
        "ST-2": 180.0, "ST-3": 220.0, "ST-4": 260.0, "ST-5": 300.0, "ST-6": 340.0, "ST-7": 380.0,
        "MC-1": 3800.0, "DC-1": 650.0, "DC-2": 900.0, "DC-3": 1200.0,
        "BG-1": 1800.0, "BG-2": 2400.0, "BG-3": 3200.0,
        "BP-1": 350.0, "BP-2": 450.0, "BP-3": 600.0, "BP-4": 800.0,
    },
    "foundation_concrete_usd_per_cy": 850.0,   # all-in: excavation, forms, rebar, 4 ksi concrete, backfill
    "fireproofing_usd_per_sf": 3.25,           # SFRM, 2-hr, per sf of member surface
    "steel_deck_usd_per_sf": 6.50,
    "slab_on_deck_usd_per_sf": 9.00,
    "eng_redesign_usd_per_calc_record": 450.0,  # EOR: ~3 h at $150/h per calc record redone
    "resubmittal_usd_per_package": 1200.0,      # detailer revision + re-issue per affected package
    # penalty on the ORIGINAL member cost when a member must be replaced after it exists:
    "replacement_factor_by_stage": {"fabricated": 0.85, "delivered": 0.95, "erected": 1.60},
    # multiplier on the NEW connection cost when a connection is changed after it exists
    "connection_rework_factor_by_stage": {"fabricated": 1.5, "delivered": 1.6, "erected": 2.5},
    "poured_footing_factor": 2.0,               # enlarging a poured footing vs placing it new
    "poured_footing_mobilization_usd": 2500.0,  # per footing: excavate, dowel, shore, re-pour
}
# Schedule effects of a change, working days. Each is a piece of WORK inserted into the CPM network as
# its own activity (change_order.estimate -> ConstructionState.reschedule), starting no earlier than the
# approval date's data date and finishing before the element's next open activity (its "hold target").
SCHEDULE_RULES = {
    "revise_under_review": 3,      # shop drawings still in review: revise them, review restarts
    "redesign": 15,                # shop drawings approved: EOR redesign 5 + re-detail 5 + re-review 5
    "refabricate": 8,              # piece already fabricated: re-fabricate the replacement + ship
    "field_rework_per_member": 0.5, "field_rework_min": 2,   # piece already erected: swap it in the field
    "poured_footing": 4,           # footing already poured: excavate, dowel, form, pour, cure the enlargement
}
# The work a change needs for an element at each construction stage. CUMULATIVE by construction: a later
# stage needs everything an earlier one did plus more (a fabricated piece is redesigned AND re-fabricated),
# so a later approval can never need less work. scripts/check_platform_contracts.py (H1) asserts it.
STAGE_WORK = {
    "design": (), "draft": (),
    "submitted": ("revise_under_review",),
    "approved": ("redesign",),
    "fabricated": ("redesign", "refabricate"),
    "delivered": ("redesign", "refabricate"),
    "erected": ("redesign", "refabricate", "field_rework"),   # a poured footing's field rework: poured_footing
}
# a step that includes another (redesigning approved drawings includes revising them): used by the check
STEP_INCLUDES = {"redesign": ("revise_under_review",)}
# index into an element's chain [DET, REV, FAB, DEL, INSTALL] of the first activity its rework must
# precede at each stage (past the chain = the element's downstream activities)
STAGE_HOLD_FROM = {"submitted": 1, "approved": 2, "fabricated": 3, "delivered": 4, "erected": 5}


# ---------------------------------------------------------------------------------------------
def shape_props(size: str) -> dict:
    """weight (lb/ft), perimeter (ft per ft) for a section size. W: weight from the name."""
    w = None
    props = {}
    try:
        from synth.v2 import aisc   # read-only use of the AISC v16 subset table
        props = aisc.shapes().get(size, {}) or {}
    except Exception:   # pragma: no cover - table missing
        props = {}
    if props.get("W"):
        w = float(props["W"])
    elif size.upper().startswith("W") and "X" in size.upper():
        w = float(size.upper().split("X")[1])
    if props.get("Type") == "HSS":
        perim_in = 2 * ((props.get("Ht") or 0) + (props.get("B") or 0))
    elif props.get("d") and props.get("bf"):
        perim_in = 2 * props["d"] + 4 * props["bf"] - 2 * (props.get("tw") or 0)
    else:
        perim_in = 48.0
    return {"size": size, "lb_per_ft": w, "perimeter_ft": perim_in / 12.0, "type": props.get("Type", "W"),
            "source": "AISC Shapes Database v16.0 subset (synth/v2/data)" if props else "weight from size name"}


def steel_rate(size: str) -> float:
    return RATES["steel_hss_usd_per_ton"] if size.upper().startswith("HSS") else RATES["steel_w_usd_per_ton"]


def conn_rate(ctype: str) -> float:
    t = (ctype or "").rstrip("*")
    if t in RATES["connection_usd_each"]:
        return RATES["connection_usd_each"][t]
    fam = t.split("-")[0]
    fallback = {"ST": 250.0, "MC": 3800.0, "DC": 800.0, "BG": 2500.0, "BP": 500.0}
    return fallback.get(fam, 300.0)


def footing_cy(B_ft: float, h_in: float) -> float:
    return B_ft * B_ft * (h_in / 12.0) / 27.0


def _uuid(*parts) -> str:
    h = hashlib.sha1("|".join(map(str, parts)).encode()).hexdigest()
    return f"{h[:8]}-{h[8:12]}-5{h[13:16]}-a{h[17:20]}-{h[20:32]}"


def _int_id(*parts, base=100000, span=899999) -> int:
    return base + int(hashlib.sha1("|".join(map(str, parts)).encode()).hexdigest()[:8], 16) % span


# ---------------------------------------------------------------------------------------------
# working-day calendar
def add_workdays(start: dt.date, n: int) -> dt.date:
    d, step = start, (1 if n >= 0 else -1)
    k = abs(n)
    while k:
        d += dt.timedelta(days=step)
        if d.weekday() < 5:
            k -= 1
    return d


def next_workday(d: dt.date) -> dt.date:
    d = d + dt.timedelta(days=1)
    while d.weekday() >= 5:
        d += dt.timedelta(days=1)
    return d


def workdays_between(a: dt.date, b: dt.date) -> int:
    """n such that add_workdays(a, n) == b, for workdays a and b (negative when b is before a)."""
    if b < a:
        return -workdays_between(b, a)
    n, d = 0, a
    while d < b:
        d += dt.timedelta(days=1)
        if d.weekday() < 5:
            n += 1
    return n


def as_of_date(as_of: dt.date | str | None) -> dt.date:
    """The status date an as-of value names (None -> AS_OF, the synthetic project's status date)."""
    if as_of is None:
        return AS_OF
    return as_of if isinstance(as_of, dt.date) else dt.date.fromisoformat(str(as_of)[:10])


@dataclass
class Activity:
    ref: str
    name: str
    wbs: str
    dur: int
    preds: list[tuple[str, str, int]] = field(default_factory=list)   # (ref, FS|SS, lag)
    element_ids: list[str] = field(default_factory=list)
    package_ref: str | None = None
    es: int = 0
    ef: int = 0
    ls: int = 0
    lf: int = 0


def cpm(acts: dict[str, Activity], finish_constraint: int | None = None,
        data_day: int | None = None, fixed: dict[str, tuple[int, int]] | None = None,
        resume: dict[str, int] | None = None) -> int:
    """Forward + backward pass in working-day indices (ES inclusive, EF exclusive).
    `fixed` pins (es, ef) of completed / started activities; `data_day` floors the start of
    everything not yet started. `resume` = {started activity: its remaining working days}: a started
    activity keeps its start but cannot finish before its latest FS predecessor (an inserted rework
    activity holding it) plus its remaining duration. Returns the project early finish."""
    fixed = fixed or {}
    resume = resume or {}
    order = _topo(acts)
    for r in order:
        a = acts[r]
        es = 0
        fs_ready = 0
        for p, typ, lag in a.preds:
            pa = acts[p]
            es = max(es, (pa.ef if typ == "FS" else pa.es) + lag)
            if typ == "FS":
                fs_ready = max(fs_ready, pa.ef + lag)
        if r in fixed:
            a.es, a.ef = fixed[r]
            if r in resume:
                a.ef = max(a.ef, fs_ready + resume[r])
            continue
        if data_day is not None:
            es = max(es, data_day)
        a.es, a.ef = es, es + a.dur
    finish = max(a.ef for a in acts.values())
    lf_end = finish if finish_constraint is None else finish_constraint
    succ: dict[str, list[tuple[str, str, int]]] = {r: [] for r in acts}
    for r, a in acts.items():
        for p, typ, lag in a.preds:
            succ[p].append((r, typ, lag))
    for r in reversed(order):
        a = acts[r]
        lf = lf_end
        for s, typ, lag in succ[r]:
            sa = acts[s]
            lf = min(lf, sa.ls - lag if typ == "FS" else sa.ls - lag + (a.ef - a.es))
        a.lf, a.ls = lf, lf - (a.ef - a.es)   # ef - es = dur, except a started activity held past its plan
    return finish


def _topo(acts: dict[str, Activity]) -> list[str]:
    seen, out = set(), []

    def visit(r, stack=()):
        if r in seen:
            return
        if r in stack:
            raise ValueError(f"schedule logic loop at {r}")
        for p, _, _ in acts[r].preds:
            visit(p, stack + (r,))
        seen.add(r)
        out.append(r)
    for r in acts:
        visit(r)
    return out


# ---------------------------------------------------------------------------------------------
@dataclass
class ConstructionState:
    project: dict
    rates: dict
    schedule_rules: dict
    as_of: str
    elements: dict[str, dict]
    submittals: list[dict]
    rfis: list[dict]
    change_events: list[dict]
    change_orders: list[dict]
    cost_codes: list[dict]
    budget_lines: list[dict]
    activities: list[dict]
    sheets: list[dict]
    element_index: dict[str, dict]       # element id -> {stage, chain, packages, sequence, level, reasons}
    contract_finish: str
    forecast_finish: str
    groups: dict[str, list[str]] = field(default_factory=dict)   # LEVEL:/GRID:/FRAME: id -> member element ids
    inbox_key: list[dict] = field(default_factory=list, repr=False)   # inbox_synth answer key (never on a record)
    _acts: dict[str, Activity] = field(default_factory=dict, repr=False)
    _day0: dt.date = field(default=AS_OF, repr=False)
    _data_day: int = 0

    # -------- helpers used by change_order / status
    def day_to_date(self, n: int) -> dt.date:
        return add_workdays(self._day0, n)

    def submittal(self, ref: str) -> dict | None:
        return next((s for s in self.submittals if s["ref"] == ref), None)

    def activity(self, ref: str) -> dict | None:
        return next((a for a in self.activities if a["ref"] == ref), None)

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in ("project", "rates", "schedule_rules", "as_of", "submittals", "rfis",
                                              "change_events", "change_orders", "cost_codes", "budget_lines",
                                              "activities", "sheets", "element_index", "contract_finish",
                                              "forecast_finish", "groups")}

    def successors(self, ref: str) -> list[str]:
        return [r for r, a in self._acts.items() if any(p == ref for p, _, _ in a.preds)]

    def hold_target(self, refs: list[str]) -> str | None:
        """The first activity in `refs` not complete at the data date; when every one is complete, the
        earliest-starting open activity reachable through their successors (work on an element whose
        own follow-on activities are all done still has to finish before something - ultimately
        substantial completion). None only when the whole project is complete."""
        status = {a["ref"]: a["status"] for a in self.activities}
        for r in refs:
            if r in self._acts and status.get(r) != "complete":
                return r
        seen, frontier, found = set(refs), list(refs), []
        while frontier:
            nxt = []
            for r in frontier:
                for s in self.successors(r):
                    if s in seen:
                        continue
                    seen.add(s)
                    (found if status.get(s) != "complete" else nxt).append(s)
            if found:
                return min(found, key=lambda r: (self._acts[r].es, r))
            frontier = nxt
        return None

    def reschedule(self, inserted: list[dict]) -> dict:
        """Re-run the CPM from the data date with the change's work INSERTED as new activities.

        inserted: [{ref, name, dur, after: [inserted refs it follows], holds: [existing refs it must
        finish before]}]. Each inserted activity starts no earlier than the data date (the morning after
        approval). Completed activities stay fixed; a started activity keeps its start and, when held,
        finishes no earlier than the rework plus its remaining duration. Returns per-activity before/after
        early finish and float (baseline float for held activities), the inserted activities' own dates
        and the project finish shift."""
        import copy
        acts = copy.deepcopy(self._acts)
        status = {a["ref"]: a["status"] for a in self.activities}
        fixed, resume = {}, {}
        for r, a in acts.items():
            if status[r] == "complete":
                fixed[r] = (a.es, a.ef)
            elif status[r] == "in_progress":
                fixed[r] = (a.es, a.ef)
                resume[r] = a.ef - self._data_day
        new_refs = set()
        for x in inserted:
            if x["ref"] in acts:
                raise ValueError(f"inserted activity {x['ref']} already exists")
            acts[x["ref"]] = Activity(x["ref"], x["name"], "0.0 Change (inserted)", int(x["dur"]),
                                      [(p, "FS", 0) for p in x.get("after", [])])
            new_refs.add(x["ref"])
        for x in inserted:
            for t in x.get("holds", []):
                if status.get(t) == "complete":
                    raise ValueError(f"{x['ref']} cannot hold {t}: it is complete at the data date")
                acts[t].preds.append((x["ref"], "FS", 0))
        cf = self._contract_day
        new_finish = cpm(acts, finish_constraint=cf, data_day=self._data_day, fixed=fixed, resume=resume)
        old_finish = max(a.ef for a in self._acts.values())
        per, new = {}, {}
        held = {t for x in inserted for t in x.get("holds", [])}
        for r, n in acts.items():
            if r in new_refs:
                new[r] = {"early_start": self.day_to_date(n.es).isoformat(),
                          "early_finish": self.day_to_date(n.ef - 1).isoformat(),
                          "float_after": n.ls - n.es}
                continue
            o = self._acts[r]
            if n.ef != o.ef or r in held:
                per[r] = {"early_finish_before": self.day_to_date(o.ef - 1).isoformat(),
                          "early_finish_after": self.day_to_date(n.ef - 1).isoformat(),
                          "slip_days": n.ef - o.ef, "float_before": o.ls - o.es, "float_after": n.lf - n.ef,
                          "status": status[r]}
                if r in held:
                    # does the inserted work set this activity's dates (rather than another, later predecessor)?
                    ready = max(acts[p].ef for p, _, _ in n.preds if p in new_refs)
                    per[r]["hold_binds"] = (n.ef == ready + resume[r]) if r in resume else (n.es == ready)
        return {"finish_before": self.day_to_date(old_finish - 1).isoformat(),
                "finish_after": self.day_to_date(new_finish - 1).isoformat(),
                "finish_slip_days": new_finish - old_finish,
                "contract_finish": self.contract_finish,
                "project_float_before": cf - old_finish, "project_float_after": cf - new_finish,
                "days_past_contract": max(0, new_finish - cf), "activities": per, "inserted": new}


STAGE_FROM_CHAIN = ("submitted", "approved", "fabricated", "delivered", "erected")


def build_state(design: dict, seed: int = SEED, as_of: dt.date | str | None = None) -> ConstructionState:
    """The construction state at close of business on `as_of` (default AS_OF, the status date).

    Projection, not history: the schedule (CPM) is computed once; every activity, package stage, submittal
    status and element stage is then READ OFF that schedule at the as-of status day, assuming the current
    forecast holds (no progress variance). Dates of past events (RFIs, change events, issued sheets) stay
    anchored to the real data date, so an as-of state differs from today's only in what construction has
    reached. as_of on or before AS_OF's next workday reproduces today's state exactly."""
    rng = random.Random(seed)
    as_of_d = as_of_date(as_of)
    els = {e["id"]: e for e in design["elements"]}
    # the design's lateral frames (FRAME:SMF-A, FRAME:SCBF-1, ...): one connection submittal per frame
    # line, whatever lines the layout has; the first SCBF line carries the revise-and-resubmit story
    smf_frames = sorted(k.split(":", 1)[1] for k, e in els.items() if e["type"] == "frame" and e.get("system") == "SMF")
    scbf_frames = sorted(k.split(":", 1)[1] for k, e in els.items() if e["type"] == "frame" and e.get("system") == "SCBF")
    rr_frame = scbf_frames[0] if scbf_frames else None
    scbf_line = rr_frame.split("-", 1)[1] if rr_frame else ""
    scbf_cols = sorted(k[4:] for k, e in els.items() if e["type"] == "column" and "scbf_column" in (e.get("roles") or []))
    # the RFI narratives name a real element of the design's braced frame: an interior braced-frame column,
    # an L2 brace of the first braced line and its collector girder
    rfi_col = next((c for c in scbf_cols if c[:-1] == scbf_line and c[-1] in "BC"), scbf_cols[0] if scbf_cols else "3B")
    rfi_brace = next((k for k in sorted(els) if k.startswith(f"BR-L2-{scbf_line}-") and k.endswith("-N")), "BR-L2-3-AB-N")
    rfi_coll = next((k for k in sorted(els) if k.startswith(f"G-L2-{scbf_line}-") and "collector" in (els[k].get("roles") or [])),
                    "G-L2-3-BC")
    rels = design["relations"]

    def seq_of_x(x: float) -> str:
        return "S1" if x <= 60.0 + 1e-6 else "S2"

    def mid_x(e) -> float:
        if "p1" in e and "p2" in e:
            return (e["p1"][0] + e["p2"][0]) / 2
        return e.get("x", 0.0)

    lvl_top = {"L1": "L2", "L2": "L3", "L3": "RF"}
    # ---- element -> (level package, sequence)
    member_pkg: dict[str, tuple[str, str]] = {}
    for e in els.values():
        t = e["type"]
        if t in ("beam", "girder"):
            member_pkg[e["id"]] = (e["level"], seq_of_x(mid_x(e)))
        elif t == "column":
            member_pkg[e["id"]] = ("L2", seq_of_x(e["x"]))
        elif t == "brace":
            member_pkg[e["id"]] = (lvl_top[e["level"]], seq_of_x(mid_x(e)))
    fdn_seq: dict[str, str] = {}
    for e in els.values():
        if e["type"] in ("footing", "pier", "grade_beam"):
            fdn_seq[e["id"]] = seq_of_x(mid_x(e))
        elif e["type"] == "connection" and e["id"].startswith("BP-"):
            fdn_seq[e["id"]] = seq_of_x(e["x"])
    conn_member = {e["id"]: e["member"] for e in els.values() if e["type"] == "connection" and e.get("member")}

    # ---- schedule (activities first: package stages are read off it)
    A: dict[str, Activity] = {}

    def act(ref, name, wbs, dur, preds=(), pkg=None):
        A[ref] = Activity(ref, name, wbs, dur, [(p if isinstance(p, tuple) else (p, "FS", 0)) for p in preds], [], pkg)
        return ref

    LV = [("L2", "Level 2"), ("L3", "Level 3"), ("RF", "Roof")]
    SQ = [("S1", "Seq 1 (grid 1-3)"), ("S2", "Seq 2 (grid 3-5)")]
    act("MS-NTP", "Notice to proceed", "1.0 Milestones", 0)
    act("MOB", "Mobilization and site layout", "2.0 Sitework", 5, ["MS-NTP"])
    # foundations
    act("DET-AR", "Anchor rod / base plate submittal: prepare", "3.1 Foundations - submittals", 6, ["MS-NTP"], "SUB-AR")
    act("REV-AR", "Anchor rod / base plate submittal: EOR review", "3.1 Foundations - submittals", 10, ["DET-AR"], "SUB-AR")
    act("FAB-AR", "Anchor rods and base plates: fabricate", "3.2 Foundations - procurement", 6, ["REV-AR"], "SUB-AR")
    act("DEL-AR", "Anchor rods: deliver", "3.2 Foundations - procurement", 1, ["FAB-AR"], "SUB-AR")
    act("DET-MIX", "Foundation concrete mix design: prepare", "3.1 Foundations - submittals", 4, ["MS-NTP"], "SUB-MIX")
    act("REV-MIX", "Foundation concrete mix design: review", "3.1 Foundations - submittals", 7, ["DET-MIX"], "SUB-MIX")
    for s, sl in SQ:
        prev_det = [] if s == "S1" else ["DET-RB-S1"]
        act(f"DET-RB-{s}", f"Foundation rebar shop drawings {sl}: detail", "3.1 Foundations - submittals", 8,
            ["MS-NTP"] + prev_det, f"SUB-RB-{s}")
        act(f"REV-RB-{s}", f"Foundation rebar shop drawings {sl}: EOR review", "3.1 Foundations - submittals", 10,
            [f"DET-RB-{s}"], f"SUB-RB-{s}")
        act(f"FAB-RB-{s}", f"Foundation rebar {sl}: fabricate", "3.2 Foundations - procurement", 5, [f"REV-RB-{s}"], f"SUB-RB-{s}")
        act(f"DEL-RB-{s}", f"Foundation rebar {sl}: deliver", "3.2 Foundations - procurement", 1, [f"FAB-RB-{s}"], f"SUB-RB-{s}")
        crew = [] if s == "S1" else ["FDN-S1"]
        act(f"FDN-{s}", f"Footings, piers, grade beams {sl}: excavate, form, set rods, pour", "3.3 Foundations - construct",
            12, [f"DEL-RB-{s}", "DEL-AR", "REV-MIX", "MOB"] + crew, f"SUB-RB-{s}")
    # steel: frame-line connection submittals gate the first fabrication
    frame_subs = [(fl, f"SMF line {fl[4:]} moment connections (RBS)") for fl in smf_frames] + \
                 [(fl, f"SCBF line {fl[5:]} brace gusset connections") for fl in scbf_frames]
    for fl, nm in frame_subs:
        act(f"DET-{fl}", f"{nm}: detail", "4.1 Steel - submittals", 10, ["MS-NTP"], f"SUB-{fl}")
        act(f"REV-{fl}", f"{nm}: EOR review" + (" (rev 0 R&R, rev 1)" if fl == rr_frame else ""),
            "4.1 Steel - submittals", 20 if fl == rr_frame else 10, [f"DET-{fl}"], f"SUB-{fl}")
    prev = None
    pkgs_order = [(lv, s) for lv, _ in LV for s, _ in SQ]
    for i, (lv, s) in enumerate(pkgs_order):
        lname, sname = dict(LV)[lv], dict(SQ)[s]
        k = f"ST-{lv}-{s}"
        pkg = f"SUB-{k}"
        act(f"DET-{k}", f"Steel shop drawings {lname} {sname}: detail", "4.1 Steel - submittals",
            14 if i == 0 else 9, ["MS-NTP"] + ([f"DET-{prev}"] if prev else []), pkg)
        act(f"REV-{k}", f"Steel shop drawings {lname} {sname}: EOR review", "4.1 Steel - submittals", 10, [f"DET-{k}"], pkg)
        fab_pred = [f"REV-{k}"] + ([f"FAB-{prev}"] if prev else [f"REV-{fl}" for fl, _ in frame_subs])
        act(f"FAB-{k}", f"Steel {lname} {sname}: fabricate", "4.2 Steel - fabrication", 8, fab_pred, pkg)
        del_pred = [f"FAB-{k}"] + ([(f"ERECT-{prev}", "SS", 4)] if prev else [])
        act(f"DEL-{k}", f"Steel {lname} {sname}: deliver", "4.3 Steel - delivery", 2, del_pred, pkg)
        er_pred = [f"DEL-{k}"] + ([f"ERECT-{prev}"] if prev else [])
        if lv == "L2":
            er_pred.append((f"FDN-{s}", "FS", 5))   # 5-day cure before setting columns
        act(f"ERECT-{k}", f"Steel {lname} {sname}: erect, plumb, bolt-up", "4.4 Steel - erection", 9, er_pred, pkg)
        prev = k
    # deck + slabs
    act("DET-DK-FL", "Floor deck shop drawings: detail", "5.1 Deck - submittals", 8, ["REV-ST-L2-S1"], "SUB-DK-FL")
    act("REV-DK-FL", "Floor deck shop drawings: EOR review", "5.1 Deck - submittals", 10, ["DET-DK-FL"], "SUB-DK-FL")
    act("FAB-DK-FL", "Floor deck: manufacture", "5.2 Deck - procurement", 15, ["REV-DK-FL"], "SUB-DK-FL")
    act("DET-DK-RF", "Roof deck shop drawings: detail", "5.1 Deck - submittals", 8, ["DET-DK-FL", ("REV-ST-RF-S1", "SS", 0)], "SUB-DK-RF")
    act("REV-DK-RF", "Roof deck shop drawings: EOR review", "5.1 Deck - submittals", 10, ["DET-DK-RF"], "SUB-DK-RF")
    act("FAB-DK-RF", "Roof deck: manufacture", "5.2 Deck - procurement", 15, ["REV-DK-RF"], "SUB-DK-RF")
    for lv, lname in LV:
        fab = "FAB-DK-RF" if lv == "RF" else "FAB-DK-FL"
        pkg = "SUB-DK-RF" if lv == "RF" else "SUB-DK-FL"
        act(f"DEL-DK-{lv}", f"{lname} deck: deliver", "5.2 Deck - procurement", 1, [fab, (f"ERECT-ST-{lv}-S1", "SS", 0)], pkg)
        act(f"DECK-{lv}", f"{lname} deck: lay, weld, studs", "5.3 Deck - install", 10 if lv != "RF" else 8,
            [f"DEL-DK-{lv}", (f"ERECT-ST-{lv}-S1", "FS", 0), (f"ERECT-ST-{lv}-S2", "SS", 3)], pkg)
        if lv != "RF":
            act(f"SLAB-{lv}", f"{lname} slab on deck: reinforce and pour", "5.4 Slabs", 6, [f"DECK-{lv}", f"ERECT-ST-{lv}-S2"])
    act("DET-SFRM", "SFRM product data + thickness schedule: prepare", "6.1 Fireproofing - submittals", 6,
        [("ERECT-ST-L3-S1", "SS", 0)], "SUB-SFRM")
    act("REV-SFRM", "SFRM submittal: architect / EOR review", "6.1 Fireproofing - submittals", 10, ["DET-SFRM"], "SUB-SFRM")
    act("SFRM", "Apply SFRM to framing", "6.2 Fireproofing - apply", 15, ["REV-SFRM", "SLAB-L3", "DECK-RF"], "SUB-SFRM")
    act("MS-DRYIN", "Building dried-in", "1.0 Milestones", 0, ["DECK-RF"])
    act("ENCL", "Enclosure, MEP rough-in and interiors (by others)", "7.0 Follow-on trades", 85, ["MS-DRYIN", "SFRM", "SLAB-L2"])
    act("MS-SC", "Substantial completion", "1.0 Milestones", 0, ["ENCL"])

    planned_finish = cpm(A)
    contract_day = planned_finish + 12           # 12 working days of project float in the contract
    cpm(A, finish_constraint=contract_day)
    # data date: the morning after AS_OF; picked as 3 days into Level 3 Seq 1 erection
    data_day = A["ERECT-ST-L3-S1"].es + 3
    day0 = add_workdays(next_workday(AS_OF), -data_day)
    # status day: the working-day index whose MORNING is the state reported (close of business on as_of)
    status_day = data_day + workdays_between(next_workday(AS_OF), next_workday(as_of_d))

    def d2s(n: int) -> str:
        return add_workdays(day0, n).isoformat()

    def act_status(a: Activity, day: int | None = None) -> tuple[str, float]:
        day = status_day if day is None else day
        if a.ef <= day and not (a.dur == 0 and a.es > day):
            return "complete", 100.0
        if a.es < day:
            return "in_progress", round(100.0 * (day - a.es) / max(a.dur, 1), 1)
        return "not_started", 0.0

    def chain_stage(chain: list[str]) -> tuple[str, list[str]]:
        """chain = [DET, REV, FAB?, DEL?, INSTALL?]; stage read off the schedule."""
        det, rev, *rest = chain
        fab, dlv, inst = (rest + [None, None, None])[:3]
        st = {r: act_status(A[r])[0] for r in chain if r}
        why = []
        if inst and st[inst] == "complete":
            return "erected", why
        if dlv and st[dlv] == "complete":
            if inst and st[inst] == "in_progress":
                why.append(f"{A[inst].name} is {act_status(A[inst])[1]:.0f}% complete")
            return "delivered", why
        if fab and st[fab] == "complete":
            return "fabricated", why
        if st[rev] == "complete":
            if fab and st[fab] == "in_progress":
                why.append(f"{A[fab].name} in progress ({act_status(A[fab])[1]:.0f}%)")
            return "approved", why
        if st[rev] == "in_progress" or st[det] == "complete":
            return "submitted", why
        return "design", why

    # ---- element chains (what activities an element passes through, in order)
    chains: dict[str, list[str]] = {}
    downstream: dict[str, list[str]] = {}   # not-yet-done successors used when an erected element is reworked
    for eid, (lv, s) in member_pkg.items():
        k = f"ST-{lv}-{s}"
        chains[eid] = [f"DET-{k}", f"REV-{k}", f"FAB-{k}", f"DEL-{k}", f"ERECT-{k}"]
        downstream[eid] = [f"ERECT-{k}", f"DECK-{lv}"] + ([f"SLAB-{lv}"] if lv != "RF" else ["MS-DRYIN"])
    for cid, m in conn_member.items():
        if m in chains:
            chains[cid] = list(chains[m])
            downstream[cid] = list(downstream[m])
    for eid, s in fdn_seq.items():
        if eid.startswith("BP-"):
            chains[eid] = ["DET-AR", "REV-AR", "FAB-AR", "DEL-AR", f"FDN-{s}"]
        else:
            chains[eid] = [f"DET-RB-{s}", f"REV-RB-{s}", f"FAB-RB-{s}", f"DEL-RB-{s}", f"FDN-{s}"]
        downstream[eid] = [f"FDN-{s}", f"ERECT-ST-L2-{s}", "DECK-L2", "SLAB-L2"]
    for lv, _ in LV:
        dk = f"DK-{lv}"
        if dk in els:
            f_ = "RF" if lv == "RF" else "FL"
            chains[dk] = [f"DET-DK-{f_}", f"REV-DK-{f_}", f"FAB-DK-{f_}", f"DEL-DK-{lv}", f"DECK-{lv}"]
            downstream[dk] = [f"DECK-{lv}"] + ([f"SLAB-{lv}"] if lv != "RF" else ["MS-DRYIN"])
    for eid, ch in chains.items():
        for r in ch:
            if eid not in A[r].element_ids:
                A[r].element_ids.append(eid)
    for lv, _ in LV:
        if lv != "RF":
            A[f"SLAB-{lv}"].element_ids = [f"DK-{lv}"]
    A["SFRM"].element_ids = sorted(e for e in member_pkg if els[e]["type"] in ("beam", "girder", "column"))

    # ---- submittal packages
    subs: list[dict] = []
    sfrm_members = [e for e in member_pkg if els[e]["type"] in ("beam", "girder", "column")]

    def frame_elems(fl: str) -> list[str]:
        mem = [e["id"] for e in els.values() if e.get("frame") == fl or fl in (e.get("frames") or [])]
        cons = [c for c, m in conn_member.items() if m in mem and els[c]["conn_type"].rstrip("*") in ("MC-1", "BG-1", "BG-2", "BG-3", "DC-1", "DC-2", "DC-3")]
        return sorted(mem) + sorted(cons)

    def add_sub(ref, number, title, spec, spec_title, kind, chain, elem_ids, company, level=None, seq=None,
                revision=0, response_override=None):
        stage, why = chain_stage(chain)
        det, rev = A[chain[0]], A[chain[1]]
        rev_status = act_status(rev)[0]
        if stage == "design":
            status = "draft"
        elif stage == "submitted":
            status = "submitted"
        else:
            status = stage
        response = None
        # today's responses come from the seeded rng in the same order as ever (as-of states keep them); a review
        # that only completes in a projected state gets a deterministic per-package choice
        drawn = None
        if act_status(rev, data_day)[0] == "complete" and not response_override:
            drawn = rng.choice(["Approved", "Approved", "Approved as Noted"])
        if rev_status == "complete":
            response = response_override or drawn or ("Approved", "Approved", "Approved as Noted")[
                int(hashlib.sha1(ref.encode()).hexdigest()[:4], 16) % 3]
        dates = {
            "created": d2s(det.es),
            "submitted": d2s(rev.es) if act_status(rev)[0] != "not_started" else None,
            "due": d2s(rev.ef - 1),
            "returned": d2s(rev.ef - 1) if rev_status == "complete" else None,
            "required_on_job": d2s(A[chain[-1]].es) if len(chain) > 2 and chain[-1] else None,
        }
        if len(chain) > 3 and chain[2] and chain[3]:
            fab, dlv = A[chain[2]], A[chain[3]]
            dates["fabrication_complete"] = d2s(fab.ef - 1) if act_status(fab)[0] == "complete" else None
            dates["anticipated_delivery"] = d2s(dlv.es)
            dates["actual_delivery"] = d2s(dlv.ef - 1) if act_status(dlv)[0] == "complete" else None
        bic = {"draft": company, "submitted": PROJECT["companies"]["eor"]}.get(status, PROJECT["companies"]["gc"])
        subs.append({"ref": ref, "number": number, "title": title, "spec_section": spec, "spec_title": spec_title,
                     "package_kind": kind, "level": level, "sequence": seq, "status": status, "stage": stage,
                     "stage_notes": why, "revision": revision, "response": response, "ball_in_court": bic,
                     "responsible_contractor": company, "submittal_manager": PROJECT["people"]["gc_pm"],
                     "reviewer": PROJECT["people"]["eor"], "element_ids": sorted(set(elem_ids)),
                     "activity_refs": [c for c in chain if c], "dates": dates})

    C = PROJECT["companies"]
    fdn_all = sorted(fdn_seq)
    for i, (s, sl) in enumerate(SQ):
        add_sub(f"SUB-RB-{s}", f"03 20 00-00{i + 1}", f"Foundation reinforcing shop drawings - {sl}", "03 20 00",
                "Concrete Reinforcing", "rebar_shop_drawings",
                [f"DET-RB-{s}", f"REV-RB-{s}", f"FAB-RB-{s}", f"DEL-RB-{s}", f"FDN-{s}"],
                [e for e in fdn_all if fdn_seq[e] == s and not e.startswith("BP-")], C["concrete"], seq=s)
    add_sub("SUB-MIX", "03 30 00-001", "Foundation concrete mix design (4,000 psi NW)", "03 30 00",
            "Cast-in-Place Concrete", "product_data", ["DET-MIX", "REV-MIX", None, None, "FDN-S2"],
            [e for e in fdn_all if not e.startswith("BP-")], C["concrete"])
    add_sub("SUB-AR", "05 12 00-001", "Anchor rods and base plates - setting plan and details", "05 12 00",
            "Structural Steel Framing", "anchor_rods", ["DET-AR", "REV-AR", "FAB-AR", "DEL-AR", "FDN-S2"],
            [e for e in fdn_all if e.startswith("BP-")], C["steel"])
    n = 2
    for fl, nm in [(fl, f"Special moment frame line {fl[4:]} - RBS moment connections (MC-1)") for fl in smf_frames] + \
                  [(fl, f"Special concentrically braced frame line {fl[5:]} - brace gusset connections") for fl in scbf_frames]:
        add_sub(f"SUB-{fl}", f"05 12 00-{n:03d}", nm, "05 12 00", "Structural Steel Framing", "connection_design",
                [f"DET-{fl}", f"REV-{fl}"], frame_elems(fl), C["steel"], revision=1 if fl == rr_frame else 0,
                response_override="Approved as Noted" if fl == rr_frame else "Approved")
        n += 1
    for lv, s in pkgs_order:
        k = f"ST-{lv}-{s}"
        elem = [e for e, p in member_pkg.items() if p == (lv, s)]
        elem += [c for c, m in conn_member.items() if m in elem]
        add_sub(f"SUB-{k}", f"05 12 00-{n:03d}", f"Structural steel shop drawings - {dict(LV)[lv]} framing, {dict(SQ)[s]}",
                "05 12 00", "Structural Steel Framing", "steel_shop_drawings",
                [f"DET-{k}", f"REV-{k}", f"FAB-{k}", f"DEL-{k}", f"ERECT-{k}"], elem, C["steel"], level=lv, seq=s)
        n += 1
    add_sub("SUB-DK-FL", "05 31 00-001", "Composite floor deck - Levels 2 and 3 (3\" 20 ga)", "05 31 00", "Steel Decking",
            "deck_shop_drawings", ["DET-DK-FL", "REV-DK-FL", "FAB-DK-FL", "DEL-DK-L2", "DECK-L2"],
            ["DK-L2", "DK-L3"], C["deck"])
    add_sub("SUB-DK-RF", "05 31 00-002", "Roof deck (1-1/2\" 20 ga type B)", "05 31 00", "Steel Decking",
            "deck_shop_drawings", ["DET-DK-RF", "REV-DK-RF", "FAB-DK-RF", "DEL-DK-RF", "DECK-RF"], ["DK-RF"], C["deck"])
    add_sub("SUB-SFRM", "07 81 00-001", "Spray-applied fireproofing - product data and thickness schedule", "07 81 00",
            "Applied Fireproofing", "product_data", ["DET-SFRM", "REV-SFRM", None, None, "SFRM"], sfrm_members, C["deck"])

    # ---- element index (stage per element from its own chain)
    elem_subs: dict[str, list[str]] = {}
    for s in subs:
        for e in s["element_ids"]:
            elem_subs.setdefault(e, []).append(s["ref"])
    element_index: dict[str, dict] = {}
    for eid, ch in chains.items():
        stage, why = chain_stage(ch)
        e = els.get(eid, {})
        lv, sq = member_pkg.get(eid) or member_pkg.get(conn_member.get(eid, ""), (None, None))
        if eid in fdn_seq:
            sq = fdn_seq[eid]
        reasons = list(why)
        if eid in fdn_seq and stage == "erected":
            reasons.insert(0, "foundation poured" if not eid.startswith("BP-") else "anchor rods cast in, base plate set")
        element_index[eid] = {"stage": stage, "chain": ch, "downstream": downstream.get(eid, []),
                              "submittals": elem_subs.get(eid, []), "level": lv, "sequence": sq,
                              "type": e.get("type"), "notes": reasons}

    # ---- RFIs (about specific elements / connections)
    def frames_into(src, end):
        return next((r["dst"] for r in rels if r["src"] == src and r["kind"] == "frames-into" and r.get("end") == end), None)

    dd = data_day
    rfi_specs = [
        ("RFI-001", f"Anchor rod projection at base plate BP-{rfi_col} vs pier P-{rfi_col} ties",
         f"Pier P-{rfi_col} top ties conflict with the anchor rod template at BP-{rfi_col} (SCBF column). Confirm tie spacing may "
         "open to 6 in. within 8 in. of the pier top.",
         "Ties may be relocated as proposed; keep (2) #4 ties within top 5 in. See SK-S-01.",
         "closed", [f"BP-{rfi_col}", f"P-{rfi_col}", f"COL-{rfi_col}"], -95, -88, "S-501", "03 20 00", "no", "no"),
        ("RFI-002", "Shear tab ST-5 at G-L3-2-BC to COL-2B: tab clashes with column flange stiffener",
         "Detailer reports the ST-5 tab for girder G-L3-2-BC at COL-2B lands on the stiffener of the SMF-adjacent "
         "column detail. Request alternate tab location or extended tab.",
         None, "open", ["CX-G-L3-2-BC-i", "G-L3-2-BC", "COL-2B"], -6, None, "S-401", "05 12 00", "tbd", "tbd"),
        ("RFI-003", f"SCBF gusset BG-3 at {rfi_brace}: gusset vs deck rib at Level 3",
         f"Gusset plate BG-3 at the top of {rfi_brace} projects 2 in. above top of steel into the deck flute at "
         f"{frames_into(rfi_brace, 'j')}. Confirm deck closure / notch acceptable.",
         "Notch deck and provide pour stop closure per detail 7/S-402; gusset geometry unchanged.",
         "answered", [f"CX-{rfi_brace}-j", rfi_brace, frames_into(rfi_brace, "j")], -30, -18,
         "S-402", "05 12 00", "no", "no"),
        ("RFI-004", "Footing F-2B top of footing vs storm line crossing",
         "Civil storm line crosses under F-2B at el. -3.5 ft. Request lowering F-2B by 1'-0\".",
         "Lower F-2B 1'-0\"; extend pier P-2B; footing size unchanged. Cost via change event CE-002.",
         "closed", ["F-2B", "P-2B"], -110, -104, "S-101", "03 30 00", "yes", "no"),
        ("RFI-005", "RBS cut geometry at B-L3-A-23 (MC-1)",
         "Confirm RBS cut dimensions a, b, c for MC-1 at beam B-L3-A-23; shop drawing shows c = 2.0 in.",
         "Use a = 5 in., b = 18 in., c = 1.75 in. per AISC 358 Ch. 5 calc E3.",
         "answered", ["B-L3-A-23", "CX-B-L3-A-23-i", "CX-B-L3-A-23-j"], -22, -15, "S-301", "05 12 00", "no", "no"),
        ("RFI-006", "RTU curb support framing at roof bay 3-4 / A-B",
         "Mechanical RTU-2 curb is 14 ft x 8 ft; infill beams B-RF-34-AB1/AB2 at 10 ft spacing do not catch the curb. "
         "Provide curb support framing.",
         None, "open", ["B-RF-34-AB1", "B-RF-34-AB2", "G-RF-3-AB", "G-RF-4-AB"], -4, None, "S-203", "05 12 00", "tbd", "tbd"),
        ("RFI-007", f"Drag connection DC-1 at collector {rfi_coll}: bolt count",
         "DC-1 schedule calls (6) bolts; collector force table implies (8). Confirm.",
         None, "draft", [f"CX-{rfi_coll}-i", f"CX-{rfi_coll}-j", rfi_coll], -1, None, "S-402", "05 12 00", "tbd", "tbd"),
    ]
    rfis = []
    for ref, subj, q, ans, st, eids, d_open, d_ans, sheet, spec, ci, si in rfi_specs:
        eids = [e for e in eids if e in els]
        rfis.append({"ref": ref, "number": ref, "subject": subj, "question": q, "answer": ans, "status": st,
                     "element_ids": eids, "drawing_number": sheet, "spec_section": spec,
                     "cost_impact": ci, "schedule_impact": si,
                     "assignee": PROJECT["people"]["eor"], "rfi_manager": PROJECT["people"]["gc_pm"],
                     "received_from": PROJECT["people"]["steel_pm"] if spec.startswith("05") else PROJECT["people"]["concrete_pm"],
                     "ball_in_court": {"draft": "Creator", "open": "Assignees"}.get(st, "RFI Manager"),
                     "dates": {"created": d2s(dd + d_open), "due": d2s(dd + d_open + 7),
                               "answered": d2s(dd + d_ans) if d_ans is not None else None,
                               "closed": d2s(dd + d_ans + 2) if st == "closed" and d_ans is not None else None}})

    # ---- cost codes + budget
    cost_codes = [
        {"code": "03 20 00", "name": "Concrete Reinforcing", "division": "03 Concrete"},
        {"code": "03 30 00", "name": "Cast-in-Place Concrete - Foundations", "division": "03 Concrete"},
        {"code": "03 31 00", "name": "Structural Concrete - Slab on Deck", "division": "03 Concrete"},
        {"code": "05 12 00", "name": "Structural Steel Framing", "division": "05 Metals"},
        {"code": "05 12 10", "name": "Structural Steel Connections", "division": "05 Metals"},
        {"code": "05 31 00", "name": "Steel Decking", "division": "05 Metals"},
        {"code": "07 81 00", "name": "Applied Fireproofing", "division": "07 Thermal and Moisture Protection"},
        {"code": "01 31 00", "name": "Project Management - Engineering Services", "division": "01 General Requirements"},
    ]
    budget: list[dict] = []

    def line(ref, code, desc, qty, unit, unit_cost, elem_ids, basis):
        budget.append({"ref": ref, "cost_code": code, "description": desc, "quantity": round(qty, 2), "unit": unit,
                       "unit_cost": unit_cost, "amount": round(qty * unit_cost, 2), "element_ids": sorted(elem_ids),
                       "basis": basis, "estimate": True})

    for lv, s in pkgs_order:
        for fam in ("W", "HSS"):
            mem = [e for e, p in member_pkg.items() if p == (lv, s) and els[e]["size"].upper().startswith(fam)]
            if not mem:
                continue
            lb = 0.0
            for e in mem:
                lb += shape_props(els[e]["size"])["lb_per_ft"] * _length_ft(els[e])
            rate = steel_rate(els[mem[0]]["size"])
            line(f"BL-05-{lv}-{s}-{fam}", "05 12 00", f"Structural steel {fam} - {dict(LV)[lv]} {dict(SQ)[s]}",
                 lb / 2000.0, "ton", rate, mem,
                 f"sum(weight lb/ft x length ft) / 2000 over {len(mem)} members x ${rate:,.0f}/ton (assumed, F+E)")
    by_type: dict[str, list[str]] = {}
    for e in els.values():
        if e["type"] == "connection":
            by_type.setdefault(e["conn_type"].rstrip("*"), []).append(e["id"])
    for t, ids in sorted(by_type.items()):
        line(f"BL-0510-{t}", "05 12 10", f"Connections {t}", len(ids), "ea", conn_rate(t), ids,
             f"{len(ids)} x ${conn_rate(t):,.0f}/each (assumed)")
    for s, sl in SQ:
        ids = [e for e in fdn_all if fdn_seq[e] == s and not e.startswith("BP-")]
        cy = sum(_concrete_cy(els[e]) for e in ids)
        line(f"BL-03-FDN-{s}", "03 30 00", f"Foundations (footings, piers, grade beams) - {sl}", cy, "cy",
             RATES["foundation_concrete_usd_per_cy"], ids,
             f"footings B^2 x h, piers b^2 x 2.5 ft, grade beams b x h x span -> cy x ${RATES['foundation_concrete_usd_per_cy']:,.0f}/cy all-in (assumed)")
    b = design.get("building", {})
    xs = [p for _, p in b.get("grids", {}).get("x", [])] or [0, 120]
    ys = [p for _, p in b.get("grids", {}).get("y", [])] or [0, 85]
    plate = (max(xs) - min(xs)) * (max(ys) - min(ys))
    for lv, lname in LV:
        line(f"BL-0531-{lv}", "05 31 00", f"{lname} deck", plate, "sf", RATES["steel_deck_usd_per_sf"], [f"DK-{lv}"],
             f"floor plate {max(xs) - min(xs):.0f} x {max(ys) - min(ys):.0f} ft x ${RATES['steel_deck_usd_per_sf']}/sf (assumed)")
        if lv != "RF":
            line(f"BL-0331-{lv}", "03 31 00", f"{lname} slab on deck", plate, "sf", RATES["slab_on_deck_usd_per_sf"],
                 [f"DK-{lv}"], f"floor plate x ${RATES['slab_on_deck_usd_per_sf']}/sf (assumed)")
    sf = sum(shape_props(els[e]["size"])["perimeter_ft"] * _length_ft(els[e]) for e in sfrm_members)
    line("BL-0781", "07 81 00", "SFRM to beams, girders and columns", sf, "sf", RATES["fireproofing_usd_per_sf"], sfrm_members,
         f"sum(section perimeter x length) x ${RATES['fireproofing_usd_per_sf']}/sf (assumed)")

    # ---- change events / orders (existing)
    def mem_cost(ids, frac):
        return sum(shape_props(els[e]["size"])["lb_per_ft"] * _length_ft(els[e]) / 2000.0 * steel_rate(els[e]["size"])
                   for e in ids if e in els) * frac
    mech = [e for e in ("B-RF-34-AB1", "B-RF-34-AB2", "G-RF-3-AB", "G-RF-4-AB") if e in els]
    line_a = sorted(e for e in els if els[e]["type"] == "beam" and els[e].get("line") == "A" and els[e]["level"] in ("L2", "L3"))
    ce = [
        {"ref": "CE-001", "number": "001", "title": "RTU-2 weight increase: roof framing bay 3-4 / A-B upsized",
         "description": "Owner-directed mechanical change raised RTU-2 operating weight; roof infill and girders in bay "
                        "3-4 / A-B redesigned (calc B4).", "status": "approved", "reason": "Owner Change",
         "element_ids": mech, "line_items": [
             {"cost_code": "05 12 00", "description": "Added steel weight (20% of bay members)", "amount": round(mem_cost(mech, 0.20), 2)},
             {"cost_code": "01 31 00", "description": "EOR redesign (4 calc records)", "amount": 4 * RATES["eng_redesign_usd_per_calc_record"]}],
         "created": d2s(dd - 70), "co_refs": ["CO-001"]},
        {"ref": "CE-002", "number": "002", "title": "Lower footing F-2B 1'-0\" for storm line crossing (RFI-004)",
         "description": "Additional excavation, lean fill and pier extension at F-2B.", "status": "approved",
         "reason": "Unforeseen Condition", "element_ids": ["F-2B", "P-2B"], "line_items": [
             {"cost_code": "03 30 00", "description": "Pier extension 1 ft + excavation",
              "amount": round(((24 / 12) ** 2 * 1.0 / 27.0) * RATES["foundation_concrete_usd_per_cy"] + 1800.0, 2)}],
         "created": d2s(dd - 103), "co_refs": ["CO-002"]},
        {"ref": "CE-003", "number": "003", "title": "Curtain wall embed plates at slab edge, line A, Levels 2-3",
         "description": "Architect bulletin ASI-04 adds curtain wall anchor embeds on grid line A spandrel beams.",
         "status": "pending", "reason": "Design Development", "element_ids": line_a, "line_items": [
             {"cost_code": "05 12 00", "description": f"Embed plates welded to {len(line_a)} spandrel beams (ROM)",
              "amount": float(len(line_a) * 950)}],
         "created": d2s(dd - 12), "co_refs": ["CO-003"]},
        {"ref": "CE-004", "number": "004", "title": "Field-modify shear tab at G-L3-2-BC / COL-2B (RFI-002)",
         "description": "Potential cost if RFI-002 answer requires an extended tab.", "status": "draft",
         "reason": "Design Clarification", "element_ids": ["CX-G-L3-2-BC-i", "G-L3-2-BC", "COL-2B"], "line_items": [
             {"cost_code": "05 12 10", "description": "Extended tab (ROM)", "amount": conn_rate("ST-5") * 1.5}],
         "created": d2s(dd - 5), "co_refs": []},
    ]
    for c in ce:
        c["amount"] = round(sum(li["amount"] for li in c["line_items"]), 2)
    cos = [
        {"ref": "CO-001", "number": "001", "title": ce[0]["title"], "status": "approved", "co_type": "prime",
         "change_event_ref": "CE-001", "amount": ce[0]["amount"], "schedule_days": 0, "element_ids": mech,
         "created": d2s(dd - 65), "approved": d2s(dd - 50)},
        {"ref": "CO-002", "number": "002", "title": ce[1]["title"], "status": "approved", "co_type": "prime",
         "change_event_ref": "CE-002", "amount": ce[1]["amount"], "schedule_days": 1, "element_ids": ["F-2B", "P-2B"],
         "created": d2s(dd - 100), "approved": d2s(dd - 96)},
        {"ref": "CO-003", "number": "003", "title": ce[2]["title"], "status": "pending", "co_type": "potential",
         "change_event_ref": "CE-003", "amount": ce[2]["amount"], "schedule_days": 0, "element_ids": line_a,
         "created": d2s(dd - 8), "approved": None},
    ]

    # ---- incoming items waiting on the EOR (inbox_synth: unlinked, so they touch no element until read)
    from .inbox_synth import incoming
    inbox = incoming(els, d2s, dd, PROJECT["people"], PROJECT["companies"])
    rfis += inbox["rfis"]
    ce += inbox["change_events"]
    cos += inbox["change_orders"]

    # ---- sheets
    def ids_where(pred):
        return sorted(e["id"] for e in els.values() if pred(e))
    is_fdn = lambda e: e["type"] in ("footing", "pier", "grade_beam") or e["id"].startswith("BP-")  # noqa: E731
    sheets = [
        ("S-001", "General notes and design criteria", []),
        ("S-101", "Foundation plan", ids_where(is_fdn)),
        ("S-201", "Level 2 framing plan", ids_where(lambda e: e.get("level") == "L2" and e["type"] in ("beam", "girder")) + ["DK-L2"]),
        ("S-202", "Level 3 framing plan", ids_where(lambda e: e.get("level") == "L3" and e["type"] in ("beam", "girder")) + ["DK-L3"]),
        ("S-203", "Roof framing plan", ids_where(lambda e: e.get("level") == "RF" and e["type"] in ("beam", "girder")) + ["DK-RF"]),
        ("S-301", "Special moment frame elevations - lines A and D",
         ids_where(lambda e: (e.get("frame") or "").startswith("SMF") or any(f.startswith("SMF") for f in e.get("frames") or []))),
        ("S-302", "Braced frame elevation" + ("s" if len(scbf_frames) > 1 else "") + " - line"
         + ("s " if len(scbf_frames) > 1 else " ") + " and ".join(f[5:] for f in scbf_frames),
         ids_where(lambda e: (e.get("frame") or "") in scbf_frames or any(f in scbf_frames for f in e.get("frames") or []))),
        ("S-401", "Typical beam connection details (ST-2 to ST-7)",
         ids_where(lambda e: e["type"] == "connection" and e["conn_type"].startswith("ST"))),
        ("S-402", "Moment, drag and brace connection details",
         ids_where(lambda e: e["type"] == "connection" and e["conn_type"].startswith(("MC", "DC", "BG")))),
        ("S-501", "Foundation details and schedules", ids_where(lambda e: e["type"] in ("footing", "pier", "grade_beam"))),
        ("S-601", "Column schedule and base plates", ids_where(lambda e: e["type"] == "column" or e["id"].startswith("BP-"))),
    ]
    sheet_recs = [{"ref": f"SHT-{n}", "number": n, "title": t, "element_ids": ids, "discipline": "Structural",
                   "revision": "1" if n in ("S-203", "S-402") else "0",
                   "issued": d2s(-20 if n not in ("S-203", "S-402") else dd - 40),
                   "version_set": "IFC Set" if n not in ("S-203", "S-402") else "Bulletin 02"}
                  for n, t, ids in sheets]

    groups: dict[str, list[str]] = {}
    for r in rels:
        if r["kind"] == "member-of" and r["dst"].startswith(("LEVEL:", "GRID:", "FRAME:")) and r["src"] in element_index:
            groups.setdefault(r["dst"], []).append(r["src"])

    # ---- activities out
    activities = []
    for r in _topo(A):
        a = A[r]
        st, pct = act_status(a)
        activities.append({"ref": r, "name": a.name, "wbs": a.wbs, "duration": a.dur, "status": st, "percent_complete": pct,
                           "predecessors": [{"ref": p, "type": t, "lag": lag} for p, t, lag in a.preds],
                           "element_ids": list(a.element_ids), "package_ref": a.package_ref,
                           "early_start": d2s(a.es if a.dur else max(a.es - 1, 0)),
                           "early_finish": d2s(max(a.ef - 1, 0) if not a.dur else a.ef - 1),
                           "late_start": d2s(a.ls if a.dur else max(a.ls - 1, 0)),
                           "late_finish": d2s(max(a.lf - 1, 0)),
                           "total_float": a.ls - a.es, "critical": (a.ls - a.es) <= (contract_day - planned_finish),
                           "actual_start": (d2s(a.es if a.dur else max(a.es - 1, 0)) if st != "not_started" else None),
                           "actual_finish": d2s(max(a.ef - 1, 0)) if st == "complete" else None,
                           "milestone": a.dur == 0})
    st = ConstructionState(
        project={**PROJECT, "as_of": as_of_d.isoformat(), "data_date": d2s(status_day), "start": d2s(0),
                 **({"projected_from": AS_OF.isoformat()} if status_day != data_day else {})},
        rates=RATES, schedule_rules=SCHEDULE_RULES, as_of=as_of_d.isoformat(), elements=els,
        submittals=subs, rfis=rfis, change_events=ce, change_orders=cos, cost_codes=cost_codes, budget_lines=budget,
        activities=activities, sheets=sheet_recs, element_index=element_index,
        contract_finish=d2s(contract_day - 1), forecast_finish=d2s(planned_finish - 1),
        groups=groups, inbox_key=inbox["key"], _acts=A, _day0=day0, _data_day=status_day)
    st._contract_day = contract_day
    return st


def _length_ft(e: dict) -> float:
    if e.get("span_ft"):
        return float(e["span_ft"])
    if "p1" in e and "p2" in e:
        return math.dist(e["p1"], e["p2"])
    if e.get("type") == "column":
        return float(e.get("z1", 0)) - float(e.get("z0", 0))
    return 0.0


def _concrete_cy(e: dict) -> float:
    t = e["type"]
    if t == "footing":
        return footing_cy(e["B_ft"], e["h_in"])
    if t == "pier":
        return (e["b_in"] / 12.0) ** 2 * (e["z1"] - e["z0"]) / 27.0
    if t == "grade_beam":
        return e["b_in"] / 12.0 * e["h_in"] / 12.0 * math.dist(e["p1"][:2], e["p2"][:2]) / 27.0
    return 0.0
