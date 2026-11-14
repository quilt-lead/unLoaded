"""Procore adapter (SYNTHETIC): the construction state shaped like Procore REST API objects.

Shapes follow Procore's public REST API reference. developers.procore.com renders client-side
and could not be fetched directly, so field names were read from mirrors of Procore's OpenAPI
spec (withone.ai knowledge pages) where noted, and are otherwise from recollection of the
public reference - treat the latter as approximate:

- Submittals (v1.1 list/show)  - READ from mirror:
  https://developers.procore.com/reference/rest/submittals
  mirror: https://www.withone.ai/knowledge/procore/conn_mod_def%3A%3AGLdZZE5Su5g%3A%3Ak81UFdGDRC-0HR1NYpzaWw
  (id, number, formatted_number, revision, title, status{}, type{}, specification_section{},
  submittal_manager{}, received_from{}, responsible_contractor{}, submittal_package{},
  ball_in_court[], approvers[{approver_type, response{name}, sent_date, due_date,
  returned_date, user{}}], due_date, submit_by, issue_date, received_date, closed_at,
  distributed_at, location{}, scheduled_task{}, custom_fields). status.status vocabulary
  Draft / Open / Closed and the approver responses (Approved, Approved as Noted, Revise and
  Resubmit, Rejected) are recollection. Procore has no native fabricated / delivered /
  erected submittal status: that is carried in `custom_fields` (as a GC would configure it)
  plus the delivery dates.
- RFIs (v1.0)  - READ from mirror:
  https://developers.procore.com/reference/rest/rfis
  mirror: https://www.withone.ai/knowledge/procore/conn_mod_def%3A%3AGLdZPkS8Iag%3A%3AJljsnXEbTqG8cDU3DM8GoA
  (status: open | closed | draft | recycled; questions[].plain_text_body; answers[].official;
  ball_in_court_role: Assignees | Creator | RFI Manager). cost_impact / schedule_impact
  {status, value} sub-fields are recollection.
- Change events (v1.1)  - READ from mirror:
  https://developers.procore.com/reference/rest/change-events
  mirror: https://www.withone.ai/knowledge/procore/conn_mod_def%3A%3AGLdXn61pdjg%3A%3AeNq2SxSdQN6_BLnlJT7OmA
  (status{id, name, mapped_to_status}: Open / Pending / Closed; change_type{}, change_reason{},
  event_origin{}, change_items[]).
- Potential change orders (prime contract PCOs): field list is recollection; status values
  use the documented prime_pco_status filter vocabulary (draft, pending, approved, ...).
- Budget line items (v1.0/v1.1), cost codes, schedule tasks, drawings: recollection of the
  public reference (budget_line_items: original_budget_amount, unit_of_measure, quantity,
  unit_cost, wbs_code{id, flat_code}); NOT verified against the live docs.

Every id is deterministic; every deep link is mock://procore/... (never a real tenant).
"""
from __future__ import annotations

from . import _norm
from .base import (BUDGET_LINES, CHANGE_EVENTS, CHANGE_ORDERS, COST_CODES, RFIS, SCHEDULE_ACTIVITIES, SHEETS,
                   SUBMITTALS, NormalizedRecord, PlatformAdapter)
from .synthetic import ConstructionState, _int_id

COMPANY_ID = 4100217
PROJECT_ID = 2060301
DOMAINS = {"gc": "tidewater.example", "steel": "keelson.example", "eor": "northpoint.example",
           "architect": "fernwood.example", "concrete": "bedrock.example", "deck": "ridgeline.example"}
PERSON_CO = {"gc_pm": "gc", "gc_super": "gc", "steel_pm": "steel", "eor": "eor", "architect": "architect",
             "concrete_pm": "concrete", "deck_pm": "deck", "owner_rep": "gc"}
PATH = {SUBMITTALS: "submittals", RFIS: "rfis", CHANGE_EVENTS: "change_events", CHANGE_ORDERS: "potential_change_orders",
        BUDGET_LINES: "budget_line_items", COST_CODES: "cost_codes", SCHEDULE_ACTIVITIES: "schedule/tasks",
        SHEETS: "drawings"}


def _ts(date: str | None, hour: int = 15) -> str | None:
    return f"{date}T{hour:02d}:00:00Z" if date else None


