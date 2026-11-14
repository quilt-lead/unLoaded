"""Potential change order (PCO) for a proposed design move: what it touches on the platforms,
what it costs, and what it does to the schedule. Everything is an ESTIMATE.

estimate(impact, adapters, design) -> dict

`impact` (from the impact engine; every key optional):
    {"elements": [element ids affected],
     "resized": [{"id", "old_size", "new_size", "length_ft"}],
     "connections_changed": [{"id", "old_type", "new_type"}],
     "footings_changed": [{"id", "old_B_ft", "new_B_ft", "old_h_in", "new_h_in"}],
     "records": [calc record ids to redo], "sheets": [...], "spec_articles": [...]}

Output (every number is a figure {"value", "unit", "estimate": true, "basis"}; every item that
lives on a platform carries "platform", "link" (mock deep link) and "sources" (all platforms):
    {"summary": {total_cost, finish_delay, float_consumed, counts, worst_stage, headline},
     "submittals": [{ref, number, title, status, stage, action, flag, element_ids, platform, link, sources}],
     "rfis": [{ref, number, title, status, action, element_ids, platform, link, sources}],
     "sheets": [{number, title, source, platform?, link?, sources?}],
     "spec_articles": [{article, source}],
     "calc_records": [ids],
     "cost": {"lines": [{category, element_id, description, figure, platform, link}],
              "by_category": {category: figure}, "total": figure, "range": {low, high}},
     "schedule": {"activities": [{ref, title, added_days, reasons, inserted, early_start, early_finish,
                                  holds: [{ref, title, early_finish_before/after, float_before/after, slip_days,
                                           finish_push, hold_binds, drives_finish}],
                                  early_finish_before/after, float_before/after, slip_days (most-delayed hold)}],
                  "element_holds": {element id: {stage, target, target_title, target_float, drives_finish}},
                  "float_consumed": figure, "finish_delay": figure, "forecast_slip": figure,
                  "project_finish_before", "project_finish_after", "contract_finish", "method"},

Schedule (synthetic state): the change's work is INSERTED into the CPM network as activities
(_rework_plan; work per stage = synthetic.STAGE_WORK, cumulative), each starting no earlier than the data
date (the morning after approval) and finishing before the element's next open activity. It is never
added to an existing activity's duration: that anchored the work to that activity's own start and float,
counted one redesign once per sequential activity, and dropped work whose follow-on activities were done.
     "assumptions": {as_of, rates, schedule_rules}, "warnings": [...], "estimate": true, "synthetic": true}
"""
from __future__ import annotations

from .base import BUDGET_LINES, RFIS, SCHEDULE_ACTIVITIES, SHEETS, SUBMITTALS, PlatformAdapter, stage_rank
from .status import _dedupe, _state_of, element_stage
from .synthetic import RATES, SCHEDULE_RULES, conn_rate, footing_cy, shape_props, steel_rate


def fig(value: float, unit: str, basis: str) -> dict:
    return {"value": round(float(value), 2), "unit": unit, "estimate": True, "basis": basis}


def _money(x: float) -> str:
    return f"${x:,.0f}"


