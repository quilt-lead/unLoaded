"""Typed client for the ACC (Autodesk Build, now "Forma Build") endpoints that have NO official OpenAPI spec.

Autodesk's spec repo (aps-sdk-openapi @ 1e2490246ad3, 2026-11-05) publishes Authentication, Data Management,
Issues and Account Admin - generated into generated/aps_*_client. RFIs v3, Submittals v2, Cost Management
and Sheets are NOT in it, so this module is written by hand from the APS reference pages below (each read
2026-11-14). The response models are pydantic with `extra="allow"`: only fields named on the reference page
are declared, anything else the API returns is kept untouched in `model_extra`.

Endpoints (base https://developer.api.autodesk.com; projectId = Data Management project id WITHOUT "b."):

  RFIs v3       POST /construction/rfis/v3/projects/{projectId}/search:rfis   body {limit<=200, offset, filter, sort}
                     https://aps.autodesk.com/en/docs/acc/v1/reference/http/rfis-rfi-search-POST/
                POST /construction/rfis/v3/projects/{projectId}/rfis          required: status, title
                     https://aps.autodesk.com/en/docs/acc/v1/reference/http/rfis-rfis-POST
  Submittals v2 GET  /construction/submittals/v2/projects/{projectId}/items    limit 1-50, offset
                     https://aps.autodesk.com/en/docs/acc/v1/reference/http/submittals-items-GET
                POST /construction/submittals/v2/projects/{projectId}/items    required: typeId, specId, title, stateId
                     https://aps.autodesk.com/en/docs/acc/v1/reference/http/submittals-items-POST
                GET  /construction/submittals/v2/projects/{projectId}/specs    limit 1-50
                     https://aps.autodesk.com/en/docs/acc/v1/reference/http/submittals-specs-GET
                GET  /construction/submittals/v2/projects/{projectId}/item-types   (named as the typeId source on the
                     items-POST page; its own reference page was not opened - path by that page's convention)
  Cost          GET  /cost/v1/containers/{containerId}/budgets                 containerId == projectId
                     https://aps.autodesk.com/en/docs/acc/v1/reference/http/cost-budgets-GET
                GET  /cost/v1/containers/{containerId}/change-orders/{pco|rfq|rco|oco|sco}
                     https://aps.autodesk.com/en/docs/acc/v1/reference/http/cost-change-orders-changeOrder-GET
                POST /cost/v1/containers/{containerId}/change-orders/{changeOrder}
                     https://aps.autodesk.com/en/docs/acc/v1/reference/http/cost-change-orders-changeOrder-POST
  Sheets        GET  /construction/sheets/v1/projects/{projectId}/sheets       limit 1-100
                     https://aps.autodesk.com/en/docs/acc/v1/reference/http/sheets-sheets-GET
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from .transport import Session

BASE = "https://developer.api.autodesk.com"
CO_TYPES = ("pco", "rfq", "rco", "oco", "sco")


class _M(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)


class AccRfi(_M):
    id: str
    customIdentifier: str | None = None
    title: str | None = None
    question: str | None = None
    status: str | None = None
    previousStatus: str | None = None
    workflowType: str | None = None
    assignedTo: list | None = None
    managerId: str | None = None
    dueDate: str | None = None
    officialResponse: str | None = None
    officialResponseStatus: str | None = None
    costImpact: str | None = None
    scheduleImpact: str | None = None
    priority: str | None = None
    reference: str | None = None
    createdAt: str | None = None
    updatedAt: str | None = None
    closedAt: str | None = None


class AccSubmittal(_M):
    id: str
    identifier: int | str | None = None
    customIdentifier: str | None = None
    title: str | None = None
    description: str | None = None
    typeId: str | None = None
    specId: str | None = None
    specIdentifier: str | None = None
    specTitle: str | None = None
    packageId: str | None = None
    packageTitle: str | None = None
    stateId: str | None = None
    statusId: int | str | None = None
    revision: int | str | None = None
    dueDate: str | None = None
    requiredOnJobDate: str | None = None
    responseId: str | None = None
    responseComment: str | None = None
    createdAt: str | None = None
    updatedAt: str | None = None


class AccSpec(_M):
    id: str
    identifier: str | None = None
    title: str | None = None


class AccChangeOrder(_M):
    id: str
    number: str | int | None = None
    name: str | None = None
    description: str | None = None
    scope: str | None = None
    budgetStatus: str | None = None
    costStatus: str | None = None
    estimated: float | str | None = None
    proposed: float | str | None = None
    submitted: float | str | None = None
    approved: float | str | None = None
    committed: float | str | None = None
    externalId: str | None = None
    externalSystem: str | None = None
    createdAt: str | None = None
    updatedAt: str | None = None


class AccBudget(_M):
    id: str
    parentId: str | None = None
    code: str | None = None
    name: str | None = None
    description: str | None = None
    quantity: float | None = None
    unitPrice: float | str | None = None
    unit: str | None = None
    originalAmount: float | None = None
    revised: float | None = None
    externalId: str | None = None
    externalSystem: str | None = None


class AccSheet(_M):
    id: str
    number: str | None = None
    title: str | None = None
    versionSet: dict | None = None
    tags: list | None = None
    isCurrent: bool | None = None
    createdAt: str | None = None
    updatedAt: str | None = None


def project_id_for_acc(dm_project_id: str) -> str:
    """ACC product APIs take the Data Management project id without its "b." prefix."""
    return dm_project_id[2:] if dm_project_id.startswith("b.") else dm_project_id


class AccRest:
    def __init__(self, session: Session, project_id: str, region: str | None = None):
        self.s = session
        self.pid = project_id_for_acc(project_id)
        self.cost_headers = {"region": region} if region else None   # documented on the Cost pages only

    # -------------------------------------------------------------- reads
    def rfis(self) -> list[AccRfi]:
        rows = self.s.acc_pages("POST", f"{BASE}/construction/rfis/v3/projects/{self.pid}/search:rfis", limit=200,
                                body={}, what="search:rfis")
        return [AccRfi.model_validate(r) for r in rows]

    def submittals(self) -> list[AccSubmittal]:
        rows = self.s.acc_pages("GET", f"{BASE}/construction/submittals/v2/projects/{self.pid}/items", limit=50,
                                what="submittals items")
        return [AccSubmittal.model_validate(r) for r in rows]

    def specs(self) -> list[AccSpec]:
        rows = self.s.acc_pages("GET", f"{BASE}/construction/submittals/v2/projects/{self.pid}/specs", limit=50,
                                what="submittals specs")
        return [AccSpec.model_validate(r) for r in rows]

    def item_types(self) -> list[dict]:
        return self.s.acc_pages("GET", f"{BASE}/construction/submittals/v2/projects/{self.pid}/item-types", limit=50,
                                what="submittals item-types")

    def change_orders(self, co_type: str) -> list[AccChangeOrder]:
        assert co_type in CO_TYPES
        rows = self.s.acc_pages("GET", f"{BASE}/cost/v1/containers/{self.pid}/change-orders/{co_type}", limit=100,
                                what=f"change-orders/{co_type}", headers=self.cost_headers)
        return [AccChangeOrder.model_validate(r) for r in rows]

    def budgets(self) -> list[AccBudget]:
        rows = self.s.acc_pages("GET", f"{BASE}/cost/v1/containers/{self.pid}/budgets", limit=100, what="budgets",
                                headers=self.cost_headers)
        return [AccBudget.model_validate(r) for r in rows]

    def sheets(self) -> list[AccSheet]:
        rows = self.s.acc_pages("GET", f"{BASE}/construction/sheets/v1/projects/{self.pid}/sheets", limit=100,
                                params={"currentOnly": "true"}, what="sheets")
        return [AccSheet.model_validate(r) for r in rows]

    # -------------------------------------------------------------- writes (seeding script only)
    def create_rfi(self, body: dict) -> AccRfi:
        assert body.get("status") and body.get("title"), "RFI create requires status and title"
        data, _ = self.s.request("POST", f"{BASE}/construction/rfis/v3/projects/{self.pid}/rfis", json_body=body,
                                 what="create rfi")
        return AccRfi.model_validate(data)

    def create_submittal(self, body: dict) -> AccSubmittal:
        missing = [k for k in ("typeId", "specId", "title", "stateId") if not body.get(k)]
        assert not missing, f"submittal create requires {missing}"
        data, _ = self.s.request("POST", f"{BASE}/construction/submittals/v2/projects/{self.pid}/items",
                                 json_body=body, what="create submittal")
        return AccSubmittal.model_validate(data)

    def create_change_order(self, co_type: str, body: dict) -> AccChangeOrder:
        assert co_type in CO_TYPES
        data, _ = self.s.request("POST", f"{BASE}/cost/v1/containers/{self.pid}/change-orders/{co_type}",
                                 json_body=body, what=f"create {co_type}", headers=self.cost_headers)
        return AccChangeOrder.model_validate(data)