class ProcoreAdapter(PlatformAdapter):
    name = "procore"
    label = "Procore (synthetic)"
    capabilities = frozenset({SUBMITTALS, RFIS, CHANGE_EVENTS, CHANGE_ORDERS, BUDGET_LINES, COST_CODES,
                              SCHEDULE_ACTIVITIES, SHEETS})
    doc_urls = {
        SUBMITTALS: "https://developers.procore.com/reference/rest/submittals",
        RFIS: "https://developers.procore.com/reference/rest/rfis",
        CHANGE_EVENTS: "https://developers.procore.com/reference/rest/change-events",
        CHANGE_ORDERS: "https://developers.procore.com/reference/rest/potential-change-orders",
        BUDGET_LINES: "https://developers.procore.com/reference/rest/budget-line-items",
        COST_CODES: "https://developers.procore.com/reference/rest/cost-codes",
        SCHEDULE_ACTIVITIES: "https://developers.procore.com/reference/rest/tasks",
        SHEETS: "https://developers.procore.com/reference/rest/drawings",
    }

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

        def pkg_for(spec: str):
            for k, (t, n) in packages.items():
                if spec.startswith(k):
                    return {"id": _int_id("procore-pkg", k, base=31000, span=9999), "number": str(n), "title": t}
            return None

        for s in st.submittals:
            sid = _int_id("procore-sub", s["ref"], base=60000000, span=9999999)
            spec_ids.setdefault(s["spec_section"], _int_id("procore-spec", s["spec_section"], base=12000, span=9999))
            seq = s["number"].split("-")[-1]
            status_word = {"draft": "Draft", "submitted": "Open"}.get(s["status"], "Closed")
            d = s["dates"]
            approver = {
                "approver_type": "Approver", "distributed": s["status"] not in ("draft", "submitted"),
                "response_required": True, "days_to_respond": 10, "sent_date": d["submitted"], "due_date": d["due"],
                "returned_date": d["returned"],
                "response": ({"id": {"Approved": 1, "Approved as Noted": 2}.get(s["response"], 3), "name": s["response"],
                              "considered": "approved"} if s["response"] else {"id": 0, "name": "Pending", "considered": "pending"}),
                "user": self._user("eor"), "comment": "", "attachments": []}
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
                "received_from": self._user({"Keelson": "steel_pm", "Bedrock": "concrete_pm", "Ridgeline": "deck_pm"}
                                            .get(s["responsible_contractor"].split()[0], "gc_pm")),
                "responsible_contractor": self._vendor(s["responsible_contractor"]),
                "submittal_package": pkg_for(s["spec_section"]),
                "ball_in_court": [self._user("eor")] if s["status"] == "submitted" else
                                 ([self._user({"Keelson": "steel_pm", "Bedrock": "concrete_pm", "Ridgeline": "deck_pm"}
                                              .get(s["responsible_contractor"].split()[0], "gc_pm"))] if s["status"] == "draft" else []),
                "approvers": [approver],
                "due_date": d["due"], "submit_by": d["created"], "issue_date": d["created"], "received_date": d["submitted"],
                "closed_at": _ts(d["returned"]) if status_word == "Closed" else None,
                "distributed_at": _ts(d["returned"], 17) if status_word == "Closed" else None,
                "anticipated_delivery_date": d.get("anticipated_delivery"),
                "actual_delivery_date": d.get("actual_delivery"),
                "required_on_site_date": d.get("required_on_job"),
                "location": {"id": _int_id("procore-loc", s["level"] or "site", base=5000, span=999),
                             "name": {"L2": "Level 2", "L3": "Level 3", "RF": "Roof"}.get(s["level"], "Building")},
                "scheduled_task": {"id": _int_id("procore-task", s["activity_refs"][-1]), "name": s["activity_refs"][-1]},
                "custom_fields": {
                    "custom_field_fabrication_status": {"data_type": "lov_entry", "value": s["stage"].capitalize()},
                    "custom_field_registry_element_ids": {"data_type": "string", "value": ",".join(s["element_ids"][:50]) +
                                                          ("..." if len(s["element_ids"]) > 50 else "")},
                },
                "attachments_count": 2 if s["status"] != "draft" else 0,
                "created_at": _ts(d["created"], 13), "updated_at": _ts(d["returned"] or d["submitted"] or d["created"], 18),
            }
            out[SUBMITTALS].append(_norm.submittal(s, self.name, sid, raw["formatted_number"],
                                                   self.deep_link(SUBMITTALS, sid), raw))

        for r in st.rfis:
            rid = _int_id("procore-rfi", r["ref"], base=21000000, span=999999)
            n = int(r["number"].split("-")[1])
            d = r["dates"]
            pstatus = {"draft": "draft", "open": "open", "answered": "open", "closed": "closed"}[r["status"]]
            answers = ([{"id": rid * 10 + 1, "official": True, "answer_date": d["answered"],
                         "plain_text_body": r["answer"], "rich_text_body": f"<p>{r['answer']}</p>",
                         "created_by": self._user(r["assignee"]), "created_by_id": self._user(r["assignee"])["id"],
                         "attachments": []}] if r["answer"] else [])
            impact = lambda v: {"status": {"yes": "yes_known", "no": "no_impact", "tbd": "tbd"}[v], "value": None}  # noqa: E731
            raw = {
                "id": rid, "number": str(n), "full_number": f"RFI-{n:03d}", "prefix": "RFI", "revision": 0,
                "subject": r["subject"], "reference": r["drawing_number"], "drawing_number": r["drawing_number"],
                "drawing_ids": [], "status": pstatus, "translated_status": pstatus.capitalize(),
                "accepted": r["status"] == "closed", "draft": r["status"] == "draft", "private": False,
                "ball_in_court_role": r["ball_in_court"], "current_revision": True, "has_revisions": False,
                "created_at": _ts(d["created"], 14), "initiated_at": _ts(d["created"], 14), "due_date": d["due"],
                "time_resolved": _ts(d["closed"]) if d["closed"] else None, "updated_at": _ts(d["answered"] or d["created"], 16),
                "assignee": self._user(r["assignee"]),
                "assignees": [{**self._user(r["assignee"]), "response_required": True}],
                "received_from": self._user(r["received_from"]), "rfi_manager": self._user(r["rfi_manager"]),
                "ball_in_court": [self._user(r["assignee"])] if r["status"] == "open" else [],
                "distribution_list": [self._user("gc_super"), self._user("architect")],
                "questions": [{"id": rid * 10, "question_date": _ts(d["created"], 14), "plain_text_body": r["question"],
                               "rich_text_body": f"<p>{r['question']}</p>", "created_by": self._user(r["received_from"]),
                               "attachments": [], "answers": answers}],
                "cost_impact": impact(r["cost_impact"]), "schedule_impact": impact(r["schedule_impact"]),
                "location": None, "cost_code": None,
                "specification_section": {"id": _int_id("procore-spec", r["spec_section"], base=12000, span=9999),
                                          "number": r["spec_section"]},
                "custom_fields": {"custom_field_registry_element_ids": {"data_type": "string", "value": ",".join(r["element_ids"])}},
            }
            out[RFIS].append(_norm.rfi(r, self.name, rid, raw["full_number"], self.deep_link(RFIS, rid), raw))

        cc_ids = {c["code"]: _int_id("procore-cc", c["code"], base=8800000, span=99999) for c in st.cost_codes}
        for c in st.change_events:
            cid = _int_id("procore-ce", c["ref"], base=3300000, span=99999)
            sname = {"approved": "Closed", "pending": "Pending", "draft": "Open"}[c["status"]]
            raw = {
                "id": cid, "number": c["number"], "title": c["title"], "description": c["description"],
                "scope": "out_of_scope", "project_id": self.project_id, "company_id": COMPANY_ID,
                "status": {"id": {"Open": 1, "Pending": 2, "Closed": 3}[sname], "name": sname, "mapped_to_status": sname.lower()},
                "change_type": {"id": 1, "name": "Change Event", "abbreviation": "CE"},
                "change_reason": {"id": _int_id("procore-reason", c["reason"], base=100, span=899), "change_reason": c["reason"]},
                "event_origin": None, "source": "budget_change", "comments_enabled": True, "deletable": False,
                "in_recycle_bin": False, "currency_configuration": {"currency_iso_code": "USD"},
                "created_by": self._user("gc_pm"), "created_at": _ts(c["created"], 13), "updated_at": _ts(c["created"], 16),
                "change_items": [{"id": cid * 10 + i, "description": li["description"],
                                  "budget_code": f"{li['cost_code']}.S", "cost_code": {"id": cc_ids.get(li["cost_code"]), "full_code": li["cost_code"]},
                                  "revenue_rom": f"{li['amount']:.2f}", "cost_rom": f"{li['amount'] * 0.9:.2f}",
                                  "estimate": True}
                                 for i, li in enumerate(c["line_items"])],
                "attachments": [], "markup_items": [], "production_quantities": [],
            }
            out[CHANGE_EVENTS].append(_norm.change_event(c, self.name, cid, f"CE-{c['number']}", self.deep_link(CHANGE_EVENTS, cid), raw))
        for c in st.change_orders:
            cid = _int_id("procore-pco", c["ref"], base=4400000, span=99999)
            pco_status = {"approved": "approved", "pending": "pending", "draft": "draft"}[c["status"]]
            ce_id = _int_id("procore-ce", c["change_event_ref"], base=3300000, span=99999)
            raw = {
                "id": cid, "number": c["number"], "title": c["title"], "status": pco_status,
                "executed": c["status"] == "approved", "grand_total": f"{c['amount']:.2f}",
                "schedule_impact_amount": c["schedule_days"], "change_event_ids": [ce_id],
                "contract": {"id": _int_id("procore-prime", "prime"), "number": "PC-001", "title": "Prime Contract - Quayside Partners"},
                "change_order_package": ({"id": _int_id("procore-cop", c["ref"]), "number": c["number"]}
                                         if c["status"] == "approved" else None),
                "created_by": self._user("gc_pm"), "created_at": _ts(c["created"], 13),
                "approved_at": _ts(c["approved"]) if c["approved"] else None, "estimate": True,
            }
            out[CHANGE_ORDERS].append(_norm.change_order(c, self.name, cid, f"PCO-{c['number']}", self.deep_link(CHANGE_ORDERS, cid), raw))

        for c in st.cost_codes:
            cid = cc_ids[c["code"]]
            raw = {"id": cid, "name": c["name"], "full_code": c["code"], "code": c["code"].split()[-1],
                   "parent": {"id": _int_id("procore-div", c["division"], base=8700000, span=99999), "name": c["division"]},
                   "sortable_code": c["code"].replace(" ", ".")}
            out[COST_CODES].append(_norm.cost_code(c, self.name, cid, self.deep_link(COST_CODES, cid), raw))
        for b in st.budget_lines:
            bid = _int_id("procore-bli", b["ref"], base=9900000, span=99999)
            raw = {"id": bid, "description": b["description"],
                   "wbs_code": {"id": cc_ids[b["cost_code"]], "flat_code": f"{b['cost_code']}.S",
                                "description": next(c["name"] for c in st.cost_codes if c["code"] == b["cost_code"])},
                   "line_item_type": {"id": 2, "name": "Subcontract", "code": "S"},
                   "quantity": f"{b['quantity']:.2f}", "unit_of_measure": b["unit"], "unit_cost": f"{b['unit_cost']:.2f}",
                   "calculation_strategy": "automatic", "original_budget_amount": f"{b['amount']:.2f}",
                   "approved_budget_changes": "0.00", "revised_budget": f"{b['amount']:.2f}", "estimate": True,
                   "basis": b["basis"]}
            out[BUDGET_LINES].append(_norm.budget_line(b, self.name, bid, self.deep_link(BUDGET_LINES, bid), raw))

        for i, a in enumerate(st.activities):
            tid = _int_id("procore-task", a["ref"])
            raw = {"id": tid, "task_number": f"A{1000 + 10 * i}", "activity_id": a["ref"], "name": a["name"],
                   "wbs_code": a["wbs"], "start_date": a["actual_start"] or a["early_start"],
                   "finish_date": a["actual_finish"] or a["early_finish"], "percentage": a["percent_complete"],
                   "milestone": a["milestone"], "critical_path": a["critical"], "total_float": a["total_float"],
                   "predecessors": ", ".join(f"{p['ref']}{p['type']}{('+' + str(p['lag'])) if p['lag'] else ''}"
                                             for p in a["predecessors"]),
                   "resource_name": None, "parent_id": None}
            out[SCHEDULE_ACTIVITIES].append(_norm.activity(a, self.name, tid, raw["task_number"],
                                                           self.deep_link(SCHEDULE_ACTIVITIES, tid), raw))
        for s in st.sheets:
            did = _int_id("procore-dwg", s["ref"], base=50000000, span=999999)
            raw = {"id": did, "number": s["number"], "title": s["title"], "discipline": {"id": 3, "name": s["discipline"]},
                   "current_revision": {"id": did * 10 + int(s["revision"]), "revision_number": s["revision"],
                                        "drawing_date": s["issued"], "drawing_set": {"name": s["version_set"]}}}
            out[SHEETS].append(_norm.sheet(s, self.name, did, self.deep_link(SHEETS, did), raw))
        return out
