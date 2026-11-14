"""Build the RECORDED responses the platform contract tests replay - synthetic, ours, shaped by the specs.

  uv run python scripts/make_platform_recordings.py

Writes backend/calcgraph/platforms/live/recorded/:
  procore_sandbox.json        a sandbox project AFTER seeding (records carry calc-graph markers) + 1 unmarked RFI
  procore_sandbox_empty.json  the same project BEFORE seeding (lists empty; create endpoints answer 201)
  acc_trial.json              an ACC trial project after seeding (+ issues, budgets, sheets, OCO)
  acc_trial_empty.json        before seeding
  forma.json                  a Forma project with one proposal whose elements are named by registry id

Every Procore body is validated against the response schema of its operation in
platforms/live/generated/procore_client.openapi.json (field names, JSON types, enums, date formats) with the
same checker the mock adapters use (_spec.check), so a recording cannot carry a field the spec does not
define. APS Data Management / Issues bodies are validated by the generated models during the contract run
(transport.Session records any parse failure). ACC RFIs / Submittals / Cost / Sheets and Forma bodies use
only the fields named on their reference pages (acc_rest.py / forma_live.py docstrings).
Nothing here is real data: ids are deterministic, names fictional.
"""
from __future__ import annotations

import copy
import json
import os
import sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from calcgraph.platforms import get_state, load_design  # noqa: E402
from calcgraph.platforms._spec import check  # noqa: E402
from calcgraph.platforms.live import links  # noqa: E402
from calcgraph.platforms.synthetic import _int_id, _uuid  # noqa: E402

OUT = os.path.join(ROOT, "backend", "calcgraph", "platforms", "live", "recorded")
GEN = os.path.join(ROOT, "backend", "calcgraph", "platforms", "live", "generated")
C, P, AREA = 4900001, 5800002, 7700003
PROC_SPEC = json.load(open(os.path.join(GEN, "procore_client.openapi.json")))


def _resp_schema(path: str, method: str) -> dict:
    r = PROC_SPEC["paths"][path][method]["responses"]
    s = (r.get("200") or r.get("201"))["content"]["application/json"]["schema"]
    return s


def _validated(path: str, method: str, body):
    s = _resp_schema(path, method)
    check(body, s, f"{method.upper()} {path}")
    return body


def _ts(d: str | None, h: int = 15) -> str | None:
    return f"{d}T{h:02d}:00:00Z" if d else None


def _route(method, path, body, status=200, query=None, headers=None):
    r = {"method": method, "path": path, "status": status, "body": body}
    if query:
        r["query"] = query
    if headers:
        r["headers"] = headers
    return r


def _mk(st, ref, elements):
    return links.marker(ref, elements if len(elements) <= 12 else None)