def estimate(impact: dict, adapters: list[PlatformAdapter], design: dict) -> dict:
    impact = impact or {}
    els = {e["id"]: e for e in design.get("elements", [])}
    st = _state_of(adapters)
    rates = st.rates if st is not None else RATES
    rules = st.schedule_rules if st is not None else SCHEDULE_RULES
    warnings: list[str] = []
    resized = list(impact.get("resized") or [])
    conns = list(impact.get("connections_changed") or [])
    ftgs = list(impact.get("footings_changed") or [])
    records = list(dict.fromkeys(impact.get("records") or []))
    changed = {r["id"] for r in resized} | {c["id"] for c in conns} | {f["id"] for f in ftgs}
    touched = set(impact.get("elements") or []) | changed
    for eid in sorted(touched):
        if eid not in els:
            warnings.append(f"{eid}: not in design.json elements (kept, but no platform record can reference it)")

    stage_cache: dict[str, str] = {}

    def stage(eid: str) -> str:
        if eid not in stage_cache:
            stage_cache[eid] = element_stage(eid, adapters)[0]
        return stage_cache[eid]

    # ---------------------------------------------------------------- submittals
    sub_recs = []
    for a in adapters:
        if not a.supports(SUBMITTALS):
            continue
        for r in a.list(SUBMITTALS):
            kind = r.fields.get("package_kind")
            ids = set(r.element_ids)
            if kind == "product_data":
                hit = ids & {x["id"] for x in resized} if r.fields.get("spec_section", "").startswith("07") else set()
            elif kind == "rebar_shop_drawings":
                hit = ids & {f["id"] for f in ftgs}
            else:
                hit = ids & touched
            if hit:
                sub_recs.append((r, sorted(hit)))
    subs = {}
    for r, hit in sub_recs:
        d = subs.get(r.ref)
        if d is None:
            d = _dedupe([r])[0]
            d["element_ids"] = hit
            el_stages = {e: stage(e) for e in hit}
            worst = max(el_stages.values(), key=stage_rank) if el_stages else "design"
            d["elements_by_stage"] = {s: sorted(e for e, v in el_stages.items() if v == s)
                                      for s in sorted(set(el_stages.values()), key=stage_rank)}
            stt = r.status
            if stt == "draft":
                d["action"], d["flag"] = "revise before first submission", None
            elif stt == "submitted":
                d["action"], d["flag"] = "withdraw from review, revise and resubmit", "under_review"
            elif stt == "revise_resubmit":
                d["action"], d["flag"] = "include the change in the pending resubmittal", None
            else:
                d["action"] = f"resubmit as revision {int(r.fields.get('revision') or 0) + 1}"
                d["flag"] = {"approved": "approved", "fabricated": "fabricated_steel", "delivered": "delivered_steel",
                             "erected": "erected_steel"}.get(worst if stage_rank(worst) >= 3 else stt, "approved")
                if r.fields.get("package_kind") == "rebar_shop_drawings" and worst == "erected":
                    d["flag"] = "poured_concrete"
            d["worst_element_stage"] = worst
            subs[r.ref] = d
        else:
            d["sources"].append({"platform": r.platform, "id": r.id, "url": r.links.get("self")})
    subs_out = sorted(subs.values(), key=lambda s: (-stage_rank(s["worst_element_stage"]), s["number"]))

    # ---------------------------------------------------------------- RFIs
    rfi_recs = []
    for a in adapters:
        if a.supports(RFIS):
            rfi_recs += [r for r in a.list(RFIS) if touched & set(r.element_ids)]
    rfis_out = _dedupe(rfi_recs)
    for d in rfis_out:
        r = next(x for x in rfi_recs if x.ref == d["ref"])
        d["element_ids"] = sorted(touched & set(r.element_ids))
        d["action"] = {"draft": "update the draft question for the new geometry before issuing",
                       "open": "answer must account for the change", "answered": "reopen: answer predates the change",
                       "closed": "reopen: closed answer predates the change"}.get(d["status"], "review")

    # ---------------------------------------------------------------- sheets / spec / records
    sheets_out = [{"number": s, "title": None, "source": "impact"} for s in (impact.get("sheets") or [])]
    have = {s["number"] for s in sheets_out}
    sh_recs = []
    for a in adapters:
        if a.supports(SHEETS):
            sh_recs += [r for r in a.list(SHEETS) if changed & set(r.element_ids)]
    for d in _dedupe(sh_recs):
        r = next(x for x in sh_recs if x.ref == d["ref"])
        hit = sorted(changed & set(r.element_ids))
        entry = {"number": d["number"], "title": d["title"], "source": "platform", "platform": d["platform"],
                 "link": d["link"], "sources": d["sources"], "element_ids": hit}
        if d["number"] in have:
            next(s for s in sheets_out if s["number"] == d["number"]).update({k: v for k, v in entry.items() if k != "source"})
        else:
            sheets_out.append(entry)
    specs = [{"article": s, "source": "impact"} for s in (impact.get("spec_articles") or [])]
    for s in subs_out:
        sec = next((r.fields["spec_section"] for r, _ in sub_recs if r.ref == s["ref"]), None)
        if sec and not any(x["article"].startswith(sec) for x in specs):
            specs.append({"article": f"{sec} {next(r.fields['spec_title'] for r, _ in sub_recs if r.ref == s['ref'])} - 1.4 Submittals",
                          "source": "affected submittal"})

    # ---------------------------------------------------------------- cost
    budget = []
    for a in adapters:
        if a.supports(BUDGET_LINES):
            budget = a.list(BUDGET_LINES)
            break

    def budget_link(eid: str) -> tuple[str | None, str | None]:
        for b in budget:
            if eid in b.element_ids:
                return b.platform, b.links.get("self")
        return None, None

    lines = []

    def add(category, eid, desc, value, basis):
        plat, link = budget_link(eid) if eid else (None, None)
        lines.append({"category": category, "element_id": eid, "description": desc,
                      "figure": fig(value, "USD", basis), "platform": plat, "link": link})

    rf = rates["replacement_factor_by_stage"]
    sfrm_applied = False
    if st is not None and st.activity("SFRM"):
        sfrm_applied = st.activity("SFRM")["status"] != "not_started"
    for r in resized:
        eid = r["id"]
        e = els.get(eid, {})
        L = float(r.get("length_ft") or e.get("span_ft") or 0.0)
        if not r.get("length_ft"):
            warnings.append(f"{eid}: length_ft missing, used span_ft {L} from design.json")
        po, pn = shape_props(r["old_size"]), shape_props(r["new_size"])
        if po["lb_per_ft"] is None or pn["lb_per_ft"] is None:
            warnings.append(f"{eid}: unknown weight for {r['old_size']} or {r['new_size']}; tonnage skipped")
            continue
        dlb = (pn["lb_per_ft"] - po["lb_per_ft"]) * L
        rate = steel_rate(r["new_size"])
        add("steel_tonnage", eid, f"{eid} {r['old_size']} -> {r['new_size']}, {L:.1f} ft",
            dlb / 2000.0 * rate,
            f"({pn['lb_per_ft']:.1f} - {po['lb_per_ft']:.1f} lb/ft) x {L:.2f} ft = {dlb:,.0f} lb = {dlb / 2000:.3f} ton "
            f"x {_money(rate)}/ton (assumed F+E rate); weights: {pn['source']}")
        s = stage(eid)
        if s in rf:
            old_cost = po["lb_per_ft"] * L / 2000.0 * steel_rate(r["old_size"])
            add("fabricated_steel_penalty", eid, f"{eid} already {s}: replace the existing piece",
                old_cost * rf[s],
                f"original piece {po['lb_per_ft']:.1f} lb/ft x {L:.2f} ft = {po['lb_per_ft'] * L / 2000:.3f} ton x "
                f"{_money(steel_rate(r['old_size']))}/ton = {_money(old_cost)} x {rf[s]} ({s} replacement factor, assumed: "
                f"{rf})")
        dsf = (pn["perimeter_ft"] - po["perimeter_ft"]) * L
        if abs(dsf) > 0.01 and els.get(eid, {}).get("type") in ("beam", "girder", "column"):
            fac = 2.0 if sfrm_applied else 1.0
            add("fireproofing", eid, f"{eid} SFRM surface change", dsf * rates["fireproofing_usd_per_sf"] * fac,
                f"perimeter {po['perimeter_ft']:.3f} -> {pn['perimeter_ft']:.3f} ft/ft x {L:.2f} ft = {dsf:+.1f} sf x "
                f"${rates['fireproofing_usd_per_sf']}/sf" + (" x 2 (SFRM already applied)" if fac > 1 else " (SFRM not yet applied)"))
    crf = rates["connection_rework_factor_by_stage"]
    for c in conns:
        eid = c["id"]
        s = stage(eid)
        ro, rn = conn_rate(c["old_type"]), conn_rate(c["new_type"])
        if s in crf:
            add("connection_rework", eid, f"{eid} {c['old_type']} -> {c['new_type']} ({s})", rn * crf[s],
                f"new {c['new_type']} {_money(rn)}/each x {crf[s]} rework factor for {s} connections (assumed: {crf}); "
                f"existing {c['old_type']} written off")
        else:
            add("connection_rework", eid, f"{eid} {c['old_type']} -> {c['new_type']} ({s})", rn - ro,
                f"{c['new_type']} {_money(rn)}/each - {c['old_type']} {_money(ro)}/each (assumed unit rates); not yet fabricated")
    for f in ftgs:
        eid = f["id"]
        e = els.get(eid, {})
        oB, nB = float(f.get("old_B_ft") or e.get("B_ft")), float(f.get("new_B_ft") or e.get("B_ft"))
        oh, nh = float(f.get("old_h_in") or e.get("h_in")), float(f.get("new_h_in") or f.get("old_h_in") or e.get("h_in"))
        dcy = footing_cy(nB, nh) - footing_cy(oB, oh)
        rate = rates["foundation_concrete_usd_per_cy"]
        s = stage(eid)
        base = f"{nB:g}^2 x {nh / 12:.2f} ft - {oB:g}^2 x {oh / 12:.2f} ft = {dcy * 27:.1f} cf = {dcy:.2f} cy x {_money(rate)}/cy (assumed all-in)"
        if s == "erected":
            k, mob = rates["poured_footing_factor"], rates["poured_footing_mobilization_usd"]
            add("foundation", eid, f"{eid} enlarge poured footing {oB:g} -> {nB:g} ft", dcy * rate * k + mob,
                base + f" x {k} (enlarging a poured footing) + {_money(mob)} mobilization (excavate, dowel, shore)")
        else:
            add("foundation", eid, f"{eid} footing {oB:g} -> {nB:g} ft", dcy * rate, base)
    if records:
        fee = rates["eng_redesign_usd_per_calc_record"]
        add("engineering", None, f"EOR redesign of {len(records)} calc record(s)", len(records) * fee,
            f"{len(records)} records x {_money(fee)}/record (assumed ~3 h at $150/h each)")
    resub_fee = rates["resubmittal_usd_per_package"]
    for s in subs_out:
        k = 1.0 if s["status"] in ("approved", "fabricated", "delivered", "erected") else (0.5 if s["status"] == "submitted" else 0.0)
        if k:
            lines.append({"category": "resubmittal", "element_id": None, "description": f"Resubmit {s['number']} {s['title']}",
                          "figure": fig(resub_fee * k, "USD", f"{_money(resub_fee)}/package (assumed detailer revision + re-issue)"
                                        + (" x 0.5 (still under review)" if k < 1 else "")),
                          "platform": s["platform"], "link": s["link"]})
    by_cat: dict[str, float] = {}
    for ln in lines:
        by_cat[ln["category"]] = by_cat.get(ln["category"], 0.0) + ln["figure"]["value"]
    total = sum(by_cat.values())
    cost = {"lines": lines,
            "by_category": {k: fig(v, "USD", f"sum of {sum(1 for x in lines if x['category'] == k)} '{k}' lines")
                            for k, v in by_cat.items()},
            "total": fig(total, "USD", "sum of all lines; unit rates in assumptions.rates (synthetic, not a quote)"),
            "range": {"low": fig(total * 0.8, "USD", "total x 0.8 (ROM accuracy band, assumed)"),
                      "high": fig(total * 1.35, "USD", "total x 1.35 (ROM accuracy band, assumed)")}}

    # ---------------------------------------------------------------- schedule
    acts = {}
    for a in adapters:
        if a.supports(SCHEDULE_ACTIVITIES):
            acts = {r.ref: r for r in a.list(SCHEDULE_ACTIVITIES)}
            break
    sched_acts, method, knock, holds = [], "", [], {}
    finish_delay = float_used = project_slip = 0
    proj_before = proj_after = contract = None
    if st is not None:
        plan = _rework_plan(sorted(changed), stage, st, rules, {f["id"] for f in ftgs}, warnings)
        holds = plan["holds"]
    if st is not None and plan["inserted"]:
        res = st.reschedule(plan["inserted"])
        method = ("CPM re-run from the data date (the morning after approval) with the change's work inserted as "
                  "activities: each starts no earlier than the data date and must finish before the element's next open "
                  "activity (working days, Mon-Fri)")
        proj_before, proj_after, contract = res["finish_before"], res["finish_after"], res["contract_finish"]
        finish_delay = res["days_past_contract"]
        project_slip = res["finish_slip_days"]
        pf0 = res["project_float_before"]
        float_used = max(0, pf0 - max(res["project_float_after"], 0))
        float_basis = f"project float (contract finish - forecast finish) {pf0} -> {res['project_float_after']} working days"
        targets = {}
        for t in sorted({t for x in plan["inserted"] for t in x["holds"]}):
            a = acts.get(t)
            r = res["activities"].get(t, {})
            # working days this held activity pushes the project finish: its slip beyond its own float above
            # the project float (total float includes the contract's project float)
            push = max(0, r.get("slip_days", 0) - (r.get("float_before", 0) - pf0))
            targets[t] = {"ref": t, "title": a.title if a else t, "status": r.get("status"),
                          "early_finish_before": r.get("early_finish_before"), "early_finish_after": r.get("early_finish_after"),
                          "slip_days": r.get("slip_days"), "float_before": r.get("float_before"),
                          "float_after": r.get("float_after"), "finish_push": push,
                          "hold_binds": bool(r.get("hold_binds")),
                          # the change's work on this activity is what moves the project finish (not another path)
                          "drives_finish": bool(r.get("hold_binds")) and project_slip > 0 and push == project_slip,
                          "platform": a.platform if a else None, "link": a.links.get("self") if a else None}
        for e, h in holds.items():
            tg = targets.get(h["target"]) if h["target"] else None
            if tg:
                h.update({"target_title": tg["title"], "target_float": tg["float_before"],
                          "drives_finish": tg["drives_finish"]})
        for x in plan["inserted"]:
            r = res["inserted"][x["ref"]]
            held = [targets[t] for t in x["holds"]]
            worst = max(held, key=lambda h: (h["finish_push"], h["slip_days"] or 0)) if held else {}
            sched_acts.append({"ref": x["ref"], "title": x["name"], "added_days": x["dur"], "reasons": x["reasons"],
                               "inserted": True, "after": x["after"], "early_start": r["early_start"],
                               "early_finish": r["early_finish"], "holds": held,
                               # the most-delayed activity it holds (what the panel's one-line summary shows)
                               "early_finish_before": worst.get("early_finish_before"),
                               "early_finish_after": worst.get("early_finish_after"), "slip_days": worst.get("slip_days"),
                               "float_before": worst.get("float_before"), "float_after": worst.get("float_after"),
                               "platform": worst.get("platform"), "link": worst.get("link")})
        knock = [{"ref": k, "slip_days": v["slip_days"], "float_after": v["float_after"]}
                 for k, v in res["activities"].items() if k not in targets and v["slip_days"]]
    elif st is None and changed:
        # live adapter: no network to insert into, so each element's cumulative stage work lands on the
        # first open activity of its schedule chain and float arithmetic stands in for the CPM
        extra: dict[str, dict] = {}
        for eid in sorted(changed):
            chain = [r for r, a in acts.items() if eid in a.element_ids]
            ref = next((r for r in chain if acts[r].status != "complete"), None)
            days, why = _stage_days(stage(eid), eid in {f["id"] for f in ftgs}, 1, rules)
            if ref and days:
                e = extra.setdefault(ref, {"days": 0, "reasons": []})
                e["days"] = max(e["days"], days)
                e["reasons"].append(f"{eid}: {stage(eid)}: {why}")
        method = "float arithmetic (no CPM available): delay = max(0, added days - total float)"
        float_basis = "largest single draw on an activity's total float: min(added days, float before)"
        unknown = []
        for ref, e in sorted(extra.items()):
            n = int(-(-e["days"] // 1))
            a = acts.get(ref)
            fl = a.total_float if a else None
            if fl is None:   # float not reported: nothing is known to absorb the delay, so assume none
                unknown.append(ref)
            fl0 = fl if fl is not None else 0
            float_used = max(float_used, min(n, fl0))
            project_slip = max(project_slip, n - fl0)
            sched_acts.append({"ref": ref, "title": a.title if a else ref, "added_days": n, "reasons": e["reasons"],
                               "float_before": fl, "float_after": fl - n if fl is not None else None,
                               "float_known": fl is not None, "platform": a.platform if a else None,
                               "link": a.links.get("self") if a else None})
        if unknown:
            float_basis += (f"; total float not reported for {', '.join(unknown)}: assumed 0 there (every added day "
                            "counts as delay), an upper bound")
            warnings.append(f"schedule float unknown for {len(unknown)} activit{'y' if len(unknown) == 1 else 'ies'} "
                            f"({', '.join(unknown)}): delay assumes no float there")
        finish_delay = max(0, project_slip)
        if not sched_acts:
            method = "no schedule-affecting changes"
    else:
        float_basis = "no activity affected"
        method = "no schedule-affecting changes"
    schedule = {
        "activities": sched_acts, "knock_on": knock[:30], "method": method,
        "element_holds": holds,
        "float_consumed": fig(float_used, "working days", float_basis),
        "forecast_slip": fig(project_slip, "working days", "change in forecast project finish from the CPM re-run"),
        "finish_delay": fig(finish_delay, "working days",
                            "working days the new forecast finish passes the contract completion date (0 = absorbed by float)"),
        "project_finish_before": proj_before, "project_finish_after": proj_after, "contract_finish": contract,
        "rules": rules,
    }

    worst = max([stage(e) for e in changed] or ["design"], key=stage_rank)
    flagged = [s for s in subs_out if s["flag"] in ("approved", "fabricated_steel", "delivered_steel", "erected_steel", "poured_concrete")]
    summary = {
        "total_cost": cost["total"], "cost_range": cost["range"], "finish_delay": schedule["finish_delay"],
        "forecast_slip": schedule["forecast_slip"], "float_consumed": schedule["float_consumed"],
        "worst_stage": worst,
        "counts": {"submittals": len(subs_out), "submittals_flagged": len(flagged), "rfis": len(rfis_out),
                   "sheets": len(sheets_out), "calc_records": len(records), "schedule_activities": len(sched_acts)},
        "headline": (f"{_money(total)} est. ({_money(total * 0.8)}-{_money(total * 1.35)}), "
                     f"{len(subs_out)} submittals ({len(flagged)} approved or later), {len(rfis_out)} RFIs, "
                     f"forecast slip {project_slip} wd, {finish_delay} wd past contract; worst element stage: {worst}"),
    }
    return {"summary": summary, "submittals": subs_out, "rfis": rfis_out, "sheets": sheets_out, "spec_articles": specs,
            "calc_records": records, "cost": cost, "schedule": schedule,
            "assumptions": {"as_of": st.as_of if st is not None else None, "rates": rates, "schedule_rules": rules,
                            "note": "synthetic project; unit rates are stated assumptions, not quotes"},
            "warnings": warnings, "estimate": True, "synthetic": True}


# ---------------------------------------------------------------- schedule: the change's work as activities
def _stage_days(stage: str, is_footing: bool, n_field: int, rules: dict) -> tuple[float, str]:
    """Working days of the cumulative work (synthetic.STAGE_WORK) for one element at `stage`, in series."""
    from .synthetic import STAGE_WORK
    parts = []
    for step in STAGE_WORK.get(stage, ()):
        if step == "field_rework":
            if is_footing:
                parts.append(("enlarge poured footing", rules["poured_footing"]))
            else:
                parts.append(("field swap", max(rules["field_rework_min"], rules["field_rework_per_member"] * n_field)))
        else:
            parts.append((step.replace("_", " "), rules[step]))
    return sum(d for _, d in parts), " + ".join(f"{w} {d:g} d" for w, d in parts)


def _rework_plan(changed: list[str], stage, st, rules: dict, footings: set, warnings: list) -> dict:
    """The change's work for the synthetic CPM: inserted activities and, per element, the activity its
    work must finish before (its hold target).

    Per element at stage s (synthetic.STAGE_WORK, cumulative): revise under review (submitted) | one shared
    EOR redesign + re-detail + re-review (approved or later) -> re-fabricate the replacement (fabricated or
    later, one per hold target) -> field swap / footing enlargement (erected, one per hold target). The
    hold target is the first open activity of the element's chain past its stage, then its downstream
    activities, then (all done) the first open activity after them - never nothing while the project runs."""
    from .synthetic import STAGE_HOLD_FROM
    ins: dict[str, dict] = {}

    def add(ref, name, dur, after, reason, hold=None):
        x = ins.setdefault(ref, {"ref": ref, "name": name, "dur": 0, "after": list(after), "holds": [], "reasons": []})
        x["dur"] = max(x["dur"], int(-(-dur // 1)))
        if reason not in x["reasons"]:
            x["reasons"].append(reason)
        if hold and hold not in x["holds"]:
            x["holds"].append(hold)
        return x

    holds: dict[str, dict] = {}
    field: dict[str, list[str]] = {}
    for eid in changed:
        s = stage(eid)
        ix = st.element_index.get(eid)
        if s not in STAGE_HOLD_FROM:
            continue
        if ix is None:
            warnings.append(f"{eid}: {s} but not on the synthetic schedule; its schedule effect is not modelled")
            continue
        target = st.hold_target(list(ix["chain"][STAGE_HOLD_FROM[s]:]) + list(ix["downstream"]))
        holds[eid] = {"stage": s, "target": target}
        if target is None:
            warnings.append(f"{eid}: every activity after it is complete; its rework is outside the schedule")
            continue
        if s == "submitted":
            add("CO-REVISE", "Change: revise shop drawings under review", rules["revise_under_review"], [],
                f"{eid}: submitted, revise under review ({rules['revise_under_review']} d)", target)
            continue
        add("CO-REDESIGN", "Change: EOR redesign, re-detail, re-review", rules["redesign"], [],
            f"{eid}: shop drawings {s}: EOR redesign 5 + re-detail 5 + re-review 5 ({rules['redesign']} d)",
            target if s == "approved" else None)
        if s == "approved":
            continue
        rf = add(f"CO-REFAB:{target}", f"Change: re-fabricate replacements (before {target})", rules["refabricate"],
                 ["CO-REDESIGN"], f"{eid}: {s}, re-fabricate the replacement ({rules['refabricate']} d)",
                 target if s in ("fabricated", "delivered") else None)
        if s == "erected":
            if eid in footings:
                add(f"CO-FOOTING:{target}", f"Change: enlarge poured footings (before {target})", rules["poured_footing"],
                    [rf["ref"]], f"{eid}: poured, enlarge the footing ({rules['poured_footing']} d)", target)
            else:
                field.setdefault(target, []).append(eid)
    for target, ids in field.items():
        d = max(rules["field_rework_min"], rules["field_rework_per_member"] * len(ids))
        x = add(f"CO-FIELD:{target}", f"Change: swap erected pieces in the field (before {target})", d,
                [f"CO-REFAB:{target}"], f"{len(ids)} erected pieces x {rules['field_rework_per_member']} d "
                f"(min {rules['field_rework_min']} d) = {d:g} d", target)
        x["reasons"] += [f"{e}: erected" for e in ids]
    order = {"CO-REVISE": 0, "CO-REDESIGN": 1}
    return {"inserted": sorted(ins.values(), key=lambda x: (order.get(x["ref"], 2), x["ref"])), "holds": holds}
