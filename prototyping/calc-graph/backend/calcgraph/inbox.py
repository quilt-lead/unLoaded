"""Inbound inbox: RFIs, change events and change order requests arriving from a construction platform,
read by the AI step, confirmed by the engineer, run through the SAME impact engine as move-a-column,
answered with a drafted reply. All routes under /api/v2/inbox (included from api.py).

Flow per item:
  1. list      the selected platform adapter's open items (move_api._adapters(): the mock, or the live
               adapter when CALCGRAPH_PLATFORM_*=live) - RFIs open/draft, change events pending/draft
               without a pending change order, change orders pending.
  2. read      calcgraph.ai.extract("inbound_item_reading", ...) - the repo's ONE structured-output LLM path
               (Pydantic schema, content-hash cache, budget caps, provenance). Provider: anthropic, model
               = the AI step's default (claude-opus-5-5). The cache key is a hash of the item's content
               (plus task / schema / model), so a reload or a second engineer never re-spends.
  3. confirm   the engineer edits / confirms the reading (stored, never overwritten by a re-read).
  4. impact    the confirmed reading mapped onto the move engine's input: move / remove a column ->
               move_api.impact_result (same as /api/v2/impact) at the as-of date (item's required-by
               date, else today); a section substitution / resize -> the change-order estimator only
               (structural recheck NOT run, said so); anything else -> no number, the reason, and the
               construction status of the elements read.
  5. reply     a drafted RFI response / change order review (deterministic template from 1-4, no LLM),
               editable; "post to platform" only for a live sandbox adapter that can post, with an
               explicit confirm - otherwise refused with the reason.
Every step lands on the elements' history (GET /api/v2/inbox/history/{element_id}), shown on the element
page's Platforms tab.

State (readings confirmed, impact summaries, replies, history) lives in data/store/inbox/state.json
(gitignored), keyed by item key and content hash. Times are US Eastern.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import threading
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Body, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from . import ai
from .ai.tasks import TaskSpec, register_task
from .ai.types import AIInputs, AIOutput

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
STATE_PATH = os.path.join(ROOT, "data", "store", "inbox", "state.json")
ET = ZoneInfo("America/New_York")
router = APIRouter(prefix="/api/v2/inbox", tags=["synthetic-v2-inbox"])
_LOCK = threading.Lock()
PROVIDER = "anthropic"      # the AI step's real provider; its default model is the one F8 uses


def now_et() -> str:
    return dt.datetime.now(ET).strftime("%Y-%m-%d %H:%M ET")


# ===================================================================== AI task: read one inbound item
CHANGE_TYPES = ("move_column", "remove_column", "substitute_section", "resize_member", "add_opening",
                "modify_connection", "add_member", "other_structural", "not_structural", "unclear")


class ElementRef(BaseModel):
    model_config = ConfigDict(extra="forbid")
    element_id: str = Field(description="a registry element id from payload.candidates (first token of a line)")
    role: Literal["primary", "affected"] = Field(description="primary = the element the change is made to")
    how_identified: str = Field(description="the words in the item that identify it (quote), and any inference")


class MoveVector(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dx_ft: float = Field(description="feet along +x = east = toward higher grid numbers (1 -> 5)")
    dy_ft: float = Field(description="feet along +y = north = toward later grid letters (A -> D)")


class InboundItemReading(AIOutput):
    change_type: Literal[CHANGE_TYPES]
    elements: list[ElementRef] = Field(default_factory=list)
    move: MoveVector | None = Field(default=None, description="for move_column only, when distance AND direction are stated")
    new_section: str | None = Field(default=None, description="for substitute_section / resize_member, e.g. W10X54")
    summary: str = Field(min_length=1, description="one sentence: what is being asked, in engineering terms")
    unresolved: list[str] = Field(default_factory=list,
                                  description="each thing the item does not pin down (which element, direction, size, ...)")


def _cand_ids(inputs: AIInputs) -> set[str]:
    return {c.split(" ", 1)[0] for c in inputs.payload.get("candidates", [])}


def _validate_reading(inputs: AIInputs, out: AIOutput) -> None:
    assert isinstance(out, InboundItemReading)
    ok = _cand_ids(inputs)
    bad = [e.element_id for e in out.elements if e.element_id not in ok]
    if bad:
        raise ValueError(f"elements not among the candidates: {bad}")
    prim = [e for e in out.elements if e.role == "primary"]
    if out.change_type in ("move_column", "remove_column"):
        if len(prim) > 1:
            raise ValueError(f"{out.change_type} names {len(prim)} primary elements; one, or none with unresolved")
        if prim and not prim[0].element_id.startswith("COL-"):
            raise ValueError(f"{out.change_type} primary {prim[0].element_id} is not a column")
        if not prim and not out.unresolved:
            raise ValueError(f"{out.change_type} with no primary column must say what is unresolved")
    if out.change_type == "move_column" and out.move is None and not out.unresolved:
        raise ValueError("move_column without a move vector must say what is unresolved")
    if out.change_type in ("substitute_section", "resize_member") and not out.new_section and not out.unresolved:
        raise ValueError(f"{out.change_type} without new_section must say what is unresolved")


INBOUND_ITEM_READING = register_task(TaskSpec(
    name="inbound_item_reading",
    version="1",
    intended_for="RFIs / change events / change order requests arriving from a construction platform",
    output_schema=InboundItemReading,
    validate=_validate_reading,
    max_output_tokens=6000,
    instructions=(
        "You read one item that arrived from a construction platform (an RFI, a change event or a change "
        "order request) for the structural engineer of record of the building described in the payload. "
        "Say what change it asks for and which structural elements it concerns, so the engineer can run "
        "an impact check.\n"
        "Element ids: use only ids from payload.candidates (the first token of each line). Columns are "
        "COL-<grid number><grid letter>, e.g. COL-2B is at grid 2/B. Coordinates: +x is east, toward higher "
        "grid numbers; +y is north, toward later grid letters (A, B, C, D). payload.grids gives positions in ft.\n"
        "change_type: move_column, remove_column (delete a column), substitute_section (a different rolled "
        "section for an existing member), resize_member, add_opening (penetration / web opening), "
        "modify_connection, add_member, other_structural, not_structural (no structural question: finishes, "
        "colors, architecture, MEP only), unclear (cannot tell what is asked).\n"
        "Do not guess. If the item does not identify exactly one element, or does not state the direction "
        "or the distance of a move, or the new size, leave that out and put each missing fact in "
        "`unresolved`; you may still list the plausible elements with role 'affected' and say so in "
        "how_identified. Convert inches to feet. Give a confidence for the whole reading: high only when "
        "every element and number is stated or follows directly from a grid reference. Cite the item "
        "evidence id in evidence_refs."
    ),
))


# ===================================================================== state file
def _load() -> dict:
    try:
        with open(STATE_PATH) as fh:
            return json.load(fh)
    except FileNotFoundError:
        return {"items": {}, "history": []}


def _save(s: dict) -> None:
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    tmp = STATE_PATH + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(s, fh, indent=1, sort_keys=True)
    os.replace(tmp, STATE_PATH)


def _event(s: dict, item: dict, event: str, text: str, element_ids: list[str]) -> None:
    s["history"].append({"at": now_et(), "item_key": item["key"], "number": item["number"], "kind": item["kind"],
                         "platform": item["platform"], "link": item["link"], "event": event, "text": text,
                         "element_ids": sorted(set(element_ids))})


# ===================================================================== items from the adapter
def _mv():
    from . import move_api
    return move_api


def _adapter(platform: str | None):
    ads = _mv()._adapters()
    from .platforms.base import RFIS
    if platform:
        a = next((x for x in ads if x.name == platform), None)
        if a is None:
            raise HTTPException(404, f"no platform {platform!r}; one of {[x.name for x in ads]}")
        return a, ads
    return next((x for x in ads if x.supports(RFIS)), ads[0]), ads


def content_hash(kind: str, number: str, title: str, body: str) -> str:
    return hashlib.sha256(json.dumps({"kind": kind, "number": number, "title": title, "body": body},
                                     sort_keys=True).encode()).hexdigest()


def list_items(a) -> list[dict]:
    """Open items waiting on the engineer, from one adapter (normalized records only)."""
    from .platforms.base import CHANGE_EVENTS, CHANGE_ORDERS, RFIS
    out = []

    def add(r, kind, body, required_by):
        out.append({"key": f"{a.name}:{kind}:{r.id}", "platform": a.name, "platform_label": a.label, "kind": kind,
                    "id": r.id, "ref": r.ref, "number": r.number, "title": r.title, "body": body or "",
                    "status": r.status, "received": r.dates.get("created"), "required_by": required_by,
                    "linked_element_ids": list(r.element_ids), "link": r.links.get("self"),
                    "source": r.fields.get("source", "mock"), "source_label": r.fields.get("source_label"),
                    "content_hash": content_hash(kind, r.number, r.title, body or "")})
    if a.supports(RFIS):
        for r in a.list(RFIS):
            if r.status in ("open", "draft"):
                add(r, "rfi", r.fields.get("question"), r.dates.get("due"))
    pending_co_ce = set()
    if a.supports(CHANGE_ORDERS):
        ces = {c.ref: c for c in a.list(CHANGE_EVENTS)} if a.supports(CHANGE_EVENTS) else {}
        for r in a.list(CHANGE_ORDERS):
            if r.status in ("pending", "draft"):
                ce = ces.get(r.fields.get("change_event_ref"))
                pending_co_ce.add(r.fields.get("change_event_ref"))
                body = (ce.raw.get("description") if ce is not None else None) or r.raw.get("description") or r.title
                add(r, "change_order", body, None)
    if a.supports(CHANGE_EVENTS):
        for r in a.list(CHANGE_EVENTS):
            if r.status in ("pending", "draft") and r.ref not in pending_co_ce:
                add(r, "change_event", r.raw.get("description") or r.title, None)
    return sorted(out, key=lambda i: (i["received"] or "", i["number"]), reverse=True)


def _item(key: str) -> dict:
    plat = key.split(":", 1)[0]
    a, _ = _adapter(plat)
    it = next((i for i in list_items(a) if i["key"] == key), None)
    if it is None:
        raise HTTPException(404, f"no open item {key!r} on {plat}")
    return it


# ===================================================================== AI inputs
def _design() -> dict:
    return _mv()._design()


def ai_inputs(item: dict, design: dict) -> AIInputs:
    """Evidence = the item text (doc hash = the item's content hash). Payload = the item, the building's
    grids and levels, and candidates: every column, beam, girder and brace, plus any element named
    literally in the text and the connections of those elements."""
    els = design["elements"]
    text = f"{item['title']}\n{item['body']}"
    ids = {e["id"] for e in els}
    literal = {t for t in re.findall(r"[A-Z]{1,4}(?:-[A-Z0-9]+)+", text.upper()) if t in ids}
    keep = []
    for e in els:
        lit = e["id"] in literal or (e["type"] == "connection" and e.get("member") in literal)
        if e["type"] in ("column", "beam", "girder", "brace") or lit:
            loc = (f"x={e['x']:g} y={e['y']:g}" if "x" in e and "y" in e else
                   f"({e['p1'][0]:g},{e['p1'][1]:g})-({e['p2'][0]:g},{e['p2'][1]:g})" if "p1" in e and "p2" in e else "")
            keep.append(" ".join(str(v) for v in (e["id"], e["type"], e.get("size") or e.get("conn_type") or "",
                                                   e.get("level") or "", loc) if v != ""))
    b = design.get("building", {})
    return AIInputs.model_validate({
        "evidence": [{"id": "item", "doc_sha256": item["content_hash"], "frame": "text", "text": text}],
        "payload": {"item": {"kind": item["kind"], "number": item["number"], "title": item["title"], "body": item["body"],
                             "platform": item["platform_label"]},
                    "building": b.get("name"), "grids": b.get("grids"),
                    "levels": [{"key": lv["key"], "name": lv["name"], "elev_ft": lv["elev_ft"]} for lv in b.get("levels", [])],
                    "candidates": keep},
    })


_RUN: ai.Run | None = None


def _run() -> ai.Run:
    """One spend ledger for the server process; the cap comes from CALCGRAPH_AI_MAX_RUN_USD (default $0,
    which refuses any billed call - a cache hit is always served)."""
    global _RUN
    if _RUN is None:
        _RUN = ai.Run()
    return _RUN


def llm_status() -> dict:
    p = ai.get_provider(PROVIDER)
    ok, why = p.enabled()
    return {"provider": p.name, "model": p.model_id, "enabled": ok, "why": why, "run": _run().summary(),
            "run_cap_usd": _run().budget.max_cost_usd_per_run}


def read_item(item: dict, design: dict, *, cache_only: bool = False, run: ai.Run | None = None) -> dict:
    """The AI reading of one item (cache first). cache_only=True never calls the provider."""
    inputs = ai_inputs(item, design)
    prov = ai.get_provider(PROVIDER)
    if cache_only:
        from .ai.step import _keys
        _, ck, _ = _keys(INBOUND_ITEM_READING, InboundItemReading, inputs, prov)
        if ai.ResultCache().get(INBOUND_ITEM_READING.name, ck) is None:
            return {"reading": None, "cached": False}
    res = ai.extract(INBOUND_ITEM_READING, inputs, provider=prov, run=run or _run())
    return {"reading": res.output.model_dump(mode="json"), "cached": res.cached,
            "usage": res.usage.model_dump(), "provenance": res.provenance.model_dump(mode="json", exclude={"evidence"}),
            "content_hash": item["content_hash"]}


# ===================================================================== reading -> engine input
def plan_run(reading: dict, design: dict) -> dict:
    """Map a confirmed reading onto what the engine can run. engine: move | resize | none."""
    els = {e["id"]: e for e in design["elements"]}
    ct = reading.get("change_type")
    prim = [e["element_id"] for e in reading.get("elements", []) if e.get("role") == "primary"]
    if reading.get("unresolved") and not prim and ct not in ("not_structural",):
        return {"engine": None, "expressible": False,
                "reason": "the reading leaves the element unresolved: " + "; ".join(reading["unresolved"])
                          + " - confirm which element before running"}
    if ct in ("move_column", "remove_column"):
        if not prim or not prim[0].startswith("COL-"):
            return {"engine": None, "expressible": False, "reason": f"{ct} needs one primary column"}
        mv = reading.get("move") or {}
        if ct == "move_column" and not mv:
            return {"engine": None, "expressible": False,
                    "reason": "the move distance / direction is unresolved: " + "; ".join(reading.get("unresolved") or [])}
        return {"engine": "move", "expressible": True,
                "move": {"column": prim[0], "dx": float(mv.get("dx_ft") or 0.0), "dy": float(mv.get("dy_ft") or 0.0),
                         "remove": ct == "remove_column"},
                "reason": "move-a-column impact engine (stale calcs, screened estimates, health, change order)"}
    if ct in ("substitute_section", "resize_member"):
        new = (reading.get("new_section") or "").upper().replace(" ", "")
        if not prim or prim[0] not in els or not new:
            return {"engine": None, "expressible": False, "reason": f"{ct} needs one primary member and the new section"}
        from .platforms.synthetic import shape_props
        if shape_props(new)["lb_per_ft"] is None:
            return {"engine": None, "expressible": False, "reason": f"{new} is not a section the cost tables know"}
        return {"engine": "resize", "expressible": "partial",
                "resize": {"id": prim[0], "old_size": els[prim[0]].get("size"), "new_size": new},
                "reason": ("change-order estimator only (tonnage, stage penalties, resubmittals, schedule); the move "
                           "engine moves and removes columns, so the STRUCTURAL recheck of the new section and what it "
                           "carries was NOT run - the calc records that design it are listed to redo")}
    if ct == "not_structural":
        return {"engine": None, "expressible": False, "reason": "not a structural question: no structural impact to run"}
    what = {"add_opening": "a web opening / penetration", "modify_connection": "a connection modification",
            "add_member": "an added member", "other_structural": "this change", "unclear": "an unclear request"}.get(ct, ct)
    return {"engine": None, "expressible": False,
            "reason": f"the impact engine cannot express {what} (it moves and removes columns); no cost or schedule "
                      "number is given - the construction status of the elements read is shown instead"}


def run_impact(item: dict, reading: dict, as_of_value: str | None) -> dict:
    """The engine run for a confirmed reading at an as-of date (default: the item's required-by date)."""
    from . import as_of as asof
    mv = _mv()
    d = _design()
    plan = plan_run(reading, d)
    as_of_value = as_of_value or item.get("required_by") or "today"
    d_as_of = asof.parse(as_of_value)
    ads = asof.adapters(d, d_as_of, mv._adapters)
    out = {"plan": plan, "as_of": asof.describe(ads, d_as_of), "computed_at": now_et()}
    prim = [e["element_id"] for e in reading.get("elements", []) if e.get("role") == "primary"]
    ids = prim or [e["element_id"] for e in reading.get("elements", [])]
    if plan["engine"] == "move":
        res = mv.impact_result(mv.Move(**plan["move"], as_of=as_of_value))
        co = res.get("change_order") or {}
        out["impact"] = {"column": res["column"], "stale": len(res["stale"]), "health": {
            k: res["health"].get(k) for k in ("band", "score", "band_construction", "score_construction", "worst_uc")},
            "sheets": res["health"].get("sheets")}
        out["change_order"] = co.get("summary")
        out["links"] = {"move_page": f"/v2?col={plan['move']['column']}&dx={plan['move']['dx']:g}&dy={plan['move']['dy']:g}"
                                     f"&remove={int(plan['move']['remove'])}&as_of={(d_as_of or asof.today()).isoformat()}"}
        try:
            out["timeline"] = asof.impact_timeline({**plan["move"], "as_of": as_of_value})
        except HTTPException as e:
            out["timeline_error"] = e.detail
    elif plan["engine"] == "resize":
        from .platforms import estimate
        from .platforms.synthetic import _length_ft
        r = plan["resize"]
        e = {x["id"]: x for x in d["elements"]}[r["id"]]
        recs = [x["id"] for x in d["records"] if r["id"] in x.get("elements", [])]
        imp = {"elements": [r["id"]], "resized": [{**r, "length_ft": _length_ft(e)}], "records": recs}
        co = estimate(imp, ads, d)
        out["change_order"] = co.get("summary")
        out["records_to_redo"] = recs
    out["status"] = {eid: _status(ads, d, eid) for eid in ids[:6]}
    return out


def _status(ads, d, eid) -> dict:
    from .platforms import construction_status
    try:
        s = construction_status(eid, ads, d)
        return {k: s.get(k) for k in ("stage", "float_days", "reasons")} | {
            "submittals": [x["number"] for x in s.get("submittals", [])]}
    except Exception as e:   # noqa: BLE001 - shown, never hidden
        return {"error": f"{type(e).__name__}: {e}"}


# ===================================================================== reply draft
def _money(v) -> str:
    return "-" if v is None else f"${v:,.0f}"


def draft_reply(item: dict, reading: dict, impact: dict | None, base_url: str) -> str:
    """RFI response / change order review text (template; the engineer edits it before anything is sent)."""
    head = {"rfi": f"Response to {item['number']}", "change_order": f"Review of change order request {item['number']}",
            "change_event": f"Review of change event {item['number']}"}[item["kind"]]
    lines = [f"{head}: {item['title']}", "DRAFT - for the engineer of record to review and edit before it is sent.", ""]
    els = [e["element_id"] for e in reading.get("elements", [])]
    lines.append(f"Our reading: {reading.get('summary', '').strip()}")
    if els:
        lines.append("Elements: " + ", ".join(els))
    if reading.get("unresolved"):
        lines.append("Needs clarification from the sender: " + "; ".join(reading["unresolved"]))
    lines.append("")
    plan = (impact or {}).get("plan") or plan_run(reading, _design())
    if reading.get("change_type") == "not_structural":
        lines += ["This item does not raise a structural question. Please route it to the Architect of record; "
                  "no structural response is required.", ""]
    elif impact and plan.get("engine") == "move":
        co, im = impact.get("change_order") or {}, impact.get("impact") or {}
        a = impact["as_of"]
        what = (f"Removing {plan['move']['column']}" if plan["move"]["remove"] else
                f"Moving {plan['move']['column']} by ({plan['move']['dx']:+g}, {plan['move']['dy']:+g}) ft")
        lines.append(f"Impact screening ({what}), if approved by {a['as_of']}:")
        lines.append(f"- {im.get('stale')} calc records to redo; design difficulty {im.get('health', {}).get('band')}, "
                     f"with construction status {im.get('health', {}).get('band_construction')}.")
        if co:
            lines.append(f"- Estimated cost {_money(co.get('total_cost', {}).get('value'))} (range "
                         f"{_money(co.get('cost_range', {}).get('low', {}).get('value'))} to "
                         f"{_money(co.get('cost_range', {}).get('high', {}).get('value'))}); forecast slip "
                         f"{co.get('forecast_slip', {}).get('value', 0):g} working days, "
                         f"{co.get('finish_delay', {}).get('value', 0):g} past the contract date.")
            c = co.get("counts", {})
            lines.append(f"- Touches {c.get('submittals', 0)} submittals ({c.get('submittals_flagged', 0)} approved or later), "
                         f"{c.get('rfis', 0)} RFIs, {c.get('sheets', 0)} sheets.")
        tl = impact.get("timeline") or {}
        if tl.get("approve_by_line"):
            lines.append(f"- {tl['approve_by_line']}.")
        lines.append("")
        lines.append("Response: [engineer to complete - accept / accept with conditions / reject]")
        lines.append("")
    elif impact and plan.get("engine") == "resize":
        co = impact.get("change_order") or {}
        r = plan["resize"]
        lines.append(f"Substitution {r['old_size']} -> {r['new_size']} at {r['id']}, if approved by {impact['as_of']['as_of']}:")
        lines.append(f"- Estimated cost {_money(co.get('total_cost', {}).get('value'))}, forecast slip "
                     f"{co.get('forecast_slip', {}).get('value', 0):g} working days (change-order estimator).")
        lines.append("- Structural check of the new section NOT yet run; records to redo: "
                     + ", ".join(impact.get("records_to_redo") or []) + ".")
        lines += ["", "Response: [engineer to complete after the structural check]", ""]
    else:
        lines.append(f"Impact: not computed - {plan.get('reason')}.")
        for eid, s in ((impact or {}).get("status") or {}).items():
            if s.get("stage"):
                lines.append(f"- {eid} is {s['stage']} on site" + (f"; submittals {', '.join(s['submittals'])}" if s.get("submittals") else ""))
        lines += ["", "Response: [engineer to complete]", ""]
    lines.append("Links:")
    if item.get("link"):
        lines.append(f"- {item['platform_label']} record: {item['link']}")
    for eid in els[:6]:
        lines.append(f"- {eid} in the registry: {base_url}v2/element/{eid}")
    mp = ((impact or {}).get("links") or {}).get("move_page")
    if mp:
        lines.append(f"- Impact check: {base_url}{mp.lstrip('/')}")
    return "\n".join(lines)


# ===================================================================== routes
def _merged(item: dict, s: dict) -> dict:
    st = s["items"].get(item["key"], {})
    stale = st.get("content_hash") and st["content_hash"] != item["content_hash"]
    return {**item, "state": {k: st.get(k) for k in ("confirmed", "impact", "reply", "reply_edited_at", "posted")},
            "changed_since_read": bool(stale)}


@router.get("")
def inbox(platform: str | None = None):
    a, ads = _adapter(platform)
    d = _design()
    s = _load()
    items = []
    for it in list_items(a):
        m = _merged(it, s)
        m["post"] = post_status(it)
        try:
            m["reading"] = read_item(it, d, cache_only=True)["reading"]
        except Exception as e:   # noqa: BLE001
            m["reading"], m["reading_error"] = None, f"{type(e).__name__}: {e}"
        items.append(m)
    return {"platform": a.name, "platforms": [{"name": x.name, "label": x.label, "source": getattr(x, "source", "mock")}
                                              for x in ads], "items": items, "llm": llm_status(), "now": now_et()}


@router.post("/{key}/read")
def read(key: str):
    item = _item(key)
    try:
        out = read_item(item, _design())
    except ai.ProviderDisabled as e:
        raise HTTPException(409, f"no cached reading for this content and the AI provider is off: {e}")
    except ai.BudgetExceeded as e:
        raise HTTPException(402, str(e))
    except (ai.AIOutputInvalid, ai.AIEvidenceError) as e:
        raise HTTPException(502, f"the model's reading failed validation (not stored): {e}")
    with _LOCK:
        s = _load()
        st = s["items"].setdefault(key, {})
        if not st.get("read_logged") or st.get("content_hash") != item["content_hash"]:
            _event(s, item, "read", f"AI reading: {out['reading']['summary']}", [e["element_id"] for e in out["reading"]["elements"]])
            st["read_logged"] = True
            st["content_hash"] = item["content_hash"]
        _save(s)
    return {**out, "llm": llm_status()}


@router.put("/{key}/reading")
def confirm(key: str, reading: dict = Body(...)):
    """The engineer's confirmed (possibly edited) reading. Validated against the same schema and
    candidate list as the AI's; stored as-is and never overwritten by a re-read."""
    item = _item(key)
    try:
        r = InboundItemReading.model_validate({"confidence": 1.0, "evidence_refs": ["item"], **reading})
        _validate_reading(ai_inputs(item, _design()), r)
    except Exception as e:   # noqa: BLE001
        raise HTTPException(400, f"reading not valid: {e}")
    body = r.model_dump(mode="json")
    with _LOCK:
        s = _load()
        st = s["items"].setdefault(key, {})
        st.update(confirmed=body, confirmed_at=now_et(), content_hash=item["content_hash"])
        _event(s, item, "confirmed", f"Engineer confirmed: {body['summary']}", [e["element_id"] for e in body["elements"]])
        _save(s)
    return {"confirmed": body}


@router.post("/{key}/impact")
def impact(key: str, body: dict = Body(default={})):
    item = _item(key)
    s = _load()
    reading = (s["items"].get(key) or {}).get("confirmed")
    if not reading:
        raise HTTPException(409, "confirm the reading first (PUT /reading)")
    try:
        out = run_impact(item, reading, body.get("as_of"))
    except ValueError as e:
        raise HTTPException(400, str(e))
    with _LOCK:
        s = _load()
        st = s["items"].setdefault(key, {})
        st["impact"] = out
        co = out.get("change_order") or {}
        txt = (f"Impact at {out['as_of']['as_of']}: " + (co.get("headline") or out["plan"]["reason"]))
        _event(s, item, "impact", txt, [e["element_id"] for e in reading["elements"]])
        _save(s)
    return out


@router.post("/{key}/reply")
def reply(key: str, request: Request):
    item = _item(key)
    s = _load()
    st = s["items"].get(key) or {}
    if not st.get("confirmed"):
        raise HTTPException(409, "confirm the reading first")
    text = draft_reply(item, st["confirmed"], st.get("impact"), str(request.base_url))
    with _LOCK:
        s = _load()
        st = s["items"].setdefault(key, {})
        st.update(reply=text, reply_drafted_at=now_et(), reply_edited_at=None)
        _event(s, item, "reply-drafted", "Reply drafted (not sent)", [e["element_id"] for e in st["confirmed"]["elements"]])
        _save(s)
    return {"reply": text, "post": post_status(item)}


@router.put("/{key}/reply")
def edit_reply(key: str, body: dict = Body(...)):
    item = _item(key)
    with _LOCK:
        s = _load()
        st = s["items"].setdefault(key, {})
        st.update(reply=str(body.get("reply", "")), reply_edited_at=now_et())
        _save(s)
    return {"reply": st["reply"], "reply_edited_at": st["reply_edited_at"], "post": post_status(item)}


def post_status(item: dict) -> dict:
    """Whether 'post to platform' is allowed, and why not. Allowed only for a LIVE adapter on a sandbox
    that implements post_reply (none does yet: the RFI reply / change-order review endpoints are not in
    the generated client subsets, and a write without a spec-checked call is not made)."""
    a, _ = _adapter(item["platform"])
    if getattr(a, "source", "mock") != "live":
        return {"allowed": False, "reason": f"{a.label} is the synthetic mock: there is no platform to post to"}
    live = getattr(a, "live", None)
    if not getattr(live, "sandbox", False):
        return {"allowed": False, "reason": "live adapter is not a sandbox: posting is refused outside a sandbox"}
    if not hasattr(live, "post_reply"):
        return {"allowed": False, "reason": "posting replies is not implemented for this adapter (no spec-checked "
                                            "reply endpoint in its generated client)"}
    return {"allowed": True, "reason": "live sandbox - needs an explicit confirm"}


@router.post("/{key}/post")
def post(key: str, body: dict = Body(default={})):
    item = _item(key)
    ps = post_status(item)
    if not ps["allowed"]:
        raise HTTPException(409, ps["reason"])
    if body.get("confirm") is not True:
        raise HTTPException(400, "posting needs {\"confirm\": true}")
    s = _load()
    st = s["items"].get(key) or {}
    if not st.get("reply"):
        raise HTTPException(409, "draft a reply first")
    a, _ = _adapter(item["platform"])
    res = a.live.post_reply(item, st["reply"])   # pragma: no cover - no adapter implements it yet
    with _LOCK:
        s = _load()
        s["items"][key]["posted"] = {"at": now_et(), "result": res}
        _event(s, item, "posted", "Reply posted to the platform", [e["element_id"] for e in st["confirmed"]["elements"]])
        _save(s)
    return {"posted": res}


@router.get("/history/{eid}")
def history(eid: str):
    """Inbox events (received item read, reading confirmed, impact run, reply drafted / posted) for one
    element, newest first."""
    s = _load()
    return [h for h in reversed(s["history"]) if eid in h["element_ids"]]


@router.get("/llm")
def llm():
    return llm_status()
