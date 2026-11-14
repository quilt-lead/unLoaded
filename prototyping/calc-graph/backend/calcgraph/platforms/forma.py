"""Autodesk Forma adapter (SYNTHETIC, lighter): the design model as Forma elements + one proposal.

Forma is an early-stage design / site tool, not a construction-management system, so this
adapter serves no submittals, RFIs, cost or schedule (capabilities say so). It exposes the
registry elements as Forma elements so a design proposal can be linked to the same ids.

Shape follows the Forma element specification - READ:
  https://aps.autodesk.com/en/docs/forma/v1/working-with-forma/element-system/forma-element-specification
  urn = urn:adsk-forma-elements:{system}:{authcontext}:{id}:{revision}; element = {urn,
  metadata, properties{category, name, virtual, ...}, representations{volumeMesh, footprint,
  ...}, children[{key, urn, transform (16 numbers, column-major 4x4, metres)}]}.
  GET v1alpha/elements/{urn}?recursive -> {element, elements{urn: element}} (from search
  result: https://aps.autodesk.com/en/docs/forma/v1/reference/http-reference/element-getelement-GET).
Structural attributes (size, level, roles) are not part of the spec's core properties; they ride
in a `structural` property object as a project extension. Proposals: no official reference page
was found, so the proposal object ({id, name, rootElementUrn, ...}) is a minimal guess.

Deep links are mock://forma/... (never a real Forma project).
"""
from __future__ import annotations

from .base import ELEMENTS, PROPOSALS, NormalizedRecord, PlatformAdapter
from .synthetic import ConstructionState, _uuid

FT = 0.3048
AUTH = "pro_" + _uuid("forma-project")[:10]
SYSTEM = "integrate"


def _urn(eid: str, rev: str = "1") -> str:
    return f"urn:adsk-forma-elements:{SYSTEM}:{AUTH}:{_uuid('forma-el', eid)[:18]}:{rev}"


def _transform(x_ft: float, y_ft: float, z_ft: float) -> list[float]:
    return [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, round(x_ft * FT, 4), round(y_ft * FT, 4), round(z_ft * FT, 4), 1]


class FormaAdapter(PlatformAdapter):
    name = "forma"
    label = "Autodesk Forma (synthetic)"
    capabilities = frozenset({ELEMENTS, PROPOSALS})
    doc_urls = {
        ELEMENTS: "https://aps.autodesk.com/en/docs/forma/v1/working-with-forma/element-system/forma-element-specification",
        PROPOSALS: "(no public reference found; minimal guess)",
    }

    def __init__(self, state: ConstructionState):
        super().__init__()
        self.state = state
        self.project_id = AUTH

    def deep_link(self, record_type: str, id: str) -> str:
        if record_type == PROPOSALS:
            return f"mock://forma/projects/{self.project_id}/proposals/{id}"
        return f"mock://forma/projects/{self.project_id}/elements/{id}"

    def _build(self) -> dict[str, list[NormalizedRecord]]:
        els = self.state.elements
        physical = {"column", "beam", "girder", "brace", "footing", "pier", "grade_beam", "deck", "connection"}
        out: dict[str, list[NormalizedRecord]] = {ELEMENTS: [], PROPOSALS: []}
        level_children: dict[str, list[dict]] = {}
        for eid, e in els.items():
            if e["type"] not in physical:
                continue
            urn = _urn(eid)
            if "p1" in e:
                x, y, z = e["p1"]
            else:
                x, y, z = e.get("x", 0.0), e.get("y", 0.0), e.get("z", e.get("z0", e.get("z_top", 0.0)))
            lvl = e.get("level") or ("L1" if e["type"] in ("footing", "pier", "grade_beam", "column") else "L1")
            if e["type"] == "connection" and e.get("member") in els:
                lvl = els[e["member"]].get("level", "L1")
            raw = {
                "urn": urn,
                "metadata": {"createdBy": "synthetic-generator", "license": "internal-prototype"},
                "properties": {"category": "structural_" + e["type"], "name": eid, "virtual": e["type"] == "connection",
                               "structural": {k: e[k] for k in ("size", "conn_type", "level", "roles", "frame", "frames",
                                                                "span_ft", "B_ft", "h_in", "grid") if k in e}},
                "representations": ({"volumeMesh": {"type": "linked", "blobId": _uuid("forma-mesh", eid)}}
                                    if e["type"] != "connection" else {}),
                "children": [],
            }
            level_children.setdefault(lvl, []).append({"key": eid, "urn": urn, "transform": _transform(x, y, z)})
            out[ELEMENTS].append(NormalizedRecord(
                kind="element", id=urn, ref=eid, platform=self.name, number=eid, title=f"{e['type']} {eid}",
                status="active", element_ids=[eid], links={"self": self.deep_link(ELEMENTS, urn)},
                fields={"category": raw["properties"]["category"], "level": lvl, "size": e.get("size") or e.get("conn_type")},
                raw=raw))
        # level groups + building root
        level_urns = {}
        for lvl, kids in sorted(level_children.items()):
            urn = _urn(f"LEVEL-GROUP:{lvl}")
            level_urns[lvl] = urn
            raw = {"urn": urn, "metadata": {}, "properties": {"category": "level_group", "name": lvl, "virtual": True},
                   "representations": {}, "children": kids}
            out[ELEMENTS].append(NormalizedRecord(
                kind="element", id=urn, ref=f"LEVEL:{lvl}", platform=self.name, number=f"LEVEL:{lvl}",
                title=f"Level group {lvl}", status="active", element_ids=[k["key"] for k in kids],
                links={"self": self.deep_link(ELEMENTS, urn)}, fields={"category": "level_group"}, raw=raw))
        root_urn = _urn("BUILDING")
        root = {"urn": root_urn, "metadata": {}, "properties": {"category": "building", "name": self.state.project["name"],
                                                                  "virtual": False},
                "representations": {"footprint": {"type": "linked", "blobId": _uuid("forma-fp", "bldg")}},
                "children": [{"key": lvl, "urn": u, "transform": _transform(0, 0, 0)} for lvl, u in level_urns.items()]}
        out[ELEMENTS].append(NormalizedRecord(
            kind="element", id=root_urn, ref="BUILDING", platform=self.name, number="BUILDING", title=self.state.project["name"],
            status="active", element_ids=[], links={"self": self.deep_link(ELEMENTS, root_urn)},
            fields={"category": "building"}, raw=root))
        pid = _uuid("forma-proposal", "base")
        praw = {"id": pid, "name": "Base design (structural scheme v2)", "rootElementUrn": root_urn,
                "createdAt": f"{self.state.project['start']}T12:00:00Z", "status": "active"}
        out[PROPOSALS].append(NormalizedRecord(
            kind="proposal", id=pid, ref="PROPOSAL-BASE", platform=self.name, number="P-1", title=praw["name"],
            status="active", element_ids=sorted(e for e in els if els[e]["type"] in physical),
            links={"self": self.deep_link(PROPOSALS, pid)}, fields={"root_urn": root_urn}, raw=praw))
        return out