# ============================================================================== Procore
def procore(state, seeded: bool) -> dict:
    user = {"id": 7100001, "login": "pm@tidewater.example", "name": "Marisol Okafor"}
    subs, rfis, ces = [], [], []
    if seeded:
        for i, s in enumerate(state.submittals):
            cat = "Draft" if s["status"] == "draft" else "Open" if s["status"] == "submitted" else "Closed"
            subs.append({"id": _int_id("rec-sub", s["ref"], base=60000000, span=9999999), "number": s["number"].split("-")[-1],
                         "formatted_number": s["number"], "title": s["title"], "revision": str(s.get("revision") or 0),
                         "description": f"target status: {s['status']}\n{_mk(state, s['ref'], s['element_ids'])}",
                         "status": {"id": {"Draft": 183100, "Open": 183101, "Closed": 183102}[cat],
                                    "name": {"Draft": "Draft", "Open": "Open", "Closed": "Approved"}[cat], "status": cat},
                         "specification_section": {"id": _int_id("spec", s["spec_section"], base=12000, span=999),
                                                   "number": s["spec_section"], "description": s["spec_title"],
                                                   "label": f"{s['spec_section']} - {s['spec_title']}"},
                         "type": {"id": 501, "name": "Shop Drawing" if "product" not in s["package_kind"] else "Product Data",
                                  "translated_name": "Shop Drawing"},
                         "due_date": s["dates"].get("due"), "created_at": _ts(s["dates"].get("submitted") or state.as_of),
                         "updated_at": _ts(state.as_of), "private": False, "current_revision": True,
                         **({"actual_delivery_date": s["dates"]["delivered"]} if s["dates"].get("delivered") else {})})
        for r in state.rfis:
            rfis.append({"id": _int_id("rec-rfi", r["ref"], base=81000000, span=999999), "number": r["number"][4:],
                         "full_number": r["number"], "subject": r["subject"], "reference": f"calc-graph {r['ref']}",
                         "status": {"draft": "draft", "closed": "closed"}.get(r["status"], "open"),
                         "questions": [{"id": _int_id("rec-q", r["ref"], base=1, span=99999),
                                        "body": f"{r['question']}\n\n{_mk(state, r['ref'], r['element_ids'])}"}],
                         "created_at": _ts(r["dates"].get("created")), "updated_at": _ts(state.as_of),
                         "private": False, "rfi_manager": user, "assignee": user})
        for c in state.change_events:
            ces.append({"id": _int_id("rec-ce", c["ref"], base=91000, span=9999), "number": c["number"], "title": c["title"],
                        "description": f"{c['description']}\n{_mk(state, c['ref'], c['element_ids'])}",
                        "status": {"id": 301, "name": "Open", "mapped_to_status": "open"}, "scope": "tbd",
                        "external_data": {"origin_id": f"calc-graph:{c['ref']}", "origin_data": "calc-graph synthetic v2 model"},
                        "change_items": [{"id": _int_id("rec-ci", c["ref"], k, base=1, span=999999), "description": li["description"],
                                          "cost_impact": {"estimate": {"amount": f"{li['amount']:.2f}", "calculation_strategy": "manual"}}}
                                         for k, li in enumerate(c["line_items"])], "project_id": P, "company_id": C, "created_at": _ts(c["created"])})
    rfis.append({"id": 81999999, "number": "900", "full_number": "900", "subject": "Unrelated sandbox seed RFI (no marker)",
                 "status": "open", "questions": [{"id": 1, "body": "Seed data question."}], "private": False})
    pages = {"page": "1", "per_page": "100"}
    routes = [
        _route("GET", "/rest/v1.0/companies", _validated("/rest/v1.0/companies", "get",
               [{"id": C, "name": "Calc-Graph Sandbox Co (synthetic)", "is_active": True, "my_company": True}])),
        _route("GET", "/rest/v1.1/projects", _validated("/rest/v1.1/projects", "get",
               [{"id": P, "name": "Harbor View Office (sandbox)", "active": True, "project_number": "HVO-SBX"}]), query=pages),
        _route("GET", f"/rest/v1.1/projects/{P}/submittals",
               _validated("/rest/v1.1/projects/{project_id}/submittals", "get", subs), query=pages),
        _route("GET", f"/rest/v1.0/projects/{P}/rfis", _validated("/rest/v1.0/projects/{project_id}/rfis", "get", rfis), query=pages),
        _route("GET", "/rest/v1.1/change_events", _validated("/rest/v1.1/change_events", "get", ces), query={**pages, "project_id": str(P)}),
        _route("GET", "/rest/v1.0/change_order_packages", _validated("/rest/v1.0/change_order_packages", "get", [
            {"id": 66001, "number": "001", "title": "PCCO #001 RTU-2 roof framing", "status": "approved", "grand_total": "4190.40",
             "origin_id": "calc-graph:CO-001", "executed": True, "revision": 0, "created_at": _ts("2026-08-20")}] if seeded else []),
               query={**pages, "project_id": str(P)}),
        _route("GET", "/rest/v1.0/commitments", _validated("/rest/v1.0/commitments", "get", [
            {"id": 44001, "number": "SC-05", "title": "Structural steel - Keelson Steel Fabricators (fictional)", "status": "Approved",
             "executed": True, "private": False, "vendor": {"id": 900101, "name": "Keelson Steel Fabricators (fictional)"}}]),
               query={**pages, "project_id": str(P)}),
        _route("GET", "/rest/v1.0/tasks", _validated("/rest/v1.0/tasks", "get", [
            {"id": 55001, "name": "Erect steel L3 Seq 1", "percentage": 40, "critical_path": True, "milestone": False,
             "start_datetime": "2026-11-09T07:00:00Z", "finish_datetime": "2026-11-20T15:00:00Z",
             "notes": "[calc-graph ERECT-L3-S1]", "wbs": "05.3.1"},
            {"id": 55002, "name": "Topping-out milestone", "percentage": 0, "critical_path": True, "milestone": True,
             "start_datetime": "2027-01-15T07:00:00Z", "finish_datetime": "2027-01-15T07:00:00Z"}]),
               query={**pages, "project_id": str(P)}),
        _route("GET", f"/rest/v1.1/projects/{P}/drawing_areas", _validated("/rest/v1.1/projects/{project_id}/drawing_areas", "get", [
            {"id": AREA, "name": "Structural", "drawings_count": 2}]), query=pages),
        _route("GET", f"/rest/v1.1/drawing_areas/{AREA}/drawings", _validated("/rest/v1.1/drawing_areas/{drawing_area_id}/drawings", "get", [
            {"id": 77101, "number": "S-201", "title": "Level 2 framing plan", "discipline": "Structural", "obsolete": False,
             "current_revision": {"id": 1, "revision_number": "2", "updated_at": "2026-10-01T12:00:00Z"}},
            {"id": 77102, "number": "S-501", "title": "Foundation details", "discipline": "Structural", "obsolete": False,
             "current_revision": {"id": 2, "revision_number": "1", "updated_at": "2026-07-17T12:00:00Z"}}]), query=pages),
        _route("GET", "/rest/v1.0/cost_codes", _validated("/rest/v1.0/cost_codes", "get", [
            {"id": 88001, "code": "05 12 00", "full_code": "05-12-00", "name": "Structural Steel Framing"}]),
               query={**pages, "project_id": str(P)}),
        _route("GET", f"/rest/v1.0/projects/{P}/rfis/potential_rfi_managers",
               _validated("/rest/v1.0/projects/{project_id}/rfis/potential_rfi_managers", "get", [user])),
        _route("GET", "/rest/v1.0/specification_sections", _validated("/rest/v1.0/specification_sections", "get", [
            {"id": _int_id("spec", sec, base=12000, span=999), "number": sec, "description": t}
            for sec, t in sorted({(s["spec_section"], s["spec_title"]) for s in state.submittals})])),
        _route("GET", f"/rest/v1.0/companies/{C}/submittal_statuses",
               _validated("/rest/v1.0/companies/{company_id}/submittal_statuses", "get", [
                   {"id": 183100, "name": "Draft", "status": "Draft", "is_default": True},
                   {"id": 183101, "name": "Open", "status": "Open", "is_default": True},
                   {"id": 183102, "name": "Approved", "status": "Closed", "is_default": False}]), query=pages),
        _route("GET", f"/rest/v2.0/companies/{C}/change_events/statuses",
               _validated("/rest/v2.0/companies/{company_id}/change_events/statuses", "get",
                          {"data": [{"id": "301", "name": "Open", "default": True, "default_status": True, "deletable": False}]})),
        _route("POST", f"/rest/v1.0/projects/{P}/rfis", _validated("/rest/v1.0/projects/{project_id}/rfis", "post",
               {"id": 81500001, "subject": "created", "status": "open", "number": "1"}), status=201),
        _route("POST", f"/rest/v1.1/projects/{P}/submittals", _validated("/rest/v1.1/projects/{project_id}/submittals", "post",
               {"id": 61500001, "title": "created", "number": "001"}), status=201),
        _route("POST", "/rest/v1.1/change_events", _validated("/rest/v1.1/change_events", "post",
               {"id": 91500001, "title": "created", "number": "001"}), status=201),
    ]
    cfg = {"env": "sandbox", "company_id": C, "project_id": P}
    return {"_note": "SYNTHETIC recording shaped by the Procore OAS (generated/procore_client.openapi.json); not real data",
            "config": cfg, "routes": routes}


