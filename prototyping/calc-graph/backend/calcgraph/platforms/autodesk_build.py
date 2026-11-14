"""Autodesk Construction Cloud (ACC) Build adapter (SYNTHETIC), shaped like the public APS APIs.

Shapes follow the Autodesk Platform Services ACC reference:

- Submittals items - READ: https://aps.autodesk.com/en/docs/acc/v1/reference/http/submittals-items-GET/
  (id, identifier, customIdentifier, title, typeId, specId/specIdentifier/specTitle, packageId/
  packageIdentifier/packageTitle, stateId: draft | sbc-1 | mgr-1 | rev | mgr-2 | sbc-2 | void,
  statusId: 1 Required, 2 Open, 3 Closed, 4 Void, 5 Empty, 6 Draft, ballInCourtUsers/Companies,
  manager, subcontractor, dueDate, requiredOnJobDate, sentToReview, receivedFromReview,
  publishedDate, responseId, responseComment, revision, createdAt, updatedAt). ACC has no
  fabricated / delivered / erected state; that rides in `customAttributes` (project-defined).
- RFIs v3 - release notes READ: https://aps.autodesk.com/node/3724 (assignedTo is a list;
  linkedDocument removed in v3). The v3 reference pages returned 404, so `title`, `question`,
  `dueDate`, `costImpact`, `scheduleImpact`, `customIdentifier` and the status vocabulary
  (draft / submitted / open / answered / closed / void) are recollection.
- Cost Management budgets - READ: https://aps.autodesk.com/en/docs/acc/v1/reference/http/cost-budgets-GET/
- Cost Management change orders - READ:
  https://aps.autodesk.com/en/docs/acc/v1/reference/http/cost-change-orders-changeOrder-id-GET
  (type pco / rfq / rco / oco / sco; budgetStatus + costStatus vocabularies per type). Our
  change EVENTS map to PCOs, our change ORDERS to OCOs (owner change orders).
- Sheets - READ: https://aps.autodesk.com/en/docs/acc/v1/reference/http/sheets-sheets-GET
- Budget codes / segments: recollection (not verified).
- Schedule: no public ACC Schedule REST API was found, so this adapter does NOT serve schedule
  activities (capability omitted on purpose).

All ids are deterministic UUIDs; deep links are mock://acc/... (never a real hub or project).
"""
from __future__ import annotations

from . import _norm
from .base import (BUDGET_LINES, CHANGE_EVENTS, CHANGE_ORDERS, COST_CODES, RFIS, SHEETS, SUBMITTALS,
                   NormalizedRecord, PlatformAdapter)
from .synthetic import ConstructionState, _uuid

HUB_ID = "b." + _uuid("acc-hub")
PROJECT_ID = _uuid("acc-project", "harbor-view")
PATH = {SUBMITTALS: "submittals/items", RFIS: "rfis", CHANGE_EVENTS: "cost/change-orders/pco",
        CHANGE_ORDERS: "cost/change-orders/oco", BUDGET_LINES: "cost/budgets", COST_CODES: "cost/budget-codes",
        SHEETS: "sheets"}


def _ts(date: str | None, hour: int = 15) -> str | None:
    return f"{date}T{hour:02d}:00:00.000Z" if date else None


