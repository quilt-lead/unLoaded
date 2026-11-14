"""Autodesk Forma (the early-stage site / building design product; Autodesk now calls its API the
"Forma Site Design API") LIVE adapter - READ ONLY.

What is real (read 2026-11-14 on aps.autodesk.com; every path is alpha, the docs are marked BETA):
  GET https://developer.api.autodesk.com/forma/proposal/v1alpha/proposals?authcontext=pro_...&limit<=100
      -> {results: [{urn, metadata, properties{category: "proposal", name}, children[{urn, key, transform, name}]}],
          pagination{limit, nextUrl?}}           (proposal-listproposals-GET)
  GET https://developer.api.autodesk.com/forma/element-service/v1alpha/elements/{urn}?authcontext=pro_...&recursive=true
      -> {element, elements{urn: element}}; may answer 302, which is followed  (element-getelement-GET)
  3-legged APS token, scope data:read; optional X-Ads-Region US | EMEA.
No submittals, RFIs, cost or schedule exist in Forma, so none are served. There is no OpenAPI document for
these endpoints in Autodesk's spec repo, so nothing is generated; the calls are plain and cited here.

Registry links: a Forma element links to registry element ids only by its `properties.name` equalling a
registry id or carrying a calc-graph marker (links.py); everything else is served unlinked.
Config: FORMA_PROJECT_ID (the authcontext, "pro_..."), FORMA_REGION (optional).
"""
from __future__ import annotations

import os

from ..base import ELEMENTS, PROPOSALS, NormalizedRecord, PlatformAdapter
from . import links
from . import secrets as store
from .generated.aps_issues_client import AuthenticatedClient   # any generated APS client works as the httpx holder
from .transport import LiveError, Recorded, Session

BASE = "https://developer.api.autodesk.com"
PROPOSALS_URL = f"{BASE}/forma/proposal/v1alpha/proposals"
ELEMENT_URL = f"{BASE}/forma/element-service/v1alpha/elements/{{urn}}"
MAX_PROPOSALS = 20


class FormaLiveAdapter(PlatformAdapter):
    name = "forma"
    capabilities = frozenset({ELEMENTS, PROPOSALS})
    doc_urls = {PROPOSALS: "https://aps.autodesk.com/en/docs/forma/v1/reference/http-reference/proposal-listproposals-GET",
                ELEMENTS: "https://aps.autodesk.com/en/docs/forma/v1/reference/http-reference/element-getelement-GET"}

    def __init__(self, state=None, recorded: Recorded | None = None, config: dict | None = None):
        super().__init__()
        cfg = config if config is not None else store.app_config("aps")
        self.authcontext = cfg.get("forma_project_id")
        if not self.authcontext:
            raise LiveError("Forma project not configured (FORMA_PROJECT_ID = the pro_... id of a Forma project)")
        self.region = cfg.get("forma_region") or os.environ.get("FORMA_REGION")
        self.registry_ids = set(getattr(state, "elements", {}) or {}) if state is not None else set()
        self.label = f"Autodesk Forma (live: {self.authcontext})"
        self.recorded = recorded
        self.session: Session | None = None

    def _session(self) -> Session:
        if self.session is None:
            self.session = Session("aps", BASE, AuthenticatedClient, recorded=self.recorded)
        return self.session

    def _headers(self) -> dict | None:
        return {"X-Ads-Region": self.region} if self.region else None

    def deep_link(self, record_type: str, id: str) -> str:
        if record_type == PROPOSALS:
            return f"{PROPOSALS_URL}?authcontext={self.authcontext}"
        return ELEMENT_URL.format(urn=id) + f"?authcontext={self.authcontext}"

    def _links_for(self, el: dict) -> tuple[str | None, list[str]]:
        name = ((el.get("properties") or {}).get("name") or "")
        if name in self.registry_ids:
            return name, [name]
        return links.parse(name)

    def _build(self) -> dict[str, list[NormalizedRecord]]:
        s = self._session()
        out: dict[str, list[NormalizedRecord]] = {ELEMENTS: [], PROPOSALS: []}
        props, url, params = [], PROPOSALS_URL, {"authcontext": self.authcontext, "limit": 100}
        while url and len(props) < MAX_PROPOSALS:
            data, _ = s.request("GET", url, params=params, headers=self._headers(), what="forma proposals")
            props += (data or {}).get("results") or []
            url, params = ((data or {}).get("pagination") or {}).get("nextUrl"), None
        seen: set[str] = set()
        for p in props[:MAX_PROPOSALS]:
            linked: set[str] = set()
            data, _ = s.request("GET", ELEMENT_URL.format(urn=p["urn"]),
                                params={"authcontext": self.authcontext, "recursive": "true"},
                                headers=self._headers(), what="forma element")
            for urn, el in ((data or {}).get("elements") or {}).items():
                if urn in seen or urn == p["urn"]:
                    continue
                seen.add(urn)
                ref, ids = self._links_for(el)
                linked |= set(ids)
                pr = el.get("properties") or {}
                out[ELEMENTS].append(NormalizedRecord(
                    kind="element", id=urn, ref=ref or f"forma:{urn}", platform=self.name, number=pr.get("name") or urn,
                    title=f"{pr.get('category') or 'element'} {pr.get('name') or ''}".strip(), status="active",
                    element_ids=ids, links={"self": self.deep_link(ELEMENTS, urn)},
                    fields={"category": pr.get("category"), "representations": sorted((el.get("representations") or {}))},
                    raw=el))
            pp = p.get("properties") or {}
            out[PROPOSALS].append(NormalizedRecord(
                kind="proposal", id=p["urn"], ref=f"forma:{p['urn']}", platform=self.name, number=pp.get("name") or "",
                title=pp.get("name") or "", status="active", element_ids=sorted(linked),
                dates={"created": (p.get("metadata") or {}).get("createdAt")},
                links={"self": self.deep_link(PROPOSALS, p["urn"])}, fields={"root_urn": p["urn"]}, raw=p))
        return out

    def describe(self) -> dict:
        d = super().describe()
        d.update(synthetic=False, authcontext=self.authcontext, api_status="beta (alpha endpoints)")
        return d
