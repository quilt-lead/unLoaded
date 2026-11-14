"""As-of date for impact: what a change costs and slips depends on WHEN it is approved.

ONE projection, used by every consumer: `platforms.get_adapters(design, as_of=D)` builds the adapters
over `synthetic.build_state(design, as_of=D)` - the construction state at close of business on D, read
off the same CPM schedule (activities complete / in progress, package and element stages, submittal
status, float, the CPM re-run's data date). Health (status.construction_status), the change order
(change_order.estimate) and the construction status route all read those adapters, so none of them has
date logic of its own. as_of=None is today's state (byte-identical to before this module existed).

Assumption, stated on every response: the projection assumes the current forecast holds (no progress
variance). A live platform source has no synthetic schedule logic, so its records are served as they
are today (`projected: false` on that adapter).

This module adds the views built on that projection:
  parse(value)                  "today" | "+1w" | "+2w" | "+1m" | "YYYY-MM-DD" -> date (None for today)
  today()                       the date today in US Eastern
  presets()                     the control's presets with their dates
  adapters(design, as_of)       get_adapters(design, as_of=...) (None -> today's cached path)
  boundaries(design, ids, ...)  dates when any of the elements moves to a later construction stage
  timeline(design, estimate_fn, ids, as_of, ...)  cost + slip vs approval date, and the
                                "approve by <date> or it becomes <stage>" line
"""
from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

from .platforms.base import stage_rank
from .platforms.synthetic import AS_OF, add_workdays, next_workday

ET = ZoneInfo("America/New_York")
PRESETS = (("today", "Today", 0), ("+1w", "+1 wk", 7), ("+2w", "+2 wk", 14), ("+1m", "+1 month", 30))
ASSUMPTION = ("projected from the platform schedule assuming the current forecast holds (no progress variance); "
              "stage, float and the CPM data date are read off the schedule at close of business on the as-of date")


def today() -> dt.date:
    return dt.datetime.now(ET).date()


def parse(value: str | None) -> dt.date | None:
    """None / "" / "today" -> None (today's state, no projection); "+1w" "+2w" "+1m" "+Nd" relative to
    today (Eastern); else an ISO date."""
    if value in (None, "", "today"):
        return None
    v = str(value).strip().lower()
    for key, _, days in PRESETS:
        if v == key:
            return today() + dt.timedelta(days=days)
    if v.startswith("+") and v.endswith("d") and v[1:-1].isdigit():
        return today() + dt.timedelta(days=int(v[1:-1]))
    try:
        return dt.date.fromisoformat(v[:10])
    except ValueError:
        raise ValueError(f"as_of must be today, +1w, +2w, +1m, +Nd or YYYY-MM-DD, not {value!r}") from None


def presets() -> list[dict]:
    t = today()
    return [{"key": k, "label": lab, "date": (t + dt.timedelta(days=n)).isoformat()} for k, lab, n in PRESETS]


def is_today(d: dt.date | None) -> bool:
    """True when `d` reads the same state as today (same next workday as the status date)."""
    return d is None or next_workday(d) == next_workday(max(today(), AS_OF))


def adapters(design: dict, as_of: dt.date | None, default=None):
    """The adapters at `as_of`. `default` = a callable returning today's (cached) adapters, used when
    the date reads today's state, so the default path is exactly the existing one."""
    if is_today(as_of) and default is not None:
        return default()
    from .platforms import get_adapters
    return get_adapters(design, as_of=None if is_today(as_of) else as_of)


def describe(ads, as_of: dt.date | None) -> dict:
    """What the as-of means for this adapter set (shown next to every as-of number)."""
    st = next((a.state for a in ads if getattr(a, "state", None) is not None), None)
    return {"as_of": (as_of or today()).isoformat(), "is_today": is_today(as_of),
            "status_date": AS_OF.isoformat(),
            "data_date": st.project.get("data_date") if st is not None else None,
            "projected": st is not None and not is_today(as_of),
            "adapters": [{"name": a.name, "source": getattr(a, "source", "mock"),
                          "projected": getattr(a, "state", None) is not None} for a in ads],
            "assumption": ASSUMPTION if st is not None else
            "live platform source: records are served as they are today (no schedule logic to project)"}


# ------------------------------------------------------------------ stage boundaries
def _state(ads):
    return next((a.state for a in ads if getattr(a, "state", None) is not None), None)