class AutodeskBuildAdapter(PlatformAdapter):
    name = "autodesk_build"
    label = "Autodesk Construction Cloud Build (synthetic)"
    capabilities = frozenset({SUBMITTALS, RFIS, CHANGE_EVENTS, CHANGE_ORDERS, BUDGET_LINES, COST_CODES, SHEETS})
    doc_urls = {
        SUBMITTALS: "https://aps.autodesk.com/en/docs/acc/v1/reference/http/submittals-items-GET/",
        RFIS: "https://aps.autodesk.com/node/3724",
        CHANGE_EVENTS: "https://aps.autodesk.com/en/docs/acc/v1/reference/http/cost-change-orders-changeOrder-id-GET",
        CHANGE_ORDERS: "https://aps.autodesk.com/en/docs/acc/v1/reference/http/cost-change-orders-changeOrder-id-GET",
        BUDGET_LINES: "https://aps.autodesk.com/en/docs/acc/v1/reference/http/cost-budgets-GET/",
        COST_CODES: "https://aps.autodesk.com/en/docs/acc/v1/reference/http/cost-budgets-GET/",
        SHEETS: "https://aps.autodesk.com/en/docs/acc/v1/reference/http/sheets-sheets-GET",
    }

    def __init__(self, state: ConstructionState):
        super().__init__()
        self.state = state
        self.project_id = PROJECT_ID

    def deep_link(self, record_type: str, id: str) -> str:
        return f"mock://acc/projects/{self.project_id}/{PATH.get(record_type, record_type)}/{id}"

    def _uid(self, person: str) -> str:
        return _uuid("acc-user", person)[:12].upper().replace("-", "")

    def _company(self, name: str) -> str:
        return _uuid("acc-company", name)

    def _build(self) -> dict[str, list[NormalizedRecord]]:
        st = self.state
        P = st.project["people"]
        out: dict[str, list[NormalizedRecord]] = {k: [] for k in self.capabilities}
        state_of = {"draft": ("draft", 6), "submitted": ("rev", 2)}
        packages: dict[str, tuple[str, int]] = {}
        for i, s in enumerate(st.submittals, 1):
            sid = _uuid("acc-sub", s["ref"])
            state_id, status_id = state_of.get(s["status"], ("sbc-2", 3))
            pk = s["spec_section"][:5]
            packages.setdefault(pk, (_uuid("acc-pkg", pk), len(packages) + 1))
            d = s["dates"]
            sub_co = s["responsible_contractor"]
            raw = {
                "id": sid, "identifier": i, "customIdentifier": s["number"], "customIdentifierHumanReadable": s["number"],
                "title": s["title"], "description": f"{s['title']} ({len(s['element_ids'])} model elements).",
                "typeId": "shopdrawings" if "shop" in s["package_kind"] or s["package_kind"] in ("anchor_rods", "connection_design") else "productdata",
                "priority": "Normal", "revision": s["revision"],
                "specId": _uuid("acc-spec", s["spec_section"]), "specIdentifier": s["spec_section"], "specTitle": s["spec_title"],
                "subsection": None,
                "packageId": packages[pk][0], "packageIdentifier": packages[pk][1],
                "packageTitle": {"03 20": "Foundations", "03 30": "Foundations", "05 12": "Structural steel",
                                 "05 31": "Steel deck", "07 81": "Fireproofing"}.get(pk, pk),
                "stateId": state_id, "statusId": status_id,
                "ballInCourtUsers": ([self._uid(P["eor"])] if s["status"] == "submitted" else []),
                "ballInCourtCompanies": ([self._company(sub_co)] if s["status"] == "draft" else []),
                "ballInCourtRoles": [], "ballInCourtType": "reviewer" if s["status"] == "submitted" else
                                    ("submitter" if s["status"] == "draft" else None),
                "manager": self._uid(P["gc_pm"]), "managerType": 1,
                "subcontractor": self._company(sub_co), "subcontractorType": 2, "watchers": [],
                "dueDate": d["due"], "requiredDate": d["due"], "requiredApprovalDate": d["due"],
                "requiredOnJobDate": d.get("required_on_job"), "leadTime": 15,
                "sentToSubmitter": _ts(d["created"], 13), "receivedFromSubmitter": _ts(d["submitted"]),
                "sentToReview": _ts(d["submitted"]), "receivedFromReview": _ts(d["returned"]),
                "publishedDate": _ts(d["returned"], 17), "respondedAt": _ts(d["returned"]),
                "respondedBy": self._uid(P["eor"]) if d["returned"] else None,
                "submittedBy": self._uid(P["steel_pm"]) if d["submitted"] else None,
                "responseId": ({"Approved": "approved", "Approved as Noted": "approved-as-noted"}.get(s["response"])
                               if s["response"] else None),
                "responseComment": None,
                "customAttributes": [
                    {"attributeDefinitionId": _uuid("acc-attr", "fab"), "title": "Fabrication status", "type": "list",
                     "value": s["stage"].capitalize()},
                    {"attributeDefinitionId": _uuid("acc-attr", "deliv"), "title": "Actual delivery", "type": "date",
                     "value": d.get("actual_delivery")},
                    {"attributeDefinitionId": _uuid("acc-attr", "elems"), "title": "Model element ids", "type": "text",
                     "value": ",".join(s["element_ids"][:50]) + ("..." if len(s["element_ids"]) > 50 else "")},
                ],
                "createdAt": _ts(d["created"], 13), "updatedAt": _ts(d["returned"] or d["submitted"] or d["created"], 18),
            }
            out[SUBMITTALS].append(_norm.submittal(s, self.name, sid, s["number"], self.deep_link(SUBMITTALS, sid), raw))

        for r in st.rfis:
            rid = _uuid("acc-rfi", r["ref"])
            d = r["dates"]
            raw = {
                "id": rid, "customIdentifier": r["number"].split("-")[1], "title": r["subject"], "question": r["question"],
                "status": {"draft": "draft", "open": "open", "answered": "answered", "closed": "closed"}[r["status"]],
                "assignedTo": [{"id": self._uid(r["assignee"]), "type": "user"}], "architects": [],
                "watchers": [self._uid(P["gc_super"])], "officialResponse": r["answer"],
                "responses": ([{"id": _uuid("acc-rfi-resp", r["ref"]), "text": r["answer"], "createdBy": self._uid(r["assignee"]),
                                "createdAt": _ts(d["answered"])}] if r["answer"] else []),
                "dueDate": d["due"], "createdAt": _ts(d["created"], 14), "updatedAt": _ts(d["answered"] or d["created"], 16),
                "closedAt": _ts(d["closed"]), "createdBy": self._uid(r["received_from"]),
                "costImpact": {"yes": "Yes", "no": "No", "tbd": "Unknown"}[r["cost_impact"]],
                "scheduleImpact": {"yes": "Yes", "no": "No", "tbd": "Unknown"}[r["schedule_impact"]],
                "reference": r["drawing_number"], "discipline": ["Structural"], "category": ["Coordination"],
                "locations": [], "priority": "Normal",
                "customAttributes": [{"title": "Model element ids", "type": "text", "value": ",".join(r["element_ids"])}],
            }
            out[RFIS].append(_norm.rfi(r, self.name, rid, r["number"], self.deep_link(RFIS, rid), raw))

        budget_ids = {b["ref"]: _uuid("acc-budget", b["ref"]) for b in st.budget_lines}
        for c in st.change_events:
            cid = _uuid("acc-pco", c["ref"])
            bs = {"approved": "approved", "pending": "submitted", "draft": "draft"}[c["status"]]
            cs = {"approved": "approved", "pending": "pricing", "draft": "draft"}[c["status"]]
            raw = self._change_order(cid, "pco", c["number"], c["title"], c["description"], bs, cs, c["amount"], 0,
                                     c["created"], None, c["line_items"])
            out[CHANGE_EVENTS].append(_norm.change_event(c, self.name, cid, f"PCO-{c['number']}", self.deep_link(CHANGE_EVENTS, cid), raw))
        for c in st.change_orders:
            cid = _uuid("acc-oco", c["ref"])
            bs = {"approved": "executed", "pending": "inReview", "draft": "draft"}[c["status"]]
            ce = next(e for e in st.change_events if e["ref"] == c["change_event_ref"])
            raw = self._change_order(cid, "oco", c["number"], c["title"], ce["description"], bs, None, c["amount"],
                                     c["schedule_days"], c["created"], c["approved"], ce["line_items"])
            raw["sourceId"], raw["sourceType"] = _uuid("acc-pco", c["change_event_ref"]), "ChangeOrder"
            out[CHANGE_ORDERS].append(_norm.change_order(c, self.name, cid, f"OCO-{c['number']}", self.deep_link(CHANGE_ORDERS, cid), raw))

        for c in st.cost_codes:
            cid = _uuid("acc-code", c["code"])
            raw = {"id": cid, "segmentId": _uuid("acc-seg", "csi"), "code": c["code"].replace(" ", ""),
                   "description": c["name"], "parentId": _uuid("acc-code", c["division"])}
            out[COST_CODES].append(_norm.cost_code(c, self.name, cid, self.deep_link(COST_CODES, cid), raw))
        for b in st.budget_lines:
            bid = budget_ids[b["ref"]]
            raw = {"id": bid, "parentId": None, "code": b["cost_code"].replace(" ", ""), "name": b["description"],
                   "description": b["basis"], "scope": "budgetAndCost", "budgetCode": b["cost_code"].replace(" ", ""),
                   "quantity": b["quantity"], "inputQuantity": b["quantity"], "unit": b["unit"], "unitPrice": b["unit_cost"],
                   "originalAmount": b["amount"], "internalAdjustment": 0, "approvedOwnerChanges": 0,
                   "pendingOwnerChanges": 0, "approvedChangeOrders": 0, "pendingChangeOrders": 0, "reserves": 0,
                   "actualCost": 0, "uncommitted": b["amount"], "revised": b["amount"], "projectedCost": b["amount"],
                   "projectedBudget": b["amount"], "forecastFinalCost": b["amount"], "forecastVariance": 0,
                   "externalId": None, "externalSystem": None, "integrationState": None,
                   "createdAt": _ts(st.project["start"], 13), "updatedAt": _ts(st.project["data_date"], 9)}
            out[BUDGET_LINES].append(_norm.budget_line(b, self.name, bid, self.deep_link(BUDGET_LINES, bid), raw))

        vs = {}
        for s in st.sheets:
            sid = _uuid("acc-sheet", s["ref"])
            vs.setdefault(s["version_set"], _uuid("acc-vs", s["version_set"]))
            raw = {"id": sid, "number": s["number"], "title": s["title"],
                   "versionSet": {"id": vs[s["version_set"]], "name": s["version_set"], "issuanceDate": s["issued"], "deleted": False},
                   "isCurrent": True, "tags": ["Structural"], "paperSize": "ARCH D", "uploadFileName": f"{s['number']}.pdf",
                   "uploadId": _uuid("acc-upload", s["ref"]), "createdAt": _ts(s["issued"], 12),
                   "createdBy": self._uid(P["eor"]), "createdByName": P["eor"], "updatedAt": _ts(s["issued"], 12),
                   "updatedBy": self._uid(P["eor"]), "updatedByName": P["eor"], "deleted": False,
                   "viewable": {"urn": f"urn:adsk.wipprod:fs.file:vf.{_uuid('acc-file', s['ref'])}?version=1",
                                "guid": _uuid("acc-viewable", s["ref"])}, "collection": None}
            out[SHEETS].append(_norm.sheet(s, self.name, sid, self.deep_link(SHEETS, sid), raw))
        return out

    def _change_order(self, cid, typ, number, name, desc, budget_status, cost_status, amount, days, created, approved, items):
        P = self.state.project["people"]
        return {
            "id": cid, "number": number, "name": name, "description": desc, "type": typ, "scope": "out",
            "sourceId": None, "sourceType": None, "creatorId": self._uid(P["gc_pm"]), "ownerId": self._uid(P["gc_pm"]),
            "companyId": self._company(self.state.project["companies"]["gc"]),
            "architectCompanyId": self._company(self.state.project["companies"]["architect"]),
            "estimated": amount, "proposed": amount if budget_status != "draft" else 0,
            "submitted": amount if budget_status not in ("draft",) else 0,
            "approved": amount if budget_status in ("approved", "executed") else 0, "committed": 0,
            "scheduleChange": days, "proposedRevisedCompletionDate": None, "scopeOfWork": desc, "note": "",
            "budgetStatus": budget_status, "costStatus": cost_status,
            "costItems": [{"id": _uuid("acc-ci", cid, i), "name": li["description"], "budgetCode": li["cost_code"].replace(" ", ""),
                           "estimated": li["amount"], "budgetStatus": budget_status} for i, li in enumerate(items)],
            "createdAt": _ts(created, 13), "updatedAt": _ts(approved or created, 16), "estimate": True,
        }
