"""Seed a Procore SANDBOX project / an ACC TRIAL project from the synthetic v2 model, so the change-order
panel can show REAL platform records linked back to registry elements.

  uv run python scripts/seed_platform_sandbox.py procore                 # DRY RUN (default): prints what it would write
  uv run python scripts/seed_platform_sandbox.py acc
  uv run python scripts/seed_platform_sandbox.py procore --apply --confirm-project "<exact project name>"
  uv run python scripts/seed_platform_sandbox.py acc     --apply --confirm-project "<exact project name>"
  uv run python scripts/seed_platform_sandbox.py procore --recorded <file.json>   # offline, against recorded responses

What it writes (from synthetic.build_state(design.json), the same state the mocks reshape):
  - every RFI (7): subject/title, question, the elements/connections it is about, a calc-graph marker
  - every submittal package (16): one per frame line / level / sequence, with its status as far as the
    platform lets an API set it (Procore: status_id from the company's submittal statuses; ACC: created as
    draft - later states need workflow transitions, so the target status is written into the description)
  - every change event (4): Procore change event with a manual cost estimate line per synthetic line item;
    ACC: a PCO (Cost change order type "pco") with externalId/externalSystem
Each record carries the calc-graph marker (platforms/live/links.py) the live adapters read back.

SAFETY - a write happens only when ALL hold, otherwise the script refuses before its first request:
  1. --apply is given (default is a dry run that sends GETs only, to resolve ids, or nothing with --offline);
  2. Procore: the configured environment is the Developer Sandbox or Monthly Sandbox (hosts
     sandbox.procore.com / api-monthly.procore.com) - production hosts are refused in oauth.procore_env();
     ACC: the project id is listed in `seed_allowed_project_ids` in data/secrets/aps_app.json (the account owner adds the
     trial project there by hand: ACC has no separate sandbox host, so the allowlist is the guard);
     Procore also requires the project id in `seed_allowed_project_ids` of data/secrets/procore_app.json;
  3. --confirm-project equals the project's name as the API returns it (typed by a human, not defaulted).
Re-running is idempotent: records whose marker ref already exists in the project are skipped.
Never prints tokens or secrets; the request log is method + path + status only.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from calcgraph.platforms import get_state, load_design  # noqa: E402
from calcgraph.platforms.live import links, oauth  # noqa: E402
from calcgraph.platforms.live import secrets as store  # noqa: E402
from calcgraph.platforms.live.transport import Recorded, Session  # noqa: E402

SANDBOX_API_HOSTS = {"https://sandbox.procore.com", "https://api-monthly.procore.com"}
EL_INLINE_MAX = 12


class Refused(SystemExit):
    pass


def _marker(rec: dict) -> str:
    ids = rec.get("element_ids") or []
    return links.marker(rec["ref"], ids if len(ids) <= EL_INLINE_MAX else None)


def _elements_line(rec: dict) -> str:
    ids = rec.get("element_ids") or []
    shown = ", ".join(ids[:EL_INLINE_MAX]) + (f" (+{len(ids) - EL_INLINE_MAX} more)" if len(ids) > EL_INLINE_MAX else "")
    return f"Registry elements: {shown}" if ids else ""


def _typed(model, body: dict, wrapper: str, fill: dict) -> list[str]:
    """Validate `body` against the generated (spec-derived) model. Ids that only a live lookup can supply are
    filled with a placeholder 0 FOR THE CHECK ONLY and returned as `unresolved` (never sent: --apply refuses)."""
    inner = dict(body[wrapper])
    missing = [k for k, v in fill.items() if k not in inner]
    for k in missing:
        inner[k] = fill[k]
    model.from_dict({wrapper: inner})
    return missing


def _digits(spec: str) -> str:
    return re.sub(r"\D", "", spec or "")


# ============================================================================== Procore
def plan_procore(state, existing_refs: set[str], lookups: dict) -> list[dict]:
    from calcgraph.platforms.live.generated.procore_client.models.create_change_event_body import CreateChangeEventBody
    from calcgraph.platforms.live.generated.procore_client.models.create_rfi_body import CreateRfiBody
    from calcgraph.platforms.live.generated.procore_client.models.create_submittal_body import CreateSubmittalBody
    plan = []
    spec_ids = lookups.get("spec_ids", {})
    for r in state.rfis:
        if r["ref"] in existing_refs:
            plan.append({"kind": "rfi", "ref": r["ref"], "skip": "already in project"})
            continue
        body = {"rfi": {"subject": r["subject"],
                        "question": {"body": "\n\n".join(x for x in (r["question"], _elements_line(r), _marker(r)) if x)},
                        "reference": f"calc-graph {r['ref']}", "draft": r["status"] == "draft"}}
        if lookups.get("rfi_manager_id"):
            body["rfi"]["rfi_manager_id"] = lookups["rfi_manager_id"]
        if spec_ids.get(_digits(r.get("spec_section"))):
            body["rfi"]["specification_section_id"] = spec_ids[_digits(r["spec_section"])]
        un = _typed(CreateRfiBody, body, "rfi", {"rfi_manager_id": 0})   # typed against the spec before sending
        plan.append({"kind": "rfi", "ref": r["ref"], "body": body, **({"unresolved": un} if un else {})})
    status_ids = lookups.get("submittal_status_ids", {})
    for s in state.submittals:
        if s["ref"] in existing_refs:
            plan.append({"kind": "submittal", "ref": s["ref"], "skip": "already in project"})
            continue
        desc = "\n".join(x for x in (f"Synthetic calc-graph package ({s['package_kind']}); target status: {s['status']}.",
                                     _elements_line(s), _marker(s)) if x)
        body = {"submittal": {"number": s["number"].split("-")[-1], "title": s["title"], "description": desc,
                              "revision": str(s.get("revision") or 0)}}
        if s["dates"].get("due"):
            body["submittal"]["due_date"] = s["dates"]["due"]
        if spec_ids.get(_digits(s["spec_section"])):
            body["submittal"]["specification_section_id"] = spec_ids[_digits(s["spec_section"])]
        sid = status_ids.get("draft" if s["status"] == "draft" else "open" if s["status"] == "submitted" else "closed")
        if sid:
            body["submittal"]["status_id"] = sid
        _typed(CreateSubmittalBody, body, "submittal", {})
        plan.append({"kind": "submittal", "ref": s["ref"], "body": body})
    for c in state.change_events:
        if c["ref"] in existing_refs:
            plan.append({"kind": "change_event", "ref": c["ref"], "skip": "already in project"})
            continue
        body = {"change_event": {
            "title": c["title"], "scope": "tbd",
            "description": "\n".join(x for x in (c["description"], _elements_line(c), _marker(c),
                                                 "Amounts are calc-graph ESTIMATES from stated unit rates.") if x),
            "external_data": {"origin_id": f"calc-graph:{c['ref']}", "origin_data": "calc-graph synthetic v2 model"},
            "change_items": [{"description": li["description"][:255],
                              "cost_impact": {"estimate": {"amount": round(li["amount"], 2), "calculation_strategy": "manual"}}}
                             for li in c["line_items"]]}}
        if lookups.get("change_event_status_id"):
            body["change_event"]["status"] = {"id": lookups["change_event_status_id"]}
        un = _typed(CreateChangeEventBody, body, "change_event", {"status": {"id": 0}})
        plan.append({"kind": "change_event", "ref": c["ref"], "body": body, **({"unresolved": un} if un else {})})
    return plan


def run_procore(args, state) -> dict:
    from calcgraph.platforms.live.generated.procore_client import AuthenticatedClient
    from calcgraph.platforms.live.generated.procore_client.api.calcgraph import (
        create_change_event, create_rfi, create_submittal, list_change_event_statuses, list_change_events,
        list_potential_rfi_managers, list_projects, list_rfis, list_specification_sections, list_submittal_statuses,
        list_submittals)
    from calcgraph.platforms.live.generated.procore_client.models.create_change_event_body import CreateChangeEventBody
    from calcgraph.platforms.live.generated.procore_client.models.create_rfi_body import CreateRfiBody
    from calcgraph.platforms.live.generated.procore_client.models.create_submittal_body import CreateSubmittalBody
    cfg = store.app_config("procore") if not args.recorded else {"env": "sandbox", "company_id": 1, "project_id": 2}
    if args.recorded:
        cfg.update(json.load(open(args.recorded)).get("config", {}))
    env = oauth.procore_env(cfg)
    if env["api"] not in SANDBOX_API_HOSTS:
        raise Refused(f"refused: {env['api']} is not a Procore sandbox host")
    cid, pid = int(cfg.get("company_id") or 0), int(cfg.get("project_id") or 0)
    if args.offline:
        return {"platform": "procore", "env": env["name"], "mode": "dry-run (offline, no lookups)",
                "plan": plan_procore(state, set(), {})}
    if not (cid and pid):
        raise Refused("refused: PROCORE_COMPANY_ID / PROCORE_PROJECT_ID not configured (scripts/platform_auth.py use procore ...)")
    rec = Recorded(args.recorded) if args.recorded else None
    s = Session("procore", env["api"], AuthenticatedClient, recorded=rec)
    projs = s.procore_pages(list_projects, company_id=cid, procore_company_id=cid)
    proj = next((p for p in projs if int(p["id"]) == pid), None)
    if proj is None:
        raise Refused(f"refused: project {pid} is not visible in company {cid} on {env['name']}")
    existing = set()
    for raw in s.procore_pages(list_rfis, project_id=pid, procore_company_id=cid):
        q = " ".join((x.get("body") or "") for x in raw.get("questions") or [] if isinstance(x, dict))
        existing.add(links.parse(raw.get("reference"), q)[0])
    for raw in s.procore_pages(list_submittals, project_id=pid, procore_company_id=cid):
        existing.add(links.parse(raw.get("description"))[0])
    for raw in s.procore_pages(list_change_events, project_id=pid, procore_company_id=cid):
        existing.add(links.parse(raw.get("description"), ((raw.get("external_data") or {}).get("origin_id") or "")
                                 .replace("calc-graph:", "calc-graph "))[0])
    existing.discard(None)
    lookups: dict = {}
    mgrs, _ = s.call(list_potential_rfi_managers, project_id=pid, procore_company_id=cid)
    if mgrs:
        lookups["rfi_manager_id"] = int(args.rfi_manager_id or mgrs[0]["id"])
    specs, _ = s.call(list_specification_sections, project_id=pid, procore_company_id=cid)
    lookups["spec_ids"] = {_digits(x.get("number")): x["id"] for x in specs or [] if x.get("number")}
    sts = s.procore_pages(list_submittal_statuses, company_id=cid, procore_company_id=cid)
    for cat in ("Draft", "Open", "Closed"):
        pick = [x for x in sts if x.get("status") == cat]
        pick = [x for x in pick if cat != "Closed" or "approv" in (x.get("name") or "").lower()] or pick
        if pick:
            lookups["submittal_status_ids"] = {**lookups.get("submittal_status_ids", {}), cat.lower(): pick[0]["id"]}
    ce_sts, _ = s.call(list_change_event_statuses, company_id=str(cid), procore_company_id=cid)
    ce_list = (ce_sts or {}).get("data") if isinstance(ce_sts, dict) else ce_sts
    openish = [x for x in ce_list or [] if (x.get("name") or "").lower() in ("open", "pending")] or \
              [x for x in ce_list or [] if x.get("default_status")]
    if openish:
        lookups["change_event_status_id"] = int(openish[0]["id"])   # v2 list returns a string id; the v1.1 create body takes an integer
    plan = plan_procore(state, existing, lookups)
    report = {"platform": "procore", "env": env["name"], "api": env["api"], "company_id": cid, "project_id": pid,
              "project_name": proj.get("name"), "lookups": {k: v for k, v in lookups.items() if k != "spec_ids"},
              "spec_sections_matched": sorted(lookups["spec_ids"]), "existing_refs": sorted(existing)}
    if not args.apply:
        report.update(mode="dry-run", plan=plan)
        return report
    allowed = {int(x) for x in cfg.get("seed_allowed_project_ids") or []}
    if pid not in allowed:
        raise Refused(f"refused: project {pid} not in seed_allowed_project_ids of data/secrets/procore_app.json")
    if args.confirm_project != proj.get("name"):
        raise Refused(f"refused: --confirm-project must equal the project name exactly ({proj.get('name')!r})")
    unresolved = sorted({u for p in plan for u in p.get("unresolved", [])})
    if unresolved:
        raise Refused(f"refused: required ids not resolvable in this project: {unresolved} "
                      "(RFI manager / change-event status); fix in Procore or pass --rfi-manager-id")
    written = []
    ops = {"rfi": (create_rfi, CreateRfiBody, {"project_id": pid}),
           "submittal": (create_submittal, CreateSubmittalBody, {"project_id": pid}),
           "change_event": (create_change_event, CreateChangeEventBody, {"project_id": pid})}
    for p in plan:
        if "body" not in p:
            continue
        op, model, kw = ops[p["kind"]]
        data, _ = s.call(op, body=model.from_dict(p["body"]), procore_company_id=cid, **kw)
        written.append({"kind": p["kind"], "ref": p["ref"], "id": (data or {}).get("id")})
    report.update(mode="applied", written=written, parse_errors=s.parse_errors)
    return report


# ============================================================================== ACC
def plan_acc(state, existing_refs: set[str], lookups: dict) -> list[dict]:
    plan = []
    for r in state.rfis:
        if r["ref"] in existing_refs:
            plan.append({"kind": "rfi", "ref": r["ref"], "skip": "already in project"})
            continue
        plan.append({"kind": "rfi", "ref": r["ref"], "body": {
            "title": r["subject"][:255], "status": "draft", "reference": links.short(r["ref"]),
            "question": "\n\n".join(x for x in (r["question"], _elements_line(r), _marker(r)) if x)}})
    specs = lookups.get("spec_ids", {})
    for s in state.submittals:
        if s["ref"] in existing_refs:
            plan.append({"kind": "submittal", "ref": s["ref"], "skip": "already in project"})
            continue
        body = {"title": s["title"][:255], "stateId": "draft", "typeId": lookups.get("type_id"),
                "specId": specs.get(_digits(s["spec_section"])) or lookups.get("fallback_spec_id"),
                "description": "\n".join(x for x in (f"Synthetic calc-graph package; target status: {s['status']} "
                                                     "(ACC states beyond draft need workflow transitions).",
                                                     _elements_line(s), _marker(s)) if x)}
        if s["dates"].get("due"):
            body["requiredApprovalDate"] = s["dates"]["due"]
        plan.append({"kind": "submittal", "ref": s["ref"], "body": body,
                     **({} if body["typeId"] and body["specId"] else {"blocked": "no item type / spec section in project"})})
    for c in state.change_events:
        if c["ref"] in existing_refs:
            plan.append({"kind": "pco", "ref": c["ref"], "skip": "already in project"})
            continue
        plan.append({"kind": "pco", "ref": c["ref"], "body": {
            "name": c["title"][:1024], "scope": "tbd", "externalId": f"calc-graph:{c['ref']}", "externalSystem": "calc-graph",
            "description": "\n".join(x for x in (c["description"], _elements_line(c), _marker(c),
                                                 f"Estimate {c['amount']:.2f} USD (calc-graph unit rates).") if x)[:2048]}})
    return plan


def run_acc(args, state) -> dict:
    from calcgraph.platforms.live.acc_rest import BASE, AccRest, project_id_for_acc
    from calcgraph.platforms.live.generated.aps_dm_client import AuthenticatedClient
    from calcgraph.platforms.live.generated.aps_dm_client.api.calcgraph import get_project
    cfg = store.app_config("aps") if not args.recorded else {"hub_id": "b.hub", "project_id": "b.proj"}
    if args.recorded:
        cfg.update(json.load(open(args.recorded)).get("config", {}))
    if args.offline:
        return {"platform": "acc", "mode": "dry-run (offline, no lookups)", "plan": plan_acc(state, set(), {})}
    if not (cfg.get("hub_id") and cfg.get("project_id")):
        raise Refused("refused: ACC_HUB_ID / ACC_PROJECT_ID not configured (scripts/platform_auth.py use aps ...)")
    dm_pid = cfg["project_id"] if cfg["project_id"].startswith("b.") else "b." + cfg["project_id"]
    pid = project_id_for_acc(dm_pid)
    rec = Recorded(args.recorded) if args.recorded else None
    s = Session("aps", BASE, AuthenticatedClient, recorded=rec)
    proj, _ = s.call(get_project, hub_id=cfg["hub_id"], project_id=dm_pid)
    name = (((proj or {}).get("data") or {}).get("attributes") or {}).get("name")
    api = AccRest(s, pid, cfg.get("region"))
    existing = set()
    for r in api.rfis():
        existing.add(links.parse(r.question, r.reference)[0])
    for x in api.submittals():
        existing.add(links.parse(x.description)[0])
    for c in api.change_orders("pco"):
        existing.add(links.parse((c.externalId or "").replace("calc-graph:", "calc-graph "), c.description)[0])
    existing.discard(None)
    specs = api.specs()
    types = api.item_types()
    lookups = {"spec_ids": {_digits(x.identifier): x.id for x in specs if x.identifier},
               "fallback_spec_id": specs[0].id if specs else None,
               "type_id": next((t.get("id") for t in types if "shop" in (t.get("value") or t.get("name") or "").lower()),
                               types[0].get("id") if types else None)}
    plan = plan_acc(state, existing, lookups)
    report = {"platform": "acc", "hub_id": cfg["hub_id"], "project_id": pid, "project_name": name,
              "spec_sections_matched": sorted(lookups["spec_ids"]), "item_type_id": lookups["type_id"],
              "existing_refs": sorted(existing)}
    if not args.apply:
        report.update(mode="dry-run", plan=plan)
        return report
    allowed = {project_id_for_acc(x) for x in cfg.get("seed_allowed_project_ids") or []}
    if pid not in allowed:
        raise Refused(f"refused: ACC project {pid} not in seed_allowed_project_ids of data/secrets/aps_app.json")
    if not name or args.confirm_project != name:
        raise Refused(f"refused: --confirm-project must equal the project name exactly ({name!r})")
    written = []
    for p in plan:
        if "body" not in p or p.get("blocked"):
            continue
        if p["kind"] == "rfi":
            out = api.create_rfi(p["body"])
        elif p["kind"] == "submittal":
            out = api.create_submittal(p["body"])
        else:
            out = api.create_change_order("pco", p["body"])
        written.append({"kind": p["kind"], "ref": p["ref"], "id": out.id})
    report.update(mode="applied", written=written, blocked=[p["ref"] for p in plan if p.get("blocked")])
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("platform", choices=["procore", "acc"])
    ap.add_argument("--apply", action="store_true", help="actually write (default: dry run)")
    ap.add_argument("--confirm-project", help="exact project name, required with --apply")
    ap.add_argument("--offline", action="store_true", help="dry run with no network at all (no id lookups)")
    ap.add_argument("--recorded", help="serve requests from a recorded-responses JSON file (no network)")
    ap.add_argument("--rfi-manager-id", type=int)
    ap.add_argument("--design", help="design.json (default data/synthetic_v2/design.json)")
    a = ap.parse_args()
    if a.offline and a.apply:
        ap.error("--offline is a dry run; drop --apply")
    state = get_state(load_design(a.design))
    try:
        rep = run_procore(a, state) if a.platform == "procore" else run_acc(a, state)
    except Refused as e:
        print(str(e), file=sys.stderr)
        return 2
    except Exception as e:   # noqa: BLE001
        print(store.redact(f"{type(e).__name__}: {e}"), file=sys.stderr)
        return 1
    plan = rep.get("plan") or []
    counts = {}
    for p in plan:
        k = f"{p['kind']}:{'skip' if 'skip' in p else 'blocked' if p.get('blocked') else 'write'}"
        counts[k] = counts.get(k, 0) + 1
    rep["counts"] = counts or {w["kind"]: sum(1 for x in rep.get("written", []) if x["kind"] == w["kind"]) for w in rep.get("written", [])}
    print(json.dumps(rep, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