def boundaries(ads, element_ids: list[str], after: dt.date, horizon_days: int = 120) -> list[dict]:
    """Dates (as-of values) on which one of `element_ids` reaches a later construction stage, from
    today's state's chains: an activity completes at close of business on its early finish, so a state
    as of that date already shows it. Each: {date, approve_by (the workday before), element, activity,
    to_stage}. Only for the synthetic state (a live source has no chains: [])."""
    st = _state(ads)
    if st is None:
        return []
    acts = {a["ref"]: a for a in st.activities}
    to_stage = {0: "submitted", 1: "approved", 2: "fabricated", 3: "delivered", 4: "erected"}
    out = []
    end = after + dt.timedelta(days=horizon_days)
    for eid in element_ids:
        ix = st.element_index.get(eid)
        if ix is None:
            continue
        for i, ref in enumerate(ix["chain"]):
            a = acts.get(ref)
            if a is None or a["status"] == "complete" or not a["early_finish"]:
                continue
            stage = to_stage.get(i)   # detail done -> submitted, review done -> approved, ... install done -> erected
            if stage is None:
                continue
            f = dt.date.fromisoformat(a["early_finish"])
            if after < f <= end:
                out.append({"date": f.isoformat(), "approve_by": add_workdays(f, -1).isoformat(),
                            "element": eid, "activity": ref, "activity_name": a["name"], "to_stage": stage})
    return sorted(out, key=lambda b: (b["date"], -stage_rank(b["to_stage"]), b["element"]))


def schedule_dates(ads, element_ids: list[str], after: dt.date, horizon_days: int = 120) -> list[str]:
    """Other dates the estimate can step on: the early finish of every open activity of a submittal
    package that lists one of the elements (a review completing turns a resubmittal from x0.5 to x1),
    and of the elements' downstream activities (where field rework lands)."""
    st = _state(ads)
    if st is None:
        return []
    ids = set(element_ids)
    refs = set()
    for s in st.submittals:
        if ids & set(s["element_ids"]):
            refs |= set(s["activity_refs"])
    for eid in ids:
        ix = st.element_index.get(eid)
        if ix:
            refs |= set(ix["downstream"])
    end = after + dt.timedelta(days=horizon_days)
    out = set()
    for a in st.activities:
        if a["ref"] in refs and a["status"] != "complete" and a["early_finish"]:
            f = dt.date.fromisoformat(a["early_finish"])
            if after < f <= end:
                out.add(f.isoformat())
    return sorted(out)


def schedule_activities_by_date(ads, element_ids: list[str]) -> dict[str, list[str]]:
    """early finish date -> names of the open activities finishing then (the elements' chains, packages
    and downstream activities), to name what drives a jump."""
    st = _state(ads)
    if st is None:
        return {}
    ids = set(element_ids)
    refs = set()
    for s in st.submittals:
        if ids & set(s["element_ids"]):
            refs |= set(s["activity_refs"])
    for eid in ids:
        ix = st.element_index.get(eid)
        if ix:
            refs |= set(ix["chain"]) | set(ix["downstream"])
    out: dict[str, list[str]] = {}
    for a in st.activities:
        if a["ref"] in refs and a["status"] != "complete" and a["early_finish"]:
            out.setdefault(a["early_finish"], []).append(a["name"])
    return out


