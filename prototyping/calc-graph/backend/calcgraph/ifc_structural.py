"""Write a structural analysis model (IFC4 IfcStructuralAnalysisModel) into an IFC that an
`IfcBuilder` is building, through ifcopenshell.api.structural.

Source: the normalized analysis objects of `calcgraph.analysis.etabs.build_objects` - the same
analytical view of the design the .e2k export and the mock ETABS round trip use, so the IFC
analytical model, the ETABS model and the design cannot drift apart. Mapping:

  ETABS-style object            IFC4
  point (label @ story)         IfcStructuralPointConnection (IfcVertexPoint topology);
                                base restraints -> IfcBoundaryNodeCondition
  frame (one per story seg.)    IfcStructuralCurveMember RIGID_JOINED_MEMBER (IfcEdge topology),
                                section + grade as IfcMaterialProfileSetUsage, end releases
                                (PINNED = M2, M3 free) on IfcRelConnectsStructuralMember,
                                IfcRelAssignsToProduct -> the physical element it idealizes
  load_pattern                  IfcStructuralLoadGroup LOAD_GROUP (holds the actions)
  load_case (Linear Static)     IfcStructuralLoadCase (patterns x factor via
                                IfcRelAssignsToGroupByFactor; Dead self weight coefficient)
  combo                         IfcStructuralLoadGroup LOAD_COMBINATION (cases x factor)
  member line loads (klf)       IfcStructuralCurveAction CONST, IfcStructuralLoadLinearForce (N/m)

Everything is made through ifcopenshell.api except the topology items (IfcVertexPoint / IfcEdge,
which the api's own docs create directly for add_topology_representation) and
IfcRelAssignsToGroupByFactor (no api use case exists for it in 0.9.0).

Not written (on purpose): the Modal case (an analysis type, not a load), lateral load actions
(ETABS-style auto-lateral: the ELF / wind story forces are on the load-group pset, as in the
.e2k, not idealized into nodal loads we would have to invent), analysis results.

Every rooted entity gets a uuid5 GlobalId from a semantic key (element id + story, node key),
so a member or node keeps its GlobalId across revisions and ifcdiff can follow it. Names use the
same keys, never the ETABS labels: an unseeded ETABS label (B12, 37) renumbers when the topology
changes, which would show every member as renamed in a revision diff.
"""
from __future__ import annotations

import math

import ifcopenshell.api.group
import ifcopenshell.api.structural
import numpy as np

from .ifc_common import IfcBuilder, api

FT = 0.3048
KLF = 4448.2216152605 / 0.3048          # 1 kip/ft in N/m

# e2k pattern TYPE -> (IfcActionTypeEnum, IfcActionSourceTypeEnum)
ACTIONS = {"Dead": ("PERMANENT_G", "DEAD_LOAD_G"), "Super Dead": ("PERMANENT_G", "DEAD_LOAD_G"),
           "Live": ("VARIABLE_Q", "LIVE_LOAD_Q"), "Roof Live": ("VARIABLE_Q", "LIVE_LOAD_Q"),
           "Seismic": ("EXTRAORDINARY_A", "EARTHQUAKE_E"), "Wind": ("VARIABLE_Q", "WIND_W")}
COMBO_ACTION = {"gravity": "PERMANENT_G", "seismic": "EXTRAORDINARY_A", "overstrength": "EXTRAORDINARY_A",
                "wind": "VARIABLE_Q"}
DOFS = ("TranslationalStiffnessX", "TranslationalStiffnessY", "TranslationalStiffnessZ",
        "RotationalStiffnessX", "RotationalStiffnessY", "RotationalStiffnessZ")


def _bool_condition(B: IfcBuilder, cond, fixed: list[bool]) -> None:
    api.structural.edit_structural_boundary_condition(
        B.f, condition=cond, attributes={k: {"type": "IfcBoolean", "value": bool(v)} for k, v in zip(DOFS, fixed)})