# ============================================================================== ACC
ACC_HUB = "b." + _uuid("rec-acc-hub")
ACC_PID = _uuid("rec-acc-project")


def acc(state, seeded: bool) -> dict:
    base_r = f"/construction/rfis/v3/projects/{ACC_PID}"
    base_s = f"/construction/submittals/v2/projects/{ACC_PID}"
    base_c = f"/cost/v1/containers/{ACC_PID}"
    rfis, subs, pcos = [], [], []
    if seeded:
        for r in state.rfis:
            rfis.append({"id": _uuid("rec-acc-rfi", r["ref"]), "customIdentifier": r["number"][4:], "title": r["subject"],
                         "question": f"{r['question']}\n\n{_mk(state, r['ref'], r['element_ids'])}",
                         "status": {"draft": "draft", "closed": "closed", "answered": "answered"}.get(r["status"], "open"),
                         "workflowType": "US", "reference": links.short(r["ref"]), "createdAt": _ts(r["dates"].get("created")),
                         "officialResponse": r.get("answer") if r["status"] in ("answered", "closed") else None})
        for s in state.submittals:
            subs.append({"id": _uuid("rec-acc-sub", s["ref"]), "identifier": int(s["number"].split("-")[-1]),
                         "customIdentifier": s["number"], "title": s["title"],
                         "description": f"target status: {s['status']}\n{_mk(state, s['ref'], s['element_ids'])}",
                         "specIdentifier": s["spec_section"].replace(" ", ""), "specTitle": s["spec_title"],
                         "stateId": {"draft": "draft", "submitted": "mgr-1"}.get(s["status"], "mgr-2"),
                         "statusId": {"draft": 6, "submitted": 2}.get(s["status"], 3), "revision": s.get("revision") or 0,
                         "dueDate": s["dates"].get("due")})
        for c in state.change_events:
            pcos.append({"id": _uuid("rec-acc-pco", c["ref"]), "number": c["number"], "name": c["title"],
                         "description": f"{c['description']}\n{_mk(state, c['ref'], c['element_ids'])}", "scope": "tbd",
                         "budgetStatus": "open", "costStatus": "pricing", "estimated": c["amount"],
                         "externalId": f"calc-graph:{c['ref']}", "externalSystem": "calc-graph"})
    subs.append({"id": _uuid("rec-acc-sub-void"), "title": "voided seed item", "statusId": 4, "stateId": "void"})
    pages = {"limit": "50", "offset": "0"}
    page = lambda rows, limit: {"results": rows, "pagination": {"limit": limit, "offset": 0, "totalResults": len(rows)}}  # noqa: E731
    dm_project = {"jsonapi": {"version": "1.0"}, "links": {"self": {"href": "https://developer.api.autodesk.com/project/v1/hubs/x/projects/y"}},
                  "data": {"type": "projects", "id": "b." + ACC_PID, "attributes": {"name": "Harbor View Office (ACC trial)"},
                           "links": {"self": {"href": "https://developer.api.autodesk.com/project/v1/hubs/x/projects/y"},
                                     "webView": {"href": "https://acc.autodesk.com/build/projects/example"}}}}
    issues = [{"id": _uuid("rec-acc-issue", "1"), "displayId": 1, "title": "Field: bolt holes misaligned at CX-L2-3B-N",
               "description": "Found during erection.\n[calc-graph ISSUE-001 el=CX-L2-3B-N]", "status": "open",
               "createdAt": "2026-11-10T14:00:00.000Z"}] if seeded else []
    routes = [
        _route("GET", f"/project/v1/hubs/{ACC_HUB}/projects/b.{ACC_PID}", dm_project),
        _route("POST", f"{base_r}/search:rfis", page(rfis, 200)),
        _route("GET", f"{base_s}/items", page(subs, 50), query=pages),
        _route("GET", f"{base_s}/specs", page([{"id": _uuid("rec-acc-spec", sec), "identifier": sec.replace(" ", ""), "title": t}
                                               for sec, t in sorted({(s["spec_section"], s["spec_title"]) for s in state.submittals})], 50),
               query=pages),
        _route("GET", f"{base_s}/item-types", page([{"id": _uuid("rec-acc-type", "shop"), "value": "Shop Drawings"}], 50), query=pages),
        _route("GET", f"{base_c}/change-orders/pco", page(pcos, 100), query={"limit": "100", "offset": "0"}),
        _route("GET", f"{base_c}/change-orders/oco", page([{"id": _uuid("rec-acc-oco", "1"), "number": "1", "name": "OCO-001 RTU-2",
                                                            "budgetStatus": "approved", "approved": 4190.4,
                                                            "externalId": "calc-graph:CO-001"}] if seeded else [], 100),
               query={"limit": "100", "offset": "0"}),
        _route("GET", f"{base_c}/budgets", page([{"id": _uuid("rec-acc-budget", "05"), "code": "05 12 00", "name": "Structural steel",
                                                  "quantity": 212.0, "unit": "ton", "unitPrice": 4800, "originalAmount": 1017600.0,
                                                  "revised": 1021790.4}], 100), query={"limit": "100", "offset": "0"}),
        _route("GET", f"/construction/sheets/v1/projects/{ACC_PID}/sheets", page([
            {"id": _uuid("rec-acc-sheet", "S-201"), "number": "S-201", "title": "Level 2 framing plan", "isCurrent": True,
             "versionSet": {"id": _uuid("vs1"), "name": "IFC set", "issuanceDate": "2026-06-01"}}], 100),
               query={"limit": "100", "offset": "0"}),
        _route("GET", f"/construction/issues/v1/projects/{ACC_PID}/issues", page(issues, 100), query={"limit": "100", "offset": "0"}),
        _route("POST", f"{base_r}/rfis", {"id": _uuid("rec-acc-rfi-new"), "title": "created", "status": "draft"}, status=201),
        _route("POST", f"{base_s}/items", {"id": _uuid("rec-acc-sub-new"), "title": "created", "stateId": "draft"}, status=201),
        _route("POST", f"{base_c}/change-orders/pco", {"id": _uuid("rec-acc-pco-new"), "name": "created"}, status=201),
    ]
    return {"_note": "SYNTHETIC recording; DM/Issues shaped by aps-sdk-openapi specs, RFIs/Submittals/Cost/Sheets by the APS reference pages",
            "config": {"hub_id": ACC_HUB, "project_id": "b." + ACC_PID}, "routes": routes}


