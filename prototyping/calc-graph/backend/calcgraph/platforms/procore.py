"""Procore adapter (SYNTHETIC): the construction state shaped like Procore REST API objects.

Every raw object is built THROUGH typed models generated from Procore's own OpenAPI document
(scripts/gen_platform_models.py -> generated/procore_subset.openapi.json -> generated/procore_rest,
openapi-python-client 0.29.1) and checked field-by-field against that schema by `_spec.shaped`:
field names, JSON types, enums and date formats are the spec's, not recollection.

Source: https://developers.procore.com/api/v1/resource_groups/full_oas?version=1 (Procore "download
OAS", x-created-at 2026-11-13T21:00:38Z, fetched 2026-11-14; see data/SOURCES.md). Objects used:

  submittals           GET /rest/v1.1/projects/{project_id}/submittals/{id}      -> ProcoreSubmittal
  rfis                 GET /rest/v1.0/projects/{project_id}/rfis/{id}            -> ProcoreRfi
  change_events        GET /rest/v1.1/change_events/{id}                         -> ProcoreChangeEvent
  change_orders        GET /rest/v1.0/change_order_packages/{id}                 -> ProcoreChangeOrderPackage
  budget_lines         GET /rest/v1.1/budget_line_items/{id}                     -> ProcoreBudgetLineItem
  cost_codes           GET /rest/v1.0/cost_codes/{id}                            -> ProcoreCostCode
  schedule_activities  GET /rest/v1.0/tasks/{id}                                 -> ProcoreTask
  sheets               GET /rest/v1.1/drawing_areas/{drawing_area_id}/drawings   -> ProcoreDrawing

What the spec does NOT carry, and where it went instead (never invented on the raw object):
- fabricated / delivered / erected stage of a submittal: a project custom field
  (custom_field_<id>, lov_entry) as a GC would configure it, plus the spec's delivery dates;
- registry element ids: a project custom field (string) on submittals and RFIs;
- schedule logic (predecessors) and total float: not in the task object; they stay in the
  NormalizedRecord fields only;
- change-order amounts by our change events: change_order_packages carry grand_total / status
  (draft | pending | approved | ...); the spec's PCO object has no "approved" status, so approved
  prime changes are emitted as change order packages.

Every id is deterministic; every deep link is mock://procore/... (never a real tenant).
"""
from __future__ import annotations

from . import _norm
from ._spec import shaped
from .base import (BUDGET_LINES, CHANGE_EVENTS, CHANGE_ORDERS, COST_CODES, RFIS, SCHEDULE_ACTIVITIES, SHEETS,
                   SUBMITTALS, NormalizedRecord, PlatformAdapter)
from .synthetic import ConstructionState, _int_id

COMPANY_ID = 4100217
PROJECT_ID = 2060301
OAS_URL = "https://developers.procore.com/api/v1/resource_groups/full_oas?version=1"
CF_FAB_STATUS, CF_ELEMENT_IDS = 600101, 600102   # custom field definition ids (project-configured)
DOMAINS = {"gc": "tidewater.example", "steel": "keelson.example", "eor": "northpoint.example",
           "architect": "fernwood.example", "concrete": "bedrock.example", "deck": "ridgeline.example"}
PERSON_CO = {"gc_pm": "gc", "gc_super": "gc", "steel_pm": "steel", "eor": "eor", "architect": "architect",
             "concrete_pm": "concrete", "deck_pm": "deck", "owner_rep": "gc"}
PATH = {SUBMITTALS: "submittals", RFIS: "rfis", CHANGE_EVENTS: "change_events", CHANGE_ORDERS: "change_order_packages",
        BUDGET_LINES: "budget_line_items", COST_CODES: "cost_codes", SCHEDULE_ACTIVITIES: "schedule/tasks",
        SHEETS: "drawings"}


def _ts(date: str | None, hour: int = 15) -> str | None:
    return f"{date}T{hour:02d}:00:00Z" if date else None