def timeline(design: dict, estimate_fn, element_ids: list[str], as_of: dt.date | None,
             default_adapters=None, horizon_days: int = 120) -> dict:
    """Cost + slip vs approval date for one change.

    estimate_fn(adapters) -> change-order dict (change_order.estimate output) for the SAME change.
    Evaluated at the presets (today, +1 wk, +2 wk, +1 month), the selected as-of, every stage boundary
    of the elements and every finish of their packages' and downstream activities within the horizon -
    the estimate is a step function of the projected state and those are the steps it reads. Returns {points, next_jump, approve_by_line}."""
    base = today()
    sel = as_of or base
    t0 = adapters(design, None, default_adapters)
    bnds = boundaries(t0, element_ids, after=min(base, sel) - dt.timedelta(days=1), horizon_days=horizon_days)
    dates: dict[str, set] = {}
    for k, lab, n in PRESETS:
        dates.setdefault((base + dt.timedelta(days=n)).isoformat(), set()).add(lab)
    dates.setdefault(sel.isoformat(), set()).add("selected")
    for b in bnds:
        dates.setdefault(b["date"], set()).add("stage boundary")
    for ds in schedule_dates(t0, element_ids, after=min(base, sel) - dt.timedelta(days=1), horizon_days=horizon_days):
        dates.setdefault(ds, set()).add("schedule step")
    points = []
    for ds in sorted(dates):
        d = dt.date.fromisoformat(ds)
        ads = adapters(design, None if is_today(d) else d, default_adapters)
        co = estimate_fn(ads)
        s = co.get("summary") or {}
        st = _state(ads)
        stages = {e: (st.element_index[e]["stage"] if st is not None and e in st.element_index else None) for e in element_ids}
        points.append({"date": ds, "labels": sorted(dates[ds]), "is_today": is_today(d),
                       "total_cost": (s.get("total_cost") or {}).get("value"),
                       "forecast_slip": (s.get("forecast_slip") or {}).get("value"),
                       "finish_delay": (s.get("finish_delay") or {}).get("value"),
                       "worst_stage": s.get("worst_stage"), "stages": stages,
                       "error": co.get("error")})
    cur = next((p for p in points if p["date"] == sel.isoformat()), None)
    acts_at = schedule_activities_by_date(t0, element_ids)
    jumps = []   # every later point that is worse than the point before it
    if cur is not None:
        prev = cur
        for p in points:
            if p["date"] <= cur["date"]:
                continue
            if (p["total_cost"] or 0) > (prev["total_cost"] or 0) + 0.5 or (p["forecast_slip"] or 0) > (prev["forecast_slip"] or 0):
                drivers = [{"element": e, "from": prev["stages"].get(e), "to": s} for e, s in p["stages"].items()
                           if s and stage_rank(s) > stage_rank(prev["stages"].get(e) or "design")]
                jumps.append({"date": p["date"], "approve_by": add_workdays(dt.date.fromisoformat(p["date"]), -1).isoformat(),
                              "cost_before": prev["total_cost"], "cost_after": p["total_cost"],
                              "slip_before": prev["forecast_slip"], "slip_after": p["forecast_slip"],
                              "drivers": drivers, "boundaries": [b for b in bnds if b["date"] == p["date"]],
                              "activities": acts_at.get(p["date"], [])})
            prev = p
    stage_jump = next((j for j in jumps if j["drivers"]), None)
    jump = jumps[0] if jumps else None

    def money(v):
        return f"${(v or 0):,.0f}"

    line = None
    if stage_jump:
        j = stage_jump
        worst = max(j["drivers"], key=lambda x: stage_rank(x["to"]))
        act = j["boundaries"][0]["activity_name"] if j["boundaries"] else None
        line = (f"Approve by {j['approve_by']} or {worst['element']} becomes {worst['to']}"
                + (f" ({len(j['drivers'])} elements change stage)" if len(j["drivers"]) > 1 else "")
                + (f" when '{act}' finishes on {j['date']}" if act else "")
                + f": {money(j['cost_before'])} -> {money(j['cost_after'])}, slip {j['slip_before']:g} -> {j['slip_after']:g} wd")
        if jump is not stage_jump:
            a = " / ".join(jump["activities"][:2]) or None
            line += (f" (a smaller step first: {money(jump['cost_before'])} -> {money(jump['cost_after'])} on {jump['date']}"
                     + (f" when '{a}' finishes" if a else "") + ")")
    elif jump:
        a = " / ".join(jump["activities"][:2]) or None
        line = (f"Approve by {jump['approve_by']} or the estimate rises" + (f" when '{a}' finishes" if a else "")
                + f": {money(jump['cost_before'])} -> {money(jump['cost_after'])}, slip {jump['slip_before']:g} -> {jump['slip_after']:g} wd")
    return {"points": points, "next_jump": stage_jump or jump, "first_jump": jump, "jumps": jumps,
            "approve_by_line": line, "boundaries": bnds,
            "selected": sel.isoformat(), "assumption": ASSUMPTION, "horizon_days": horizon_days}


# ------------------------------------------------------------------ routes (/api/v2, included from api.py)
from fastapi import APIRouter, HTTPException  # noqa: E402

router = APIRouter(prefix="/api/v2", tags=["synthetic-v2-as-of"])
_TL_CACHE: dict = {}


@router.get("/as-of")
def as_of_presets():
    """The as-of control: today (US Eastern), the presets with their dates, the synthetic status date."""
    return {"today": today().isoformat(), "status_date": AS_OF.isoformat(), "presets": presets(), "assumption": ASSUMPTION}


@router.post("/impact/timeline")
def impact_timeline(m: dict):
    """Cost + forecast slip of one move vs approval date, and the 'approve by <date> or it becomes
    <stage>' line. Body = the /impact body (column, dx, dy, remove, as_of)."""
    from . import move_api
    mv = move_api.Move(**m)
    try:
        d_as_of = parse(mv.as_of)
    except ValueError as e:
        raise HTTPException(400, str(e))
    d = move_api._design()
    key = (move_api._CACHE.get("design_sha"), mv.column, mv.dx, mv.dy, mv.remove, (d_as_of or today()).isoformat(), today().isoformat())
    if key in _TL_CACHE:
        return _TL_CACHE[key]
    res = move_api._impact(d, mv)   # structural impact: independent of the date (404 for an unknown column)
    imp = move_api._change_order_input(d, res)
    ids = sorted(set(imp["elements"]) | {r["id"] for r in imp["resized"]} | {c["id"] for c in imp["connections_changed"]}
                 | {f["id"] for f in imp["footings_changed"]})
    out = timeline(d, lambda ads: move_api._change_order(d, res, ads), ids, d_as_of, default_adapters=move_api._adapters)
    out["move"] = {"column": move_api._col(mv.column), "dx": mv.dx, "dy": mv.dy, "remove": mv.remove}
    out = move_api._safe(out)
    if len(_TL_CACHE) > 64:
        _TL_CACHE.clear()
    _TL_CACHE[key] = out
    return out
