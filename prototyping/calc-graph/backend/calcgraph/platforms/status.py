"""Construction status of one element, for the move-difficulty / health meter.

construction_status(element_id, adapters=None, design=None) -> {
    element_id, stage: design|submitted|approved|fabricated|delivered|erected, stage_rank 0..5,
    submittals: [{ref, number, title, status, stage, platform, link, sources}],
    open_rfis:  [{ref, number, title, status, platform, link, sources}],
    float_days: int|None (least REPORTED total float of the element's next open activities; None when
                no next activity reports float - live platforms may not),
    next_activities: [{ref, title, status, early_start, early_finish, total_float_days|None, float_known, critical}],
    reasons: [str], move_difficulty: {value 0..1, unit, estimate, basis}}

Group ids (LEVEL:L2, GRID:2, FRAME:SMF-A) report their most advanced member. Ids with no
construction footprint (types, materials, calc records) report stage "design".
"""
from __future__ import annotations

from .base import RFIS, SCHEDULE_ACTIVITIES, STAGES, SUBMITTALS, NormalizedRecord, PlatformAdapter, stage_rank

STAGE_WEIGHT = {"design": 0.0, "submitted": 0.15, "approved": 0.35, "fabricated": 0.6, "delivered": 0.7, "erected": 0.9}
STAGE_TEXT = {
    "design": "not yet in a submittal: a design change costs engineering time only",
    "submitted": "its shop drawings are under review: they must be revised before approval",
    "approved": "its shop drawings are approved: a change means redesign, re-detail and resubmittal",
    "fabricated": "it is fabricated: a change scraps or re-works shop pieces",
    "delivered": "it is delivered to site: a change scraps delivered pieces and re-ships",
    "erected": "it is erected / in place: a change means field rework (remove, modify, re-erect)",
}


def _state_of(adapters):
    return next((a.state for a in adapters if getattr(a, "state", None) is not None), None)


def _dedupe(recs: list[NormalizedRecord]) -> list[dict]:
    out: dict[str, dict] = {}
    for r in recs:
        d = out.get(r.ref)
        src = {"platform": r.platform, "id": r.id, "url": r.links.get("self")}
        if d is None:
            out[r.ref] = {"ref": r.ref, "number": r.number, "title": r.title, "status": r.status,
                          "stage": r.fields.get("stage"), "platform": r.platform, "link": r.links.get("self"),
                          "sources": [src]}
        else:
            d["sources"].append(src)
    return list(out.values())


def element_stage(element_id: str, adapters: list[PlatformAdapter]) -> tuple[str, list[str]]:
    st = _state_of(adapters)
    if st is not None:
        if element_id in st.element_index:
            ix = st.element_index[element_id]
            return ix["stage"], list(ix["notes"])
        if element_id in st.groups:
            best, notes = "design", []
            for m in st.groups[element_id]:
                s = st.element_index[m]["stage"]
                if stage_rank(s) > stage_rank(best):
                    best = s
            n = sum(1 for m in st.groups[element_id] if st.element_index[m]["stage"] == best)
            notes.append(f"{n} of {len(st.groups[element_id])} member elements are {best}")
            return best, notes
        return "design", []
    # live adapters without a synthetic state: most advanced package stage among its submittals
    best = "design"
    for a in adapters:
        if a.supports(SUBMITTALS):
            for r in a.records_for_element(element_id, (SUBMITTALS,)):
                if r.fields.get("package_kind") in ("product_data", "connection_design"):
                    continue
                s = r.fields.get("stage") or "design"
                if stage_rank(s) > stage_rank(best):
                    best = s
    return best, []


