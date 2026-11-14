"""Procore LIVE adapter: reads a Procore Developer Sandbox (or Monthly Sandbox) project through the typed
client generated from Procore's official OpenAPI document (generated/procore_client), and serves the same
PlatformAdapter surface as the synthetic procore.py.

Endpoints called (all present in the Procore OAS, x-created-at 2026-11-13; see docs/platforms-real.md):

  submittals           GET /rest/v1.1/projects/{project_id}/submittals            (page/per_page)
  rfis                 GET /rest/v1.0/projects/{project_id}/rfis
  change_events        GET /rest/v1.1/change_events?project_id=
  change_orders        GET /rest/v1.0/change_order_packages?project_id=
  commitments          GET /rest/v1.0/commitments?project_id=                     (extras; no base record type)
  schedule_activities  GET /rest/v1.0/tasks?project_id=
  sheets               GET /rest/v1.1/projects/{project_id}/drawing_areas, then
                       GET /rest/v1.1/drawing_areas/{drawing_area_id}/drawings
  cost_codes           GET /rest/v1.0/cost_codes?project_id=
Every request carries `Procore-Company-Id` (a header parameter in the spec itself) and a Bearer token.

Not served live (and why): budget_lines - v1.x has no list-by-project GET (only POST/GET-by-id; the v2.0
company-scoped list is not wired); total float of a schedule task - the task object has none
(`total_float_days` is None, `float_known` False). Registry element links come only from the
calc-graph marker (links.py) the seeding script writes; an unmarked record keeps `element_ids=[]`.
"""
from __future__ import annotations

from ..base import (CHANGE_EVENTS, CHANGE_ORDERS, COST_CODES, RFIS, SCHEDULE_ACTIVITIES, SHEETS, SUBMITTALS,
                    NormalizedRecord, PlatformAdapter)
from . import links, oauth
from . import secrets as store
from .generated.procore_client import AuthenticatedClient
from .generated.procore_client.api.calcgraph import (list_change_events, list_change_order_packages, list_commitments,
                                                     list_cost_codes, list_drawing_areas, list_drawings, list_rfis,
                                                     list_submittals, list_tasks)
from .transport import LiveError, Recorded, Session

API_PATH = {SUBMITTALS: "rest/v1.1/projects/{p}/submittals/{id}", RFIS: "rest/v1.0/projects/{p}/rfis/{id}",
            CHANGE_EVENTS: "rest/v1.1/change_events/{id}?project_id={p}",
            CHANGE_ORDERS: "rest/v1.0/change_order_packages/{id}?project_id={p}",
            COST_CODES: "rest/v1.0/cost_codes/{id}?project_id={p}", SCHEDULE_ACTIVITIES: "rest/v1.0/tasks/{id}?project_id={p}",
            SHEETS: "rest/v1.1/drawing_areas/{area}/drawings"}


def _status_submittal(s: dict) -> str:
    st = (s.get("status") or {})
    cat, name = (st.get("status") or "").lower(), (st.get("name") or "").lower()
    if cat == "draft":
        return "draft"
    if cat == "open":
        return "revise_resubmit" if ("revise" in name or "reject" in name) else "submitted"
    if "revise" in name or "reject" in name:
        return "revise_resubmit"
    return "approved"


def _stage_submittal(status: str, s: dict) -> str:
    if s.get("actual_delivery_date"):
        return "delivered"
    return {"draft": "design", "submitted": "submitted", "revise_resubmit": "submitted"}.get(status, "approved")


def _package_kind(s: dict) -> str:
    t = ((s.get("type") or {}).get("name") or "").lower()
    if "product" in t:
        return "product_data"
    if "calc" in t or "design" in t:
        return "connection_design"
    return "shop_drawings"


RFI_STATUS = {"open": "open", "closed": "closed", "draft": "draft", "closed_with_revision": "closed", "closed_draft": "draft"}
CE_STATUS = {"open": "pending", "pending": "pending", "closed": "approved", "void": "void"}
CO_STATUS = {"draft": "draft", "approved": "approved", "no_charge": "approved", "rejected": "rejected",
             "not_proceeding": "rejected", "void": "void"}


def _num(x) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


