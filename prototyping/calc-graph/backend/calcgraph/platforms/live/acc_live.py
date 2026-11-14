"""Autodesk Construction Cloud Build (renamed "Forma Build" by Autodesk on 2026-03-24) LIVE adapter.

Reads one ACC project the signed-in user can see, through:
  - generated clients (official aps-sdk-openapi specs): Data Management (hub/project lookup) and Issues;
  - acc_rest.py (hand-written, cited per endpoint) for RFIs v3, Submittals v2, Cost Management, Sheets.

Record types served: submittals, rfis, change_events (Cost PCOs), change_orders (Cost OCOs), budget_lines,
sheets, issues. Not served: schedule_activities (no public ACC schedule REST API was found), cost_codes
(budget codes ride on the budget lines instead).

Config (data/secrets/aps_app.json or env): hub_id (ACC_HUB_ID, "b.<account id>"), project_id (ACC_PROJECT_ID,
with or without "b."), region (ACC_REGION, optional: US | EMEA; sent only where the docs define it).
"""
from __future__ import annotations

import os

from ..base import (BUDGET_LINES, CHANGE_EVENTS, CHANGE_ORDERS, ISSUES, RFIS, SHEETS, SUBMITTALS, NormalizedRecord,
                    PlatformAdapter)
from . import links
from . import secrets as store
from .acc_rest import BASE, AccRest, project_id_for_acc
from .generated.aps_issues_client import AuthenticatedClient
from .generated.aps_issues_client.api.calcgraph import get_issues
from .transport import LiveError, Recorded, Session

SUB_STATUS = {"6": "draft", "1": "draft", "5": "draft", "3": "approved"}
RFI_STATUS = {"draft": "draft", "submitted": "open", "open": "open", "openRev1": "open", "openRev2": "open",
              "answered": "answered", "answeredRev1": "answered", "answeredManager": "answered",
              "closed": "closed", "rejected": "closed"}
CO_STATUS = {"draft": "draft", "approved": "approved", "executed": "approved", "rejected": "rejected", "void": "void"}


def _sub_status(s) -> str | None:
    if str(s.statusId) == "4" or s.stateId == "void":
        return None                       # void items are not served
    if str(s.statusId) == "2":            # Open: with the submitter (sbc-*) or under review (mgr-*/rev)
        return "draft" if (s.stateId or "").startswith("sbc") else "submitted"
    return SUB_STATUS.get(str(s.statusId), "submitted")


def _f(x) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