def next_activities(element_id: str, adapters: list[PlatformAdapter], limit: int = 2) -> list[NormalizedRecord]:
    st = _state_of(adapters)
    acts = []
    for a in adapters:
        if a.supports(SCHEDULE_ACTIVITIES):
            acts = {r.ref: r for r in a.list(SCHEDULE_ACTIVITIES)}
            break
    if not acts:
        return []
    ids = [element_id]
    if st is not None and element_id in st.groups:
        ids = st.groups[element_id]
    seen, out = set(), []
    for eid in ids:
        chain = []
        if st is not None and eid in st.element_index:
            chain = st.element_index[eid]["chain"] + st.element_index[eid]["downstream"]
        else:
            chain = [r for r, rec in acts.items() if eid in rec.element_ids]
        k = 0
        for ref in chain:
            rec = acts.get(ref)
            if rec is None or rec.status == "complete" or ref in seen:
                continue
            seen.add(ref)
            out.append(rec)
            k += 1
            if k >= limit:
                break
    return out


def construction_status(element_id: str, adapters: list[PlatformAdapter] | None = None, design: dict | None = None) -> dict:
    if adapters is None:
        from . import get_adapters, load_design
        adapters = get_adapters(design if design is not None else load_design())
    st = _state_of(adapters)
    ids = st.groups.get(element_id, [element_id]) if st is not None else [element_id]
    idset = set(ids) | {element_id}
    stage, notes = element_stage(element_id, adapters)
    subs, rfis = [], []
    for a in adapters:
        if a.supports(SUBMITTALS):
            subs += [r for r in a.list(SUBMITTALS) if idset & set(r.element_ids)]
        if a.supports(RFIS):
            rfis += [r for r in a.list(RFIS) if idset & set(r.element_ids) and r.status in ("draft", "open", "answered")]
    subs_d, rfis_d = _dedupe(subs), _dedupe(rfis)
    nxt = next_activities(element_id, adapters)
    known = [r.total_float for r in nxt if r.total_float is not None]
    unknown = [r for r in nxt if r.total_float is None]
    float_days = min(known, default=None)
    reasons = [f"{element_id} is {stage}: {STAGE_TEXT[stage]}"] + notes
    hard = [s for s in subs_d if s["status"] in ("approved", "fabricated", "delivered", "erected")]
    if hard:
        reasons.append(f"{len(hard)} approved-or-later submittal(s) would need resubmittal: "
                       + ", ".join(f"{s['number']} ({s['status']})" for s in hard[:4]) + (" ..." if len(hard) > 4 else ""))
    if rfis_d:
        reasons.append(f"{len(rfis_d)} open RFI(s): " + ", ".join(f"{r['number']} {r['title']}" for r in rfis_d))
    if float_days is not None:
        crit = [r for r in nxt if r.fields.get("critical")]
        reasons.append(f"least total float on its next activities: {float_days} working days"
                       + (f" ({', '.join(r.ref for r in crit)} on the critical path)" if crit else ""))
    if unknown:
        reasons.append(f"total float not reported by the platform for {', '.join(f'{r.ref} ({r.platform})' for r in unknown)}"
                       " - not counted in the float penalty")
    w = STAGE_WEIGHT[stage]
    rfi_pen = min(0.1, 0.05 * len(rfis_d))
    float_pen = 0.0 if float_days is None else (0.1 if float_days < 5 else (0.05 if float_days <= 12 else 0.0))
    resub_pen = 0.05 if hard and stage_rank(stage) < stage_rank("fabricated") else 0.0
    val = round(min(1.0, w + rfi_pen + float_pen + resub_pen), 3)
    return {
        "element_id": element_id, "stage": stage, "stage_rank": stage_rank(stage), "stages": list(STAGES),
        "submittals": subs_d, "open_rfis": rfis_d, "float_days": float_days,
        "next_activities": [{"ref": r.ref, "title": r.title, "status": r.status, "platform": r.platform,
                             "link": r.links.get("self"), "early_start": r.dates.get("early_start"),
                             "early_finish": r.dates.get("early_finish"), "total_float_days": r.total_float,
                             "float_known": r.total_float is not None, "critical": r.fields["critical"]} for r in nxt],
        "reasons": reasons,
        "move_difficulty": {"value": val, "unit": "0-1", "estimate": True,
                            "basis": f"stage weight {w} ({stage}) + open RFIs {rfi_pen} + low float {float_pen} "
                                     f"+ approved resubmittal {resub_pen}; weights: {STAGE_WEIGHT}"},
        "synthetic": True,
    }