class ProcoreLiveAdapter(PlatformAdapter):
    name = "procore"
    capabilities = frozenset({SUBMITTALS, RFIS, CHANGE_EVENTS, CHANGE_ORDERS, COST_CODES, SCHEDULE_ACTIVITIES, SHEETS})
    doc_urls = {"oas": "https://developers.procore.com/api/v1/resource_groups/full_oas?version=1",
                "auth": "https://developers.procore.com/documentation/oauth-auth-grant-flow",
                "environments": "https://developers.procore.com/documentation/development-environments"}

    def __init__(self, state=None, recorded: Recorded | None = None, config: dict | None = None):
        super().__init__()
        self.state_for_links = state        # used only to resolve marker refs -> element ids
        cfg = config if config is not None else store.app_config("procore")
        self.env = oauth.procore_env(cfg)
        self.company_id = int(cfg["company_id"]) if cfg.get("company_id") else None
        self.project_id = int(cfg["project_id"]) if cfg.get("project_id") else None
        if not (self.company_id and self.project_id):
            raise LiveError("Procore company_id / project_id not configured (PROCORE_COMPANY_ID, PROCORE_PROJECT_ID "
                            "or data/secrets/procore_app.json); run scripts/platform_auth.py projects procore")
        self.label = f"Procore (live: {self.env['name']} project {self.project_id})"
        self.recorded = recorded
        self.session: Session | None = None
        self.extras: dict[str, list[dict]] = {}
        self._area_of: dict[str, int] = {}

    def _session(self) -> Session:
        if self.session is None:
            self.session = Session("procore", self.env["api"], AuthenticatedClient, recorded=self.recorded)
        return self.session

    def deep_link(self, record_type: str, id: str) -> str:
        """API resource URL in the configured sandbox (Procore's web-UI URL pattern is not documented in the
        OAS, so no UI link is guessed; an RFI's own `link` field is used when the API returns one)."""
        rec = next((r for r in (self._cache or {}).get(record_type, []) if r.id == str(id)), None)
        if rec is not None and rec.raw.get("link"):
            return rec.raw["link"]
        path = API_PATH.get(record_type, record_type + "/{id}").format(p=self.project_id, id=id,
                                                                      area=self._area_of.get(str(id), "?"))
        return f"{self.env['api']}/{path}"

    # ------------------------------------------------------------------ build
    def _build(self) -> dict[str, list[NormalizedRecord]]:
        s = self._session()
        res = links.Resolver(self.state_for_links)
        pid, cid = self.project_id, self.company_id
        out: dict[str, list[NormalizedRecord]] = {k: [] for k in self.capabilities}

        def rec(kind, rt, raw, number, title, status, ref, explicit, dates=None, fields=None) -> NormalizedRecord:
            r = NormalizedRecord(kind=kind, id=str(raw["id"]), ref=ref or f"procore:{kind}:{raw['id']}", platform=self.name,
                                 number=str(number or raw["id"]), title=title or "", status=status,
                                 element_ids=res.elements(ref, explicit), dates=dates or {}, fields=fields or {}, raw=raw)
            out[rt].append(r)
            return r

        for raw in s.procore_pages(list_submittals, project_id=pid, procore_company_id=cid):
            ref, el = links.parse(raw.get("description"), raw.get("title"))
            st = _status_submittal(raw)
            spec = raw.get("specification_section") or {}
            rec("submittal", SUBMITTALS, raw, raw.get("formatted_number") or raw.get("number"), raw.get("title"), st, ref, el,
                dates={"due": raw.get("due_date"), "issued": raw.get("issue_date"), "received": raw.get("received_date"),
                       "required_on_site": raw.get("required_on_site_date"), "delivered": raw.get("actual_delivery_date")},
                fields={"stage": _stage_submittal(st, raw), "stage_notes": [], "spec_section": spec.get("number") or "",
                        "spec_title": spec.get("description") or "", "package_kind": _package_kind(raw), "level": None,
                        "sequence": None, "revision": raw.get("revision"), "response": None,
                        "ball_in_court": [b.get("name") for b in raw.get("ball_in_court") or [] if isinstance(b, dict)],
                        "activity_refs": [], "vendor_status": (raw.get("status") or {}).get("name")})

        for raw in s.procore_pages(list_rfis, project_id=pid, procore_company_id=cid):
            q = next((x.get("body") for x in raw.get("questions") or [] if isinstance(x, dict)), "")
            ref, el = links.parse(raw.get("reference"), q, raw.get("subject"))
            rec("rfi", RFIS, raw, raw.get("full_number") or raw.get("number"), raw.get("subject"),
                RFI_STATUS.get(raw.get("status") or "", "open"), ref, el,
                dates={"due": raw.get("due_date"), "initiated": raw.get("initiated_at"), "resolved": raw.get("time_resolved")},
                fields={"question": q, "answer": None, "ball_in_court": (raw.get("ball_in_court") or {}).get("name"),
                        "cost_impact": raw.get("cost_impact"), "schedule_impact": raw.get("schedule_impact"),
                        "drawing_number": None, "spec_section": raw.get("specification_section_id"),
                        "vendor_status": raw.get("status")})

        for raw in s.procore_pages(list_change_events, project_id=pid, procore_company_id=cid):
            ext = raw.get("external_data") or {}
            ref, el = links.parse(raw.get("description"), (ext.get("origin_id") or "").replace("calc-graph:", "calc-graph "))
            st = raw.get("status") or {}
            amount = sum(_num(((ci.get("cost_impact") or {}).get("estimate") or {}).get("amount"))
                         for ci in raw.get("change_items") or [] if isinstance(ci, dict))
            rec("change_event", CHANGE_EVENTS, raw, raw.get("number"), raw.get("title"),
                CE_STATUS.get((st.get("mapped_to_status") or st.get("name") or "").lower(), "pending"), ref, el,
                dates={"created": raw.get("created_at")},
                fields={"amount_usd": amount, "reason": (raw.get("change_reason") or {}).get("change_reason"),
                        "line_items": len(raw.get("change_items") or []), "change_order_refs": [], "estimate": True,
                        "scope": raw.get("scope"), "vendor_status": st.get("name")})

        for raw in s.procore_pages(list_change_order_packages, project_id=pid, procore_company_id=cid):
            ref, el = links.parse(raw.get("origin_id"), raw.get("title"))
            rec("change_order", CHANGE_ORDERS, raw, raw.get("number"), raw.get("title"),
                CO_STATUS.get(raw.get("status") or "", "pending"), ref, el,
                dates={"created": raw.get("created_at"), "approved": raw.get("reviewed_at") if raw.get("status") == "approved" else None},
                fields={"amount_usd": _num(raw.get("grand_total")), "schedule_days": None, "change_event_ref": None,
                        "co_type": "change_order_package", "estimate": False, "vendor_status": raw.get("status")})

        for raw in s.procore_pages(list_cost_codes, project_id=pid, procore_company_id=cid):
            out[COST_CODES].append(NormalizedRecord(
                kind="cost_code", id=str(raw["id"]), ref=f"CC-{raw.get('full_code') or raw.get('code')}", platform=self.name,
                number=str(raw.get("full_code") or raw.get("code") or raw["id"]), title=raw.get("name") or "", status="active",
                fields={"code": raw.get("full_code") or raw.get("code"), "division": (raw.get("parent") or {}).get("name")
                        if isinstance(raw.get("parent"), dict) else None}, raw=raw))

        for raw in s.procore_pages(list_tasks, project_id=pid, procore_company_id=cid):
            ref, el = links.parse(raw.get("notes"), raw.get("name"))
            pct = raw.get("percentage") or 0
            rec("schedule_activity", SCHEDULE_ACTIVITIES, raw, raw.get("activity_id") or raw.get("key"), raw.get("name"),
                "complete" if pct >= 100 else ("in_progress" if pct > 0 else "not_started"), ref, el,
                dates={"early_start": raw.get("start_datetime"), "early_finish": raw.get("finish_datetime"),
                       "late_start": None, "late_finish": None, "actual_start": raw.get("actual_start"),
                       "actual_finish": raw.get("actual_finish")},
                fields={"wbs": raw.get("wbs"), "duration_days": raw.get("schedule_duration"), "percent_complete": pct,
                        "total_float_days": None, "float_known": False, "critical": bool(raw.get("critical_path")),
                        "milestone": bool(raw.get("milestone")), "predecessors": [], "package_ref": None})

        for area in s.procore_pages(list_drawing_areas, project_id=pid, procore_company_id=cid):
            for raw in s.procore_pages(list_drawings, drawing_area_id=area["id"], procore_company_id=cid):
                self._area_of[str(raw["id"])] = area["id"]
                cur = raw.get("current_revision") or {}
                out[SHEETS].append(NormalizedRecord(
                    kind="sheet", id=str(raw["id"]), ref=f"SHEET:{raw.get('number')}", platform=self.name,
                    number=raw.get("number") or "", title=raw.get("title") or "", status="active", element_ids=[],
                    dates={"issued": cur.get("updated_at")},
                    fields={"discipline": raw.get("discipline"), "revision": cur.get("revision_number"),
                            "version_set": area.get("name"), "obsolete": raw.get("obsolete")}, raw=raw))

        self.extras["commitments"] = s.procore_pages(list_commitments, project_id=pid, procore_company_id=cid)
        for rt, recs in out.items():
            for r in recs:
                r.links["self"] = r.raw.get("link") or self.deep_link(rt, r.id) if rt != SHEETS else \
                    f"{self.env['api']}/rest/v1.1/drawing_areas/{self._area_of.get(r.id)}/drawings"
        return out

    def describe(self) -> dict:
        d = super().describe()
        d.update(synthetic=False, env=self.env["name"], project_id=self.project_id, company_id=self.company_id,
                 parse_errors=(self.session.parse_errors if self.session else []),
                 extras={k: len(v) for k, v in self.extras.items()})
        return d