# ============================================================================== Forma
def forma(state) -> dict:
    auth = "pro_recsynthetic1"
    prop_urn = f"urn:adsk-forma-elements:proposal:{auth}:p1:1731500000000"
    els = {}
    kids = []
    for eid in ("COL-2B", "COL-3B", "G-L2-B-23"):
        if eid not in state.elements:
            continue
        urn = f"urn:adsk-forma-elements:integrate:{auth}:{_uuid('rec-forma', eid)[:12]}:1"
        els[urn] = {"urn": urn, "properties": {"category": "generic", "name": eid},
                    "representations": {"volumeMesh": {"type": "linked", "blobId": _uuid("rec-blob", eid)}}, "children": []}
        kids.append({"urn": urn, "key": eid, "transform": [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1], "name": eid})
    other = f"urn:adsk-forma-elements:terrain:{auth}:t1:1"
    els[other] = {"urn": other, "properties": {"category": "terrain", "name": "Terrain"}, "representations": {}, "children": []}
    proposal = {"urn": prop_urn, "metadata": {"createdAt": "2026-10-03T13:37:00.000Z"},
                "properties": {"category": "proposal", "name": "Scheme B (structural grid v2)"},
                "children": kids + [{"urn": other, "key": "terrain", "transform": [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]}]}
    els[prop_urn] = copy.deepcopy(proposal)
    routes = [
        _route("GET", "/forma/proposal/v1alpha/proposals", {"results": [proposal], "pagination": {"limit": 100}},
               query={"authcontext": auth}),
        _route("GET", f"/forma/element-service/v1alpha/elements/{prop_urn}", {"element": els[prop_urn], "elements": els},
               query={"authcontext": auth, "recursive": "true"}),
    ]
    return {"_note": "SYNTHETIC recording shaped by the Forma proposal-listproposals-GET / element-getelement-GET reference pages",
            "config": {"forma_project_id": auth}, "routes": routes}


def main() -> int:
    state = get_state(load_design())
    os.makedirs(OUT, exist_ok=True)
    files = {"procore_sandbox.json": procore(state, True), "procore_sandbox_empty.json": procore(state, False),
             "acc_trial.json": acc(state, True), "acc_trial_empty.json": acc(state, False), "forma.json": forma(state)}
    for name, data in files.items():
        with open(os.path.join(OUT, name), "w") as fh:
            json.dump(data, fh, indent=1, sort_keys=True)
    print(json.dumps({n: len(d["routes"]) for n, d in files.items()}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