def add_analysis_model(B: IfcBuilder, objs: list, label_map: dict, physical: dict, profile_of, grade_of,
                       line_loads: dict[str, dict[str, float]], name: str) -> dict:
    """objs / label_map: `etabs.build_objects(exp)`. physical: {element id: IFC element}.
    profile_of(size) -> the IFC profile already used by the physical model; grade_of(size) ->
    material name. line_loads: {element id: {pattern name: w klf, + down}}. Returns counts."""
    f = B.f
    model = B.rooted("IfcStructuralAnalysisModel", "sam", name=name)
    api.structural.edit_structural_analysis_model(f, structural_analysis_model=model, attributes={
        "PredefinedType": "LOADING_3D", "Description": "Analytical model of the design (calc-graph ETABS-style "
                                                       "objects; ETABS did not run)"})
    B.keyed(api.structural.assign_to_building(f, structural_analysis_model=model, building=B.building), "sam:rel:building")
    ref = B.reference_ctx
    by_kind: dict[str, list] = {}
    for o in objs:
        by_kind.setdefault(o.kind, []).append(o)
    key_of_label = {v: k for k, v in label_map["points"].items()}

    # nodes
    nodes: dict[tuple[str, float], tuple] = {}
    n_supports = 0
    for p in by_kind.get("point", []):
        pr = p.props
        nkey = f"{key_of_label[p.label]}@{p.story}"
        key = f"sam:node:{nkey}"
        node = B.rooted("IfcStructuralPointConnection", key, name=nkey)
        node.Description = f"framing: {', '.join(pr['framing'])}"
        vp = f.createIfcVertexPoint(f.createIfcCartesianPoint((pr["x_ft"] * FT, pr["y_ft"] * FT, pr["z_ft"] * FT)))
        api.geometry.assign_representation(f, product=node, representation=api.geometry.add_topology_representation(
            f, context=ref, item=vp))
        if any(pr["restraint"]):
            cond = api.structural.add_structural_boundary_condition(f, name="fixed" if all(pr["restraint"]) else "pinned",
                                                                    connection=node)
            _bool_condition(B, cond, pr["restraint"])
            n_supports += 1
            if p.element_id in physical:
                B.keyed(api.structural.assign_product(f, relating_product=physical[p.element_id], related_object=node),
                        f"{key}:product")
        nodes[(p.label, round(pr["z_ft"], 6))] = (node, vp)

    # members
    members = {}
    n_released = 0
    for fr in by_kind.get("frame", []):
        pr = fr.props
        seg = f"{fr.element_id}@{fr.story}"
        mem = B.rooted("IfcStructuralCurveMember", f"sam:member:{seg}", name=seg, predefined="RIGID_JOINED_MEMBER")
        mem.Description = f"{pr['etabs_type'].lower()} {fr.element_id} ({fr.story})"
        (ni, vi), (nj, vj) = nodes[(pr["point_i"], round(pr["xyz_i"][2], 6))], nodes[(pr["point_j"], round(pr["xyz_j"][2], 6))]
        api.geometry.assign_representation(f, product=mem, representation=api.geometry.add_topology_representation(
            f, context=ref, item=f.createIfcEdge(vi, vj)))
        d = np.array(pr["xyz_j"], float) - np.array(pr["xyz_i"], float)
        d /= np.linalg.norm(d)
        if abs(d[2]) > 0.999:                       # column: local z (section depth) at the ETABS angle
            a = math.radians(pr.get("angle_deg", 0.0))
            axis = (math.cos(a), math.sin(a), 0.0)
        else:                                       # beam / brace: local z = up, normal to the member
            up = np.array([0.0, 0.0, 1.0]) - d * d[2]
            axis = tuple((up / np.linalg.norm(up)).tolist())
        # api.structural.edit_structural_item_axis (0.9.0) fails on a member with no Axis yet
        # (get_total_inverses(None)); a new member's mandatory Axis is set directly
        mem.Axis = f.createIfcDirection(tuple(float(v) for v in axis))
        B.assign_profile_material(mem, profile_of(pr["section"]), grade_of(pr["section"]))
        for end, node in (("i", ni), ("j", nj)):
            rel = B.keyed(api.structural.add_structural_member_connection(
                f, relating_structural_member=mem, related_structural_connection=node), f"sam:member:{seg}:{end}")
            if pr["release"] == "PINNED":
                cond = api.structural.add_structural_boundary_condition(f, name="pinned (M2, M3 released)", connection=rel)
                _bool_condition(B, cond, [True, True, True, True, False, False])
                n_released += 1
        if fr.element_id in physical:
            B.keyed(api.structural.assign_product(f, relating_product=physical[fr.element_id], related_object=mem),
                    f"sam:product:{fr.element_id}")   # one rel per physical element (the api reuses it per segment)
        B.psets(mem, f"sam:member:{seg}", {"CalcGraph_Analytical": {
            "ElementId": fr.element_id, "Story": fr.story, "Section": pr["section"],
            "Release": pr["release"] or "none", "Roles": ",".join(pr.get("roles", [])),
            "SizeSource": pr.get("size_source", "")}})
        members.setdefault(fr.element_id, []).append(mem)
    items = [n for n, _ in nodes.values()] + [m for ms in members.values() for m in ms]
    B.keyed(api.structural.assign_structural_analysis_model(f, products=items, structural_analysis_model=model),
            "sam:rel:items")

    # load groups (patterns) + their actions
    groups, n_actions, loads = {}, 0, {}
    for p in by_kind.get("load_pattern", []):
        at, src = ACTIONS[p.props["type"]]
        g = B.keyed(api.structural.add_structural_load_group(f, name=p.label, action_type=at, action_source=src),
                    f"sam:pattern:{p.label}")
        g.PredefinedType = "LOAD_GROUP"
        g.Description = p.props["description"]
        ps = {"Type": p.props["type"], "SelfWeightMultiplier": p.props["self_weight"], "CalcRecords": ";".join(p.record_ids)}
        ps |= {k: v for k, v in p.props.items() if k not in ("type", "self_weight", "description")}
        B.psets(g, f"sam:pattern:{p.label}", {"CalcGraph_LoadPattern": ps})
        groups[p.label] = g
        acts = []
        for eid in sorted(line_loads):
            w = line_loads[eid].get(p.label, 0.0)
            if not w or eid not in members:
                continue
            fz = round(-w * KLF, 3)
            if fz not in loads:
                load = api.structural.add_structural_load(f, name=f"{-fz / KLF:g} klf", ifc_class="IfcStructuralLoadLinearForce")
                api.structural.edit_structural_load(f, structural_load=load, attributes={"LinearForceZ": fz})
                loads[fz] = load
            for mem in members[eid]:
                act = B.keyed(api.structural.add_structural_activity(
                    f, applied_load=loads[fz], structural_member=mem, ifc_class="IfcStructuralCurveAction",
                    predefined_type="CONST", global_or_local="GLOBAL_COORDS"), f"sam:action:{p.label}:{mem.GlobalId}")
                act.Name = f"{p.label} {eid}"
                act.ProjectedOrTrue = "TRUE_LENGTH"
                B.keyed(act.AssignedToStructuralItem[0], f"sam:action:{p.label}:{mem.GlobalId}:rel")
                acts.append(act)
        if acts:
            B.keyed(api.group.assign_group(f, products=acts, group=g), f"sam:pattern:{p.label}:actions")
            n_actions += len(acts)

    # load cases (patterns x factor) and combinations (cases x factor)
    def by_factor(key: str, group, members_factors: list[tuple[object, float]]):
        for i, (obj, fac) in enumerate(members_factors):
            # no api use case makes IfcRelAssignsToGroupByFactor (0.9.0) - the one entity built directly
            B.keyed(f.create_entity("IfcRelAssignsToGroupByFactor", GlobalId=B.guid(f"{key}:{i}"), RelatedObjects=[obj],
                                    RelatingGroup=group, Factor=float(fac)), f"{key}:{i}")

    cases = {}
    for c in by_kind.get("load_case", []):
        if c.props.get("type") != "Linear Static":
            continue
        pats = [(groups[n], fac) for n, fac in c.props["loads"]]
        at, src = groups[c.props["loads"][0][0]].ActionType, groups[c.props["loads"][0][0]].ActionSource
        case = B.keyed(api.structural.add_structural_load_case(f, name=c.label, action_type=at, action_source=src),
                       f"sam:case:{c.label}")
        sw = sum(fac * next(p.props["self_weight"] for p in by_kind["load_pattern"] if p.label == n) for n, fac in c.props["loads"])
        if sw:
            case.SelfWeightCoefficients = (0.0, 0.0, -float(sw))
        by_factor(f"sam:case:{c.label}:by", case, pats)
        cases[c.label] = case
    combos = []
    for c in by_kind.get("combo", []):
        g = B.keyed(api.structural.add_structural_load_group(f, name=c.label, action_type=COMBO_ACTION[c.props["group"]],
                                                             action_source="NOTDEFINED"), f"sam:combo:{c.label}")
        g.PredefinedType = "LOAD_COMBINATION"
        g.Description = f"{c.props['code']} ({c.props['group']})"
        B.psets(g, f"sam:combo:{c.label}", {"CalcGraph_Combination": {"Group": c.props["group"], "CalcRecords": ";".join(c.record_ids)}})
        by_factor(f"sam:combo:{c.label}:by", g, [(cases[n], fac) for n, fac in c.props["terms"]])
        combos.append(g)
    api.structural.edit_structural_analysis_model(f, structural_analysis_model=model, attributes={
        "LoadedBy": list(groups.values()) + list(cases.values()) + combos})
    return {"nodes": len(nodes), "supports": n_supports, "members": sum(len(v) for v in members.values()),
            "released_ends": n_released, "load_groups": len(groups), "load_cases": len(cases), "combinations": len(combos),
            "actions": n_actions, "distinct_loads": len(loads)}