class ProcoreAdapter(PlatformAdapter):
    name = "procore"
    label = "Procore (synthetic)"
    capabilities = frozenset({SUBMITTALS, RFIS, CHANGE_EVENTS, CHANGE_ORDERS, BUDGET_LINES, COST_CODES,
                              SCHEDULE_ACTIVITIES, SHEETS})
    doc_urls = {rt: f"{OAS_URL} :: {op}" for rt, op in {
        SUBMITTALS: "GET /rest/v1.1/projects/{project_id}/submittals/{id}",
        RFIS: "GET /rest/v1.0/projects/{project_id}/rfis/{id}",
        CHANGE_EVENTS: "GET /rest/v1.1/change_events/{id}",
        CHANGE_ORDERS: "GET /rest/v1.0/change_order_packages/{id}",
        BUDGET_LINES: "GET /rest/v1.1/budget_line_items/{id}",
        COST_CODES: "GET /rest/v1.0/cost_codes/{id}",
        SCHEDULE_ACTIVITIES: "GET /rest/v1.0/tasks/{id}",
        SHEETS: "GET /rest/v1.1/drawing_areas/{drawing_area_id}/drawings",
    }.items()}

    def __init__(self, state: ConstructionState):
        super().__init__()
        self.state = state
        self.project_id = PROJECT_ID

    def deep_link(self, record_type: str, id: str) -> str:
        return f"mock://procore/projects/{self.project_id}/{PATH.get(record_type, record_type)}/{id}"

    # ------------------------------------------------------------------ people
    def _user(self, key_or_name: str) -> dict:
        people = self.state.project["people"]
        key = key_or_name if key_or_name in people else next((k for k, v in people.items() if v == key_or_name), None)
        name = people.get(key, key_or_name)
        dom = DOMAINS.get(PERSON_CO.get(key, "gc"), "tidewater.example")
        return {"id": _int_id("procore-user", name, base=7000000, span=999999), "login": f"{name.lower().replace(' ', '.')}@{dom}",
                "name": name}

    def _vendor(self, company: str) -> dict:
        return {"id": _int_id("procore-vendor", company, base=900000, span=99999), "name": company}

    # ------------------------------------------------------------------ build
    def _build(self) -> dict[str, list[NormalizedRecord]]:
        st = self.state
        out: dict[str, list[NormalizedRecord]] = {k: [] for k in self.capabilities}
        spec_ids = {}
        packages = {"03": ("Foundations", 1), "05 12": ("Structural steel", 2), "05 31": ("Steel deck", 3), "07": ("Fireproofing", 4)}
        sub_company = {"Keelson": "steel_pm", "Bedrock": "concrete_pm", "Ridgeline": "deck_pm"}
        stage_lov = {s: i for i, s in enumerate(("design", "submitted", "approved", "fabricated", "delivered", "erected"), 1)}

        def pkg_for(spec: str):
            for k, (t, n) in packages.items():
                if spec.startswith(k):
                    return {"id": _int_id("procore-pkg", k, base=31000, span=9999), "number": str(n), "title": t}
            return None

        def ids_cf(ids):
            return {"data_type": "string", "value": ",".join(ids[:50]) + ("..." if len(ids) > 50 else "")}

        for s in st.submittals:
            sid = _int_id("procore-sub", s["ref"], base=60000000, span=9999999)
            spec_ids.setdefault(s["spec_section"], _int_id("procore-spec", s["spec_section"], base=12000, span=9999))
            seq = s["number"].split("-")[-1]
            status_word = {"draft": "Draft", "submitted": "Open"}.get(s["status"], "Closed")
            d = s["dates"]
            sub_user = self._user(sub_company.get(s["responsible_contractor"].split()[0], "gc_pm"))
            approver = {
                "id": sid * 10 + 1, "approver_type": "Approver", "workflow_group_number": 1,
                "distributed": s["status"] not in ("draft", "submitted"), "response_required": True,
                "days_to_respond": 10, "sent_date": d["submitted"], "due_date": d["due"], "returned_date": d["returned"],
                "response": ({"id": {"Approved": 1, "Approved as Noted": 2}.get(s["response"], 3), "name": s["response"],
                              "considered": "approved"} if s["response"] else {"id": 0, "name": "Pending", "considered": "pending"}),
                "user": self._user("eor"), "comment": None, "attachments": []}
            raw = {
                "id": sid, "number": seq, "formatted_number": f"{s['spec_section']}-{seq}", "revision": str(s["revision"]),
                "title": s["title"], "description": f"{s['title']}. Elements: {len(s['element_ids'])}.",
                "current_revision": True, "private": False, "for_record_only": False,
                "status": {"id": {"Draft": 1, "Open": 2, "Closed": 3}[status_word], "name": status_word, "status": status_word},
                "type": {"id": 1 if "shop" in s["package_kind"] else 2,
                         "name": "Shop Drawing" if "shop" in s["package_kind"] or s["package_kind"] in ("anchor_rods", "connection_design") else "Product Data"},
                "specification_section": {"id": spec_ids[s["spec_section"]], "number": s["spec_section"],
                                          "description": s["spec_title"], "label": f"{s['spec_section']} - {s['spec_title']}"},
                "submittal_manager": self._user(s["submittal_manager"]),
                "created_by": self._user("gc_pm"),
                "received_from": sub_user,
                "responsible_contractor": self._vendor(s["responsible_contractor"]),
                "submittal_package": pkg_for(s["spec_section"]),
                "ball_in_court": [self._user("eor")] if s["status"] == "submitted" else ([sub_user] if s["status"] == "draft" else []),
                "approvers": [approver],
                "due_date": d["due"], "submit_by": d["created"], "issue_date": d["created"], "received_date": d["submitted"],
                "closed_at": _ts(d["returned"]) if status_word == "Closed" else None,
                "distributed_at": _ts(d["returned"], 17) if status_word == "Closed" else None,
                "confirmed_delivery_date": d.get("anticipated_delivery"),
                "actual_delivery_date": d.get("actual_delivery"),
                "required_on_site_date": d.get("required_on_job"),
                "lead_time": 15 if s.get("level") else None,
                "location": {"id": _int_id("procore-loc", s["level"] or "site", base=5000, span=999),
                             "name": {"L2": "Level 2", "L3": "Level 3", "RF": "Roof"}.get(s["level"], "Building")},
                "scheduled_task": {"id": _int_id("procore-task", s["activity_refs"][-1]), "key": s["activity_refs"][-1],
                                   "name": next(a["name"] for a in st.activities if a["ref"] == s["activity_refs"][-1])},
                "custom_fields": {
                    f"custom_field_{CF_FAB_STATUS}": {"data_type": "lov_entry",
                                                      "value": {"id": stage_lov[s["stage"]], "label": s["stage"].capitalize()}},
                    f"custom_field_{CF_ELEMENT_IDS}": ids_cf(s["element_ids"]),
                },
                "attachments": [], "attachments_count": 2 if s["status"] != "draft" else 0,
                "created_at": _ts(d["created"], 13), "updated_at": _ts(d["returned"] or d["submitted"] or d["created"], 18),
            }
            raw = shaped("procore", "ProcoreSubmittal", raw)
            out[SUBMITTALS].append(_norm.submittal(s, self.name, sid, raw["formatted_number"],
                                                   self.deep_link(SUBMITTALS, sid), raw))

        for r in st.rfis:
            rid = _int_id("procore-rfi", r["ref"], base=21000000, span=999999)
            n = int(r["number"].split("-")[1])
            d = r["dates"]
            pstatus = {"draft": "draft", "open": "open", "answered": "open", "closed": "closed"}[r["status"]]
            assignee = self._user(r["assignee"])
            answers = ([{"id": rid * 10 + 1, "official": True, "answer_date": _ts(d["answered"]),
                         "plain_text_body": r["answer"], "rich_text_body": f"<p>{r['answer']}</p>",
                         "created_by": assignee["name"], "created_by_id": assignee["id"], "attachments": []}]
                       if r["answer"] else [])
            impact = {"yes": "yes_unknown", "no": "no_impact", "tbd": "tbd"}
            bic = {"Assignees": assignee, "Creator": self._user(r["received_from"])}.get(r["ball_in_court"], self._user(r["rfi_manager"]))
            raw = {
                "id": rid, "number": str(n), "full_number": f"RFI-{n:03d}", "prefix": "RFI", "revision": "0",
                "subject": r["subject"], "reference": r["drawing_number"], "drawing_number": r["drawing_number"],
                "drawing_ids": [], "status": pstatus, "translated_status": pstatus.capitalize(),
                "accepted": r["status"] == "closed", "draft": r["status"] == "draft", "private": False, "deleted": False,
                "ball_in_court_role": r["ball_in_court"], "current_revision": True, "has_revisions": False,
                "created_at": _ts(d["created"], 14), "initiated_at": _ts(d["created"], 14), "due_date": d["due"],
                "time_resolved": _ts(d["closed"]) if d["closed"] else None, "updated_at": _ts(d["answered"] or d["created"], 16),
                "created_by": {**self._user(r["received_from"]), "locale": "en"},
                "assignee": assignee, "assignees": [assignee],
                "received_from": self._user(r["received_from"]), "rfi_manager": self._user(r["rfi_manager"]),
                "ball_in_court": bic, "ball_in_courts": [bic] if r["status"] in ("draft", "open") else [],
                "distribution_list": [self._user("gc_super"), self._user("architect")],
                "questions": [{"id": rid * 10, "question_date": _ts(d["created"], 14), "plain_text_body": r["question"],
                               "rich_text_body": f"<p>{r['question']}</p>", "created_by": self._user(r["received_from"])["name"],
                               "attachments": [], "answers": answers}],
                "cost_impact": {"status": impact[r["cost_impact"]], "value": None},
                "schedule_impact": {"status": impact[r["schedule_impact"]], "value": None},
                "location": None, "cost_code": None, "responsible_contractor": None,
                "specification_section": {"id": _int_id("procore-spec", r["spec_section"], base=12000, span=9999),
                                          "number": r["spec_section"], "description": ""},
                "custom_fields": {f"custom_field_{CF_ELEMENT_IDS}": ids_cf(r["element_ids"])},
            }
            raw = shaped("procore", "ProcoreRfi", raw)
            out[RFIS].append(_norm.rfi(r, self.name, rid, raw["full_number"], self.deep_link(RFIS, rid), raw))

        cc_ids = {c["code"]: _int_id("procore-cc", c["code"], base=8800000, span=99999) for c in st.cost_codes}
        cc_name = {c["code"]: c["name"] for c in st.cost_codes}
        for c in st.change_events:
            cid = _int_id("procore-ce", c["ref"], base=3300000, span=99999)
            sname = {"approved": "Closed", "pending": "Pending", "draft": "Open"}[c["status"]]
            raw = {
                "id": cid, "number": c["number"], "title": c["title"], "description": c["description"],
                "scope": "out_of_scope", "project_id": self.project_id, "company_id": COMPANY_ID,
                "status": {"id": {"Open": 1, "Pending": 2, "Closed": 3}[sname], "name": sname, "mapped_to_status": sname.lower()},
                "change_type": {"id": 1, "name": "Change Event", "abbreviation": "CE"},
                "change_reason": {"id": _int_id("procore-reason", c["reason"], base=100, span=899), "change_reason": c["reason"]},
                "source": "budget_change", "comments_enabled": True, "deletable": False, "in_recycle_bin": False,
                "currency_configuration": {"currency_iso_code": "USD"},
                "created_by": self._user("gc_pm"), "created_at": _ts(c["created"], 13), "updated_at": _ts(c["created"], 16),
                "change_items": [{
                    "id": cid * 10 + i, "description": li["description"], "item_type": "line_item", "source": "change_event",
                    "event_id": cid, "event_number": c["number"], "event_title": c["title"], "deletable": False, "editable": True,
                    "budget_code": {"id": cc_ids[li["cost_code"]], "flat_code": f"{li['cost_code']}.S",
                                    "description": cc_name[li["cost_code"]]},
                    "latest_revenue_values": {"amount": f"{li['amount']:.2f}", "calculation_strategy": "manual"},
                    "latest_cost_values": {"amount": f"{li['amount'] * 0.9:.2f}", "calculation_strategy": "manual"},
                } for i, li in enumerate(c["line_items"])],
                "attachments": [], "markup_items": [], "production_quantities": [],
            }
            raw = shaped("procore", "ProcoreChangeEvent", raw)
            out[CHANGE_EVENTS].append(_norm.change_event(c, self.name, cid, f"CE-{c['number']}", self.deep_link(CHANGE_EVENTS, cid), raw))
        for c in st.change_orders:
            cid = _int_id("procore-pco", c["ref"], base=4400000, span=99999)
            ce = next(e for e in st.change_events if e["ref"] == c["change_event_ref"])
            raw = {
                "id": cid, "number": c["number"], "title": c["title"], "revision": 0, "private": False,
                "status": {"approved": "approved", "pending": "pending", "draft": "draft"}[c["status"]],
                "type": "PrimeContractChangeOrder", "executed": c["status"] == "approved",
                "grand_total": f"{c['amount']:.2f}", "schedule_impact_amount": c["schedule_days"],
                "description": f"{ce['description']} (from change event CE-{ce['number']})",
                "contract_id": _int_id("procore-prime", "prime"),
                "creator": self._user("gc_pm"), "designated_reviewer": self._user("owner_rep"),
                "created_at": _ts(c["created"], 13), "updated_at": _ts(c["approved"] or c["created"], 16),
                "attachments": [],
            }
            if c["approved"]:
                raw["reviewed_at"] = _ts(c["approved"])
                raw["reviewer"] = self._user("owner_rep")
            raw = shaped("procore", "ProcoreChangeOrderPackage", raw)
            out[CHANGE_ORDERS].append(_norm.change_order(c, self.name, cid, f"CO-{c['number']}", self.deep_link(CHANGE_ORDERS, cid), raw))

        for i, c in enumerate(st.cost_codes):
            cid = cc_ids[c["code"]]
            raw = {"id": cid, "name": c["name"], "full_code": c["code"], "code": c["code"].split()[-1],
                   "parent": {"id": _int_id("procore-div", c["division"], base=8700000, span=99999)},
                   "sortable_code": c["code"].replace(" ", "."), "position": i, "budgeted": True,
                   "biller": st.project["name"], "biller_id": self.project_id, "biller_type": "Project",
                   "created_at": _ts(st.project["start"], 12), "updated_at": _ts(st.project["start"], 12)}
            raw = shaped("procore", "ProcoreCostCode", raw)
            out[COST_CODES].append(_norm.cost_code(c, self.name, cid, self.deep_link(COST_CODES, cid), raw))
        for b in st.budget_lines:
            bid = _int_id("procore-bli", b["ref"], base=9900000, span=99999)
            raw = {"id": bid,
                   "wbs_code": {"id": cc_ids[b["cost_code"]], "flat_code": f"{b['cost_code']}.S", "description": cc_name[b["cost_code"]]},
                   "quantity": float(b["quantity"]), "uom": b["unit"], "unit_cost": float(b["unit_cost"]),
                   "calculation_strategy": "automatic", "original_budget_amount": float(b["amount"]),
                   "currency_configuration": {"currency_iso_code": "USD"}}
            raw = shaped("procore", "ProcoreBudgetLineItem", raw)
            out[BUDGET_LINES].append(_norm.budget_line(b, self.name, bid, self.deep_link(BUDGET_LINES, bid), raw))

        for i, a in enumerate(st.activities):
            tid = _int_id("procore-task", a["ref"])
            raw = {"id": tid, "key": a["ref"], "activity_id": f"A{1000 + 10 * i}", "schedule_activity_id": a["ref"],
                   "name": a["name"], "task_name": a["name"], "wbs": a["wbs"].split()[0],
                   "full_outline_path": f"{a['wbs']} > {a['name']}",
                   "start_datetime": _ts(a["actual_start"] or a["early_start"], 7),
                   "finish_datetime": _ts(a["actual_finish"] or a["early_finish"], 17),
                   "baseline_start": _ts(a["early_start"], 7), "baseline_finish": _ts(a["early_finish"], 17),
                   "start_variance": 0.0, "finish_variance": 0.0,
                   "percentage": int(round(a["percent_complete"])), "milestone": a["milestone"],
                   "critical_path": a["critical"], "schedule_duration": float(a["duration"]),
                   "row_number": i + 1, "has_children": False, "pending": False, "manually_edited": False}
            if a["actual_start"]:
                raw["actual_start"] = _ts(a["actual_start"], 7)
            if a["actual_finish"]:
                raw["actual_finish"] = _ts(a["actual_finish"], 17)
            raw = shaped("procore", "ProcoreTask", raw)
            out[SCHEDULE_ACTIVITIES].append(_norm.activity(a, self.name, tid, raw["activity_id"],
                                                           self.deep_link(SCHEDULE_ACTIVITIES, tid), raw))
        for s in st.sheets:
            did = _int_id("procore-dwg", s["ref"], base=50000000, span=999999)
            raw = {"id": did, "number": s["number"], "drawing_number": s["number"], "title": s["title"],
                   "discipline": s["discipline"], "drawing_discipline_id": 3, "obsolete": False, "sheet_number": None,
                   "current_revision": {"id": did * 10 + int(s["revision"]), "revision_number": s["revision"],
                                        "floorplan": False, "has_drawing_sketches": False,
                                        "pdf_url": self.deep_link(SHEETS, did) + "/pdf",
                                        "updated_at": _ts(s["issued"], 12)}}
            raw = shaped("procore", "ProcoreDrawing", raw)
            out[SHEETS].append(_norm.sheet(s, self.name, did, self.deep_link(SHEETS, did), raw))
        return out