class AccLiveAdapter(PlatformAdapter):
    name = "autodesk_build"
    capabilities = frozenset({SUBMITTALS, RFIS, CHANGE_EVENTS, CHANGE_ORDERS, BUDGET_LINES, SHEETS, ISSUES})
    doc_urls = {"rfis": "https://aps.autodesk.com/en/docs/acc/v1/reference/http/rfis-rfi-search-POST/",
                "submittals": "https://aps.autodesk.com/en/docs/acc/v1/reference/http/submittals-items-GET",
                "cost": "https://aps.autodesk.com/en/docs/acc/v1/reference/http/cost-change-orders-changeOrder-GET",
                "sheets": "https://aps.autodesk.com/en/docs/acc/v1/reference/http/sheets-sheets-GET",
                "issues": "https://github.com/autodesk-platform-services/aps-sdk-openapi/blob/main/forma/issues/Issues.yaml"}

    def __init__(self, state=None, recorded: Recorded | None = None, config: dict | None = None):
        super().__init__()
        self.state_for_links = state
        cfg = config if config is not None else store.app_config("aps")
        if not cfg.get("project_id"):
            raise LiveError("ACC project not configured (ACC_PROJECT_ID / data/secrets/aps_app.json project_id); "
                            "run scripts/platform_auth.py projects aps")
        self.hub_id = cfg.get("hub_id")
        self.project_id = project_id_for_acc(cfg["project_id"])
        self.region = cfg.get("region") or os.environ.get("ACC_REGION")
        self.label = f"Autodesk Build (live: ACC project {self.project_id[:8]}...)"
        self.recorded = recorded
        self.session: Session | None = None

    def _session(self) -> Session:
        if self.session is None:
            self.session = Session("aps", BASE, AuthenticatedClient, recorded=self.recorded)
        return self.session

    def deep_link(self, record_type: str, id: str) -> str:
        """API resource URL (no ACC web-UI URL pattern is documented in the API reference, so none is guessed)."""
        p = self.project_id
        return {SUBMITTALS: f"{BASE}/construction/submittals/v2/projects/{p}/items/{id}",
                RFIS: f"{BASE}/construction/rfis/v3/projects/{p}/rfis/{id}",
                CHANGE_EVENTS: f"{BASE}/cost/v1/containers/{p}/change-orders/pco/{id}",
                CHANGE_ORDERS: f"{BASE}/cost/v1/containers/{p}/change-orders/oco/{id}",
                BUDGET_LINES: f"{BASE}/cost/v1/containers/{p}/budgets/{id}",
                SHEETS: f"{BASE}/construction/sheets/v1/projects/{p}/sheets/{id}",
                ISSUES: f"{BASE}/construction/issues/v1/projects/{p}/issues/{id}"}.get(record_type, f"{BASE}/{record_type}/{id}")

    def _issues(self) -> list[dict]:
        s, out, offset = self._session(), [], 0
        while True:
            data, _ = s.call(get_issues, project_id=self.project_id, limit=100, offset=offset)
            res = (data or {}).get("results") or []
            out += res
            total = ((data or {}).get("pagination") or {}).get("totalResults")
            offset += len(res)
            if not res or (total is not None and offset >= total):
                return out

    def _build(self) -> dict[str, list[NormalizedRecord]]:
        api = AccRest(self._session(), self.project_id, self.region)
        res = links.Resolver(self.state_for_links)
        out: dict[str, list[NormalizedRecord]] = {k: [] for k in self.capabilities}

        def add(rt, kind, raw: dict, number, title, status, ref, explicit, dates=None, fields=None):
            out[rt].append(NormalizedRecord(
                kind=kind, id=str(raw["id"]), ref=ref or f"acc:{kind}:{raw['id']}", platform=self.name,
                number=str(number if number is not None else raw["id"]), title=title or "", status=status,
                element_ids=res.elements(ref, explicit), dates=dates or {}, links={"self": self.deep_link(rt, raw["id"])},
                fields=fields or {}, raw=raw))

        for s in api.submittals():
            st = _sub_status(s)
            if st is None:
                continue
            raw = s.model_dump(mode="json")
            ref, el = links.parse(s.description, s.title)
            add(SUBMITTALS, "submittal", raw, s.customIdentifier or s.identifier, s.title, st, ref, el,
                dates={"due": s.dueDate, "required_on_job": s.requiredOnJobDate},
                fields={"stage": {"draft": "design", "submitted": "submitted"}.get(st, "approved"), "stage_notes": [],
                        "spec_section": s.specIdentifier or "", "spec_title": s.specTitle or "",
                        "package_kind": "shop_drawings", "level": None, "sequence": None, "revision": s.revision,
                        "response": s.responseId, "ball_in_court": None, "activity_refs": [],
                        "vendor_status": {"stateId": s.stateId, "statusId": s.statusId}})

        for r in api.rfis():
            if r.status == "void":
                continue
            raw = r.model_dump(mode="json")
            ref, el = links.parse(r.question, r.reference, r.title)
            add(RFIS, "rfi", raw, r.customIdentifier, r.title, RFI_STATUS.get(r.status or "", "open"), ref, el,
                dates={"due": r.dueDate, "created": r.createdAt, "closed": r.closedAt},
                fields={"question": r.question, "answer": r.officialResponse, "ball_in_court": None,
                        "cost_impact": r.costImpact, "schedule_impact": r.scheduleImpact, "drawing_number": None,
                        "spec_section": None, "vendor_status": r.status})

        for rt, co_type in ((CHANGE_EVENTS, "pco"), (CHANGE_ORDERS, "oco")):
            for c in api.change_orders(co_type):
                raw = c.model_dump(mode="json")
                ref, el = links.parse((c.externalId or "").replace("calc-graph:", "calc-graph "), c.description, c.name)
                status = CO_STATUS.get(c.budgetStatus or c.costStatus or "", "pending")
                amount = _f(c.approved) or _f(c.submitted) or _f(c.proposed) or _f(c.estimated)
                kind = "change_event" if rt == CHANGE_EVENTS else "change_order"
                fields = {"amount_usd": amount, "estimate": not bool(_f(c.approved)), "co_type": co_type,
                          "vendor_status": {"budgetStatus": c.budgetStatus, "costStatus": c.costStatus}}
                if rt == CHANGE_EVENTS:
                    fields.update(reason=c.description, line_items=None, change_order_refs=[])
                else:
                    fields.update(schedule_days=None, change_event_ref=None)
                add(rt, kind, raw, c.number, c.name, status, ref, el, dates={"created": c.createdAt}, fields=fields)

        for b in api.budgets():
            raw = b.model_dump(mode="json")
            ref, el = links.parse((b.externalId or "").replace("calc-graph:", "calc-graph "), b.description)
            add(BUDGET_LINES, "budget_line", raw, b.code, b.name, "active", ref or f"acc:budget:{b.id}", el,
                fields={"cost_code": b.code, "quantity": b.quantity, "unit": b.unit, "unit_cost_usd": _f(b.unitPrice),
                        "amount_usd": _f(b.revised) or _f(b.originalAmount), "basis": "ACC budget (revised, else original)",
                        "estimate": False})

        for sh in api.sheets():
            raw = sh.model_dump(mode="json")
            vs = sh.versionSet or {}
            add(SHEETS, "sheet", raw, sh.number, sh.title, "active", f"SHEET:{sh.number}", [],
                dates={"issued": vs.get("issuanceDate")},
                fields={"discipline": None, "revision": None, "version_set": vs.get("name")})

        for i in self._issues():
            ref, el = links.parse(i.get("description"), i.get("title"))
            add(ISSUES, "issue", i, i.get("displayId"), i.get("title"), i.get("status") or "open", ref, el,
                dates={"due": i.get("dueDate"), "created": i.get("createdAt"), "closed": i.get("closedAt")},
                fields={"vendor_status": i.get("status")})
        return out

    def describe(self) -> dict:
        d = super().describe()
        d.update(synthetic=False, project_id=self.project_id, hub_id=self.hub_id,
                 parse_errors=(self.session.parse_errors if self.session else []))
        return d
