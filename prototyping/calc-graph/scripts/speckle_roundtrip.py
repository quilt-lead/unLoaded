"""Round trip the synthetic v2 building through Speckle and diff what comes back.

Four subcommands. `build` and `diff` run on the Mac (repo env); `send` and `receive` run
wherever specklepy can read a signed-in local Speckle account (the connectors' Accounts db),
and need nothing from this repo but this file and the payload JSON (`receive` of an IFC import
also needs pyarrow):

    uv run python scripts/speckle_roundtrip.py build --out sent.json
    python speckle_roundtrip.py send --payload sent.json --ifc model.ifc --out send.json \
        [--project-id P | --project "calc-graph prototype - Harbor View (synthetic)"]
    python speckle_roundtrip.py receive --project-id P --model "calc-graph harbor-view/registry-objects" \
        --out recv.json
    uv run python scripts/speckle_roundtrip.py diff --sent sent.json --recv recv.json

`send` writes two models (names nest on "/"): `.../registry-objects` holds one
`Objects.Data.DataObject` per physical structural member (column, beam, girder, brace, pier,
grade beam, footing), one Collection per category. `applicationId` is the IFC GlobalId;
`properties` carry the registry id, category, section, material, level name, the analytical end
points (ft) and the IFC GlobalId; `displayValue` is one box mesh per member (nominal section box,
display only - the section of record is the `section` property). `.../ifc-import` gets the IFC
through the server's file ingestion. app.speckle.systems only creates projects inside a
workspace and a free workspace holds one project, hence `--project-id` to reuse one.

`receive` reads the newest version, or `--version` (pass it right after a send or publish: the
version list lags a new version by a few seconds): an object-tree version through
`operations.receive`, a v4 artefact bundle (what the IFC importer writes) through
`specklepy.bundle`, because `operations.receive` projects bundles to Base objects and drops the
properties of instanced objects. It writes every object with properties or an applicationId,
flattened, plus the bounding box of its display meshes in feet. `diff` matches each sent member
(applicationId = GlobalId, else name = registry id, else either id in any property) and checks
registry id, GlobalId, section, material, level and coordinates. The token is never printed or
written.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from collections import Counter, defaultdict

PROJECT_NAME = "calc-graph prototype - Harbor View (synthetic)"
MODEL_PREFIX = "calc-graph harbor-view/"   # Speckle nests models on "/"
REGISTRY_MODEL = MODEL_PREFIX + "registry-objects"
IFC_MODEL = MODEL_PREFIX + "ifc-import"
MEMBER_TYPES = ("column", "beam", "girder", "brace", "pier", "grade_beam", "footing")
FT_PER = {"ft": 1.0, "feet": 1.0, "in": 1 / 12, "inches": 1 / 12, "m": 1 / 0.3048, "meters": 1 / 0.3048,
          "mm": 1 / 304.8, "millimeters": 1 / 304.8, "cm": 1 / 30.48, "centimeters": 1 / 30.48}
COORD_TOL_FT = 0.01


# --------------------------------------------------------------------------- build (Mac)

def _level_for(z: float, levels: list[tuple[str, float]]) -> str:
    below = [name for name, elev in levels if elev <= z + 1e-6]
    return below[-1] if below else "Foundation"


def build(out: str) -> None:
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    sys.path[:0] = [os.path.join(root, "backend")]
    import ifcopenshell
    import ifcopenshell.util.element as ifc_el

    from calcgraph.aisc import IN, hss_dims_m, w_dims_m

    data_dir = os.path.join(root, "data", "synthetic_v2")
    design = json.load(open(os.path.join(data_dir, "design.json")))
    ifc = ifcopenshell.open(os.path.join(data_dir, "model.ifc"))
    import ifcopenshell.geom
    import numpy as np

    grade_by_gid = {}
    for prod in ifc.by_type("IfcProduct"):
        grade_by_gid[prod.GlobalId] = ifc_el.get_psets(prod).get("Structural", {}).get("Grade")
    # world-space bounding box of each IFC element's body (ifcopenshell, metres -> ft): the baseline for
    # judging coordinates after Speckle's IFC import or a Revit trip, whose geometry is the physical body
    settings = ifcopenshell.geom.settings()
    settings.set("use-world-coords", True)
    ifc_bbox = {}
    it = ifcopenshell.geom.iterator(settings, ifc)
    if it.initialize():
        while True:
            shape = it.get()
            v = np.array(shape.geometry.verts).reshape(-1, 3) / 0.3048
            ifc_bbox[shape.guid] = [v.min(0).round(5).tolist(), v.max(0).round(5).tolist()]
            if not it.next():
                break
    levels = sorted(((e["id"].split(":", 1)[1], e["elev_ft"]) for e in design["elements"] if e["type"] == "level"),
                    key=lambda t: t[1])
    level_names = {e["id"].split(":", 1)[1]: e["name"] for e in design["elements"] if e["type"] == "level"}
    level_names["Foundation"] = "Foundation"
    m_to_ft = 1 / 0.3048

    def steel_box(size: str) -> tuple[float, float, str]:
        w = w_dims_m(size)
        if w:
            return w["bf"] * m_to_ft, w["d"] * m_to_ft, "AISC table d x bf"
        h = hss_dims_m(size)
        if h:
            return h["b"] * m_to_ft, h["h"] * m_to_ft, "HSS designation b x h"
        nominal_d = float(size[1:].split("X")[0]) * IN * m_to_ft     # W21X48 -> 21 in
        return nominal_d / 2, nominal_d, "nominal depth from designation, bf = d/2 (display only)"

    members = []
    for e in design["elements"]:
        t = e["type"]
        if t not in MEMBER_TYPES:
            continue
        rec = {"id": e["id"], "category": t, "global_id": e["global_id"], "material": grade_by_gid.get(e["global_id"]),
               "ifc_bbox_ft": ifc_bbox.get(e["global_id"])}
        if t in ("beam", "girder", "brace"):
            p1, p2 = e["p1"], e["p2"]
            w, d, how = steel_box(e["size"])
            rec.update(section=e["size"], level=e["level"], p1=p1, p2=p2, box_w_ft=w, box_d_ft=d, box_source=how)
        elif t == "column":
            p1, p2 = [e["x"], e["y"], e["z0"]], [e["x"], e["y"], e["z1"]]
            w, d, how = steel_box(e["size"])
            # base level: the level nearest the column's base (bases sit just below the slab)
            base = min(levels, key=lambda lv: abs(lv[1] - e["z0"]))[0]
            rec.update(section=e["size"], level=base, p1=p1, p2=p2, box_w_ft=w, box_d_ft=d,
                       box_source=how, grid=e["grid"])
        elif t == "pier":
            p1, p2 = [e["x"], e["y"], e["z0"]], [e["x"], e["y"], e["z1"]]
            b = e["b_in"] / 12
            rec.update(section=f'{e["b_in"]:g}x{e["b_in"]:g}', type_mark=e["pier_type"], level="Foundation", p1=p1, p2=p2,
                       box_w_ft=b, box_d_ft=b, box_source="pier b x b")
        elif t == "grade_beam":
            rec.update(section=f'{e["b_in"]:g}x{e["h_in"]:g}', level="Foundation", p1=e["p1"], p2=e["p2"],
                       box_w_ft=e["b_in"] / 12, box_d_ft=e["h_in"] / 12, box_source="grade beam b x h")
        elif t == "footing":
            h = e["h_in"] / 12
            # analytical point = centre of the footing top; the box hangs below it
            rec.update(section=e["mark"], size=f'{e["B_ft"]:g} x {e["B_ft"]:g} ft x {e["h_in"]:g} in', level="Foundation",
                       p1=[e["x"], e["y"], e["z_top"]], p2=None, box_w_ft=e["B_ft"], box_d_ft=h,
                       box_source="footing B x B x h")
        rec["level_name"] = level_names[rec["level"]]
        members.append(rec)
    missing = [m["id"] for m in members if m["ifc_bbox_ft"] is None]
    if missing:
        raise SystemExit(f"no IFC body for {missing[:5]}")
    payload = {"source": "data/synthetic_v2/design.json + model.ifc (Structural.Grade)", "units": "ft",
               "levels": levels, "members": members}
    json.dump(payload, open(out, "w"), indent=1)
    print(f"built {len(members)} members: {dict(Counter(m['category'] for m in members))} -> {out}")


# --------------------------------------------------------------------------- geometry helpers

def _box_mesh_vertices(rec: dict) -> list[float]:
    """8 corners (flat xyz list, ft) of the member's display box."""
    w, d = rec["box_w_ft"], rec["box_d_ft"]
    if rec["p2"] is None:                       # footing: B x B plan, depth d below the top point
        x, y, z = rec["p1"]
        corners = [(x + sx * w / 2, y + sy * w / 2, z - dz) for dz in (d, 0.0) for sx, sy in
                   ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        return [c for pt in corners for c in pt]
    p1, p2 = rec["p1"], rec["p2"]
    t = [b - a for a, b in zip(p1, p2)]
    n = math.sqrt(sum(c * c for c in t))
    t = [c / n for c in t]
    ref = [0.0, 0.0, 1.0] if abs(t[2]) < 0.99 else [1.0, 0.0, 0.0]
    u = [t[1] * ref[2] - t[2] * ref[1], t[2] * ref[0] - t[0] * ref[2], t[0] * ref[1] - t[1] * ref[0]]
    un = math.sqrt(sum(c * c for c in u))
    u = [c / un for c in u]                     # horizontal, across the member
    v = [t[1] * u[2] - t[2] * u[1], t[2] * u[0] - t[0] * u[2], t[0] * u[1] - t[1] * u[0]]   # "up" in section
    if v[2] < 0:                                # t x u points down for some directions: keep v up
        v = [-c for c in v]
    # beams hang below their top-of-steel line; vertical members are centred on the line
    v_lo, v_hi = ((-d, 0.0) if abs(t[2]) < 0.99 and rec["category"] in ("beam", "girder", "grade_beam")
                  else (-d / 2, d / 2))
    corners = []
    for p in (p1, p2):
        for su, sv in ((-w / 2, v_lo), (w / 2, v_lo), (w / 2, v_hi), (-w / 2, v_hi)):
            corners.append([p[i] + su * u[i] + sv * v[i] for i in range(3)])
    return [c for pt in corners for c in pt]


BOX_FACES = [4, 0, 1, 2, 3, 4, 7, 6, 5, 4, 4, 0, 4, 5, 1, 4, 1, 5, 6, 2, 4, 2, 6, 7, 3, 4, 3, 7, 4, 0]


# --------------------------------------------------------------------------- Speckle client (desk)

def _client():
    import warnings
    warnings.simplefilter("ignore")
    from specklepy.api.client import SpeckleClient
    from specklepy.api.credentials import get_local_accounts
    accts = get_local_accounts()
    if not accts:
        raise SystemExit("no local Speckle account (sign in with a connector first)")
    acct = next((a for a in accts if a.isDefault), accts[0])
    client = SpeckleClient(host=acct.serverInfo.url)
    client.authenticate_with_account(acct)
    print(f"speckle: {acct.serverInfo.url} as {acct.userInfo.email}")
    return client, acct


def _project(client, name: str) -> str:
    from specklepy.api.enums import ProjectVisibility
    from specklepy.api.inputs.project_inputs import WorkspaceProjectCreateInput
    for p in client.active_user.get_projects(limit=100).items:
        if p.name == name:
            print(f"project reused: {p.id}")
            return p.id
    # app.speckle.systems refuses projects outside a workspace: use the account's (only) workspace
    workspaces = client.active_user.get_workspaces().items
    if len(workspaces) != 1:
        raise SystemExit(f"expected one workspace, found {[w.name for w in workspaces]}: pick one explicitly")
    p = client.project.create_in_workspace(WorkspaceProjectCreateInput(
        name=name, description=("Synthetic test building from calc-graph (no real project data). Round-trip test "
                                "of registry ids through Speckle."),
        visibility=ProjectVisibility.PRIVATE, workspaceId=workspaces[0].id))
    print(f"project created: {p.id} in workspace {workspaces[0].name}")
    return p.id


def _find_model(client, project_id: str, name: str) -> str | None:
    from specklepy.api.inputs.project_inputs import ProjectModelsFilter
    found = client.model.get_models(project_id, models_filter=ProjectModelsFilter(search=name.split("/")[-1])).items
    return next((m.id for m in found if m.name.lower() == name.lower() or m.id == name), None)


def _model(client, project_id: str, name: str) -> str:
    from specklepy.api.inputs.model_inputs import CreateModelInput
    found = _find_model(client, project_id, name)
    if found:
        return found
    return client.model.create(CreateModelInput(name=name, description=None, project_id=project_id)).id


def send(payload_path: str, ifc_path: str | None, project: str, out: str, skip_ifc: bool,
         project_id: str | None = None, skip_registry: bool = False) -> None:
    from specklepy.api import operations
    from specklepy.api.inputs.version_inputs import CreateVersionInput
    from specklepy.objects.data_objects import DataObject
    from specklepy.objects.geometry import Mesh
    from specklepy.objects.models.collections.collection import Collection
    from specklepy.transports.server import ServerTransport

    payload = json.load(open(payload_path))
    client, acct = _client()
    project_id = project_id or _project(client, project)
    result = {"server": acct.serverInfo.url, "project_id": project_id,
              "project_url": f"{acct.serverInfo.url}/projects/{project_id}"}

    if not skip_registry:
        by_cat = defaultdict(list)
        for rec in payload["members"]:
            props = {"registry_id": rec["id"], "category": rec["category"], "section": rec["section"],
                     "material": rec["material"], "level": rec["level_name"], "ifc_global_id": rec["global_id"],
                     "start_ft": rec["p1"], "end_ft": rec["p2"], "display_box": rec["box_source"]}
            for extra in ("grid", "type_mark", "size"):
                if rec.get(extra):
                    props[extra] = rec[extra]
            mesh = Mesh(vertices=_box_mesh_vertices(rec), faces=list(BOX_FACES), units="ft")
            obj = DataObject(name=rec["id"], properties=props, displayValue=[mesh])
            obj.applicationId = rec["global_id"]
            obj.units = "ft"
            by_cat[rec["category"]].append(obj)
        root = Collection(name="Harbor View (synthetic) - calc-graph registry",
                          elements=[Collection(name=cat, elements=objs) for cat, objs in by_cat.items()])
        root.units = "ft"
        t0 = time.time()
        obj_id = operations.send(root, [ServerTransport(stream_id=project_id, client=client)])
        model_id = _model(client, project_id, REGISTRY_MODEL)
        ver = client.version.create(CreateVersionInput(
            object_id=obj_id, model_id=model_id, project_id=project_id,
            message=f"{len(payload['members'])} members from calc-graph registry (speckle_roundtrip.py)",
            source_application="calc-graph", total_children_count=None, parents=None))
        result["registry"] = {"model_id": model_id, "version_id": ver.id, "root_object": obj_id,
                              "sent": len(payload["members"]), "seconds": round(time.time() - t0, 1),
                              "url": f"{acct.serverInfo.url}/projects/{project_id}/models/{model_id}"}
        print(f"registry model sent: {result['registry']}")

    if ifc_path and not skip_ifc:
        from pathlib import Path

        from specklepy.api.inputs.file_import_inputs import GenerateFileUploadUrlInput, StartFileImportInput
        model_id = _model(client, project_id, IFC_MODEL)
        up = client.file_import.generate_upload_url(GenerateFileUploadUrlInput(project_id=project_id,
                                                                               file_name=os.path.basename(ifc_path)))
        etag = client.file_import.upload_file(Path(ifc_path), up.url).etag
        ing = client.file_import.start_file_ingestion(StartFileImportInput(project_id=project_id, model_id=model_id,
                                                                           file_id=up.file_id, etag=etag))
        print(f"ifc ingestion started: {ing.id} status {ing.status_data.status}")
        version_id, status, msg = None, str(ing.status_data.status), None
        for _ in range(90):                     # server-side conversion; up to 15 min
            time.sleep(10)
            vers = client.version.get_versions(model_id, project_id, limit=1).items
            if vers:
                version_id = vers[0].id
                break
            ing_now = getattr(client, "model_ingestion", None)
            if ing_now is not None and hasattr(ing_now, "get"):
                try:
                    cur = ing_now.get(ing.id, project_id)
                    status, msg = str(cur.status_data.status), cur.status_data.progress_message
                    print(f"  ingestion: {status} {msg or ''}")
                    if "fail" in status.lower() or "cancel" in status.lower():
                        break
                except Exception as exc:  # noqa: BLE001 - status is best effort, the version is the proof
                    print(f"  (ingestion status unavailable: {type(exc).__name__})")
        result["ifc"] = {"model_id": model_id, "ingestion_id": ing.id, "version_id": version_id,
                         "last_status": status, "last_message": msg,
                         "url": f"{acct.serverInfo.url}/projects/{project_id}/models/{model_id}"}
        print(f"ifc model: {result['ifc']}")
    json.dump(result, open(out, "w"), indent=1)
    print(f"-> {out}")


# --------------------------------------------------------------------------- receive (desk)

def _members(base) -> list[str]:
    names = list(base.get_member_names())
    return names


def _flatten(v, prefix="", out=None, depth=0):
    out = {} if out is None else out
    if depth > 8:
        return out
    if isinstance(v, dict):
        for k, x in v.items():
            _flatten(x, f"{prefix}.{k}" if prefix else str(k), out, depth + 1)
    elif isinstance(v, list) and v and all(isinstance(x, (int, float, str, bool)) or x is None for x in v):
        out[prefix] = v
    elif isinstance(v, list):
        for i, x in enumerate(v[:20]):
            _flatten(x, f"{prefix}[{i}]", out, depth + 1)
    elif isinstance(v, (int, float, str, bool)) or v is None:
        out[prefix] = v
    else:
        from specklepy.objects.base import Base
        if isinstance(v, Base):
            for k in _members(v):
                if k in ("displayValue", "@displayValue", "elements", "@elements"):
                    continue
                _flatten(getattr(v, k, None), f"{prefix}.{k}" if prefix else k, out, depth + 1)
    return out


def _mesh_bbox_ft(objs) -> list | None:
    from specklepy.objects.base import Base
    lo, hi = [math.inf] * 3, [-math.inf] * 3
    stack = list(objs if isinstance(objs, list) else [objs])
    seen = 0
    while stack:
        g = stack.pop()
        if isinstance(g, list):
            stack.extend(g)
            continue
        if not isinstance(g, Base):
            continue
        verts = getattr(g, "vertices", None)
        if isinstance(verts, list) and len(verts) >= 3:
            f = FT_PER.get(str(getattr(g, "units", "ft") or "ft").lower(), 1.0)
            for i in range(0, len(verts) - 2, 3):
                for k in range(3):
                    c = verts[i + k] * f
                    lo[k], hi[k] = min(lo[k], c), max(hi[k], c)
            seen += 1
        for k in ("displayValue", "@displayValue", "geometry", "@geometry"):
            sub = getattr(g, k, None)
            if sub is not None and sub is not g:
                stack.append(sub)
    return [lo, hi] if seen else None


def _apply(t: list[float] | None, x: float, y: float, z: float) -> tuple[float, float, float]:
    if not t:
        return x, y, z
    return (t[0] * x + t[1] * y + t[2] * z + t[3], t[4] * x + t[5] * y + t[6] * z + t[7],
            t[8] * x + t[9] * y + t[10] * z + t[11])


def _receive_bundle(acct, project_id: str, model_id: str, version_id: str) -> list[dict]:
    from specklepy.bundle.receive import receive as bundle_receive
    model = bundle_receive(acct, project_id, model_id, version_id, include_geometry=True, mark_received=False)
    default_f = FT_PER.get(str(model.units or "m").lower(), 1.0)
    out = []
    for o in model.objects:
        flat = _flatten(o.type_properties.to_nested(), "type")
        flat.update(_flatten(o.properties.to_nested()))
        flat["name"] = o.name
        lvl = o.level
        flat["level"] = lvl.name if lvl is not None else None
        flat["collection_path"] = " / ".join(o.collection_path or [])
        lo, hi, n = [math.inf] * 3, [-math.inf] * 3, 0
        for g in o.geometries:
            if not g.is_sgeo:
                continue
            mesh = g.decode_mesh()
            f = FT_PER.get(str(mesh.units or "").lower(), default_f)
            v = mesh.vertices
            for i in range(0, len(v) - 2, 3):
                # placement transforms are in model units; scale after placing
                p = _apply(g.transform, v[i], v[i + 1], v[i + 2])
                for k in range(3):
                    lo[k], hi[k] = min(lo[k], p[k] * f), max(hi[k], p[k] * f)
            n += 1
        out.append({"speckle_type": "bundle.object", "name": o.name, "applicationId": o.application_id,
                    "path": list(o.collection_path or []), "units": model.units, "category": None, "flat": flat,
                    "bbox_ft": [lo, hi] if n else None})
    model.close()
    return out


def receive(project_id: str, model: str, version: str | None, out: str) -> None:
    from specklepy.api import operations
    from specklepy.objects.base import Base
    from specklepy.transports.server import ServerTransport

    client, acct = _client()
    model_id = _find_model(client, project_id, model) or model
    vers = client.version.get_versions(model_id, project_id, limit=25).items
    vers.sort(key=lambda v: v.created_at, reverse=True)       # newest first, whatever order the API used
    ver = next((v for v in vers if v.id == version), None) if version else vers[0]
    if ver is None:
        raise SystemExit(f"version {version} not found in model {model}")
    t0 = time.time()
    if str(ver.referenced_object).startswith("bundle."):
        # v4 artefact bundle (the server's IFC importer writes these). operations.receive projects it to
        # Base objects but drops the properties of instanced objects, so read the bundle model directly.
        objects = _receive_bundle(acct, project_id, model_id, ver.id)
        dump = {"project_id": project_id, "model_id": model_id, "version_id": ver.id, "format": "bundle v4",
                "source_application": getattr(ver, "source_application", None),
                "message": ver.message, "created_at": str(getattr(ver, "created_at", "")),
                "receive_seconds": round(time.time() - t0, 1),
                "speckle_types": dict(Counter(o["speckle_type"] for o in objects)), "objects": objects}
        json.dump(dump, open(out, "w"), indent=1, default=str)
        print(f"received bundle version {ver.id} ({dump['source_application']}): {len(objects)} objects -> {out}")
        return
    root = operations.receive(ver.referenced_object, ServerTransport(stream_id=project_id, client=client))
    objects, types = [], Counter()

    def walk(b, path):
        if isinstance(b, list):
            for x in b:
                walk(x, path)
            return
        if not isinstance(b, Base):
            return
        st = b.speckle_type
        types[st] += 1
        if st.startswith("Objects.Geometry") or "Proxies" in st or st.endswith("Proxy"):
            return
        names = _members(b)
        is_coll = "Collection" in st
        props = getattr(b, "properties", None)
        if not is_coll and (props is not None or b.applicationId):
            disp = getattr(b, "displayValue", None) or getattr(b, "@displayValue", None)
            objects.append({"speckle_type": st, "name": getattr(b, "name", None), "applicationId": b.applicationId,
                            "path": path, "units": getattr(b, "units", None),
                            "category": getattr(b, "category", None),
                            "flat": _flatten({k: getattr(b, k, None) for k in names
                                              if k not in ("displayValue", "@displayValue", "elements", "@elements")}),
                            "bbox_ft": _mesh_bbox_ft(disp) if disp else None})
        for k in names:
            if k in ("displayValue", "@displayValue"):
                continue
            v = getattr(b, k, None)
            if isinstance(v, (Base, list)):
                walk(v, path + [str(getattr(b, "name", "") or st)] if is_coll else path)

    walk(root, [])
    dump = {"project_id": project_id, "model_id": model_id, "version_id": ver.id,
            "source_application": getattr(ver, "source_application", None) or getattr(ver, "sourceApplication", None),
            "message": ver.message, "created_at": str(getattr(ver, "created_at", None) or getattr(ver, "createdAt", "")),
            "receive_seconds": round(time.time() - t0, 1), "speckle_types": dict(types), "objects": objects}
    json.dump(dump, open(out, "w"), indent=1, default=str)
    print(f"received version {ver.id} ({dump['source_application']}): {len(objects)} objects, "
          f"types {dict(types.most_common(12))} -> {out}")


# --------------------------------------------------------------------------- diff (Mac)

def _bbox_err(got, exp) -> float:
    return max(max(abs(a - b) for a, b in zip(got[0], exp[0])), max(abs(a - b) for a, b in zip(got[1], exp[1])))


CHECKS = ("registry_id", "global_id", "section", "material", "level")


def diff(sent_path: str, recv_path: str, label: str) -> dict:
    """Match every sent member in a receive dump and check what survived.

    Matching: candidates are objects carrying the registry id or the IFC GlobalId anywhere (applicationId
    or any property value); the best is the one whose applicationId is the GlobalId, then whose name is
    the registry id (a connection plate's properties can name the beam it belongs to, so "any property"
    alone is not identity). Coordinates: `start_ft`/`end_ft` if they survived (exact), and the display
    bounding box against both the registry display box and the IFC body's box (ifcopenshell).
    """
    sent = json.load(open(sent_path))["members"]
    recv = json.load(open(recv_path))
    objs = recv["objects"]
    ids = {m["id"] for m in sent}
    gids = {m["global_id"]: m["id"] for m in sent}
    cands = defaultdict(set)
    for i, o in enumerate(objs):
        vals = {v for v in o["flat"].values() if isinstance(v, str)} | {o.get("applicationId"), o.get("name")}
        for v in vals & ids:
            cands[v].add(i)
        for v in vals & set(gids):
            cands[gids[v]].add(i)

    def score(m, o):
        return (2 if o.get("applicationId") == m["global_id"] else 0) + (1 if o.get("name") == m["id"] else 0)

    rows, lost, used = [], [], set()
    for m in sent:
        hits = sorted(cands.get(m["id"], ()), key=lambda i: -score(m, objs[i]))
        if not hits:
            lost.append(m)
            rows.append({"id": m["id"], "category": m["category"], "matched": None})
            continue
        best = hits[0]
        used.add(best)
        o = objs[best]
        strong = [i for i in hits if score(m, objs[i]) > 0]
        flat_vals = [str(v) for v in o["flat"].values() if v is not None] + [str(o.get("name"))]
        squash = {"".join(v.upper().split()) for v in flat_vals}
        r = {"id": m["id"], "category": m["category"], "speckle_type": o["speckle_type"],
             "matched": "applicationId=GlobalId" if o.get("applicationId") == m["global_id"]
             else "name=registry id" if o.get("name") == m["id"] else "GlobalId in a property"
             if m["global_id"] in flat_vals else "registry id in a property",
             "duplicates": max(0, len(strong) - 1),
             "registry_id": m["id"] in flat_vals,
             # Revit names a received DirectShape "<Category> - <source name>": the id survives only there
             "id_in_name_only": m["id"] not in flat_vals and str(o.get("name") or "").endswith(" - " + m["id"]),
             "global_id": m["global_id"] in flat_vals or o.get("applicationId") == m["global_id"],
             "section": "".join(m["section"].upper().split()) in squash,
             "material": None if m["material"] is None else any(m["material"].upper() in v.upper() for v in flat_vals),
             "level": any(v == m["level_name"] for v in flat_vals)}
        start = next((v for k, v in o["flat"].items() if k.endswith("start_ft") and isinstance(v, list)), None)
        end = next((v for k, v in o["flat"].items() if k.endswith("end_ft") and isinstance(v, list)), None)
        r["line_err_ft"] = None
        if start is not None:
            err = max(abs(a - b) for a, b in zip(start, m["p1"]))
            if m["p2"] is not None and end is not None:
                err = max(err, max(abs(a - b) for a, b in zip(end, m["p2"])))
            r["line_err_ft"] = round(err, 6)
        r["bbox_vs_registry_box_ft"] = r["bbox_vs_ifc_body_ft"] = None
        if o.get("bbox_ft"):
            v = _box_mesh_vertices(m)
            reg_box = [[min(v[k::3]) for k in range(3)], [max(v[k::3]) for k in range(3)]]
            r["bbox_vs_registry_box_ft"] = round(_bbox_err(o["bbox_ft"], reg_box), 4)
            if m.get("ifc_bbox_ft"):
                r["bbox_vs_ifc_body_ft"] = round(_bbox_err(o["bbox_ft"], m["ifc_bbox_ft"]), 4)
        rows.append(r)

    def best_err(r):
        errs = [e for e in (r.get("line_err_ft"), r.get("bbox_vs_registry_box_ft"), r.get("bbox_vs_ifc_body_ft"))
                if e is not None]
        return min(errs) if errs else None

    table = []
    for c in [c for c in MEMBER_TYPES if any(m["category"] == c for m in sent)]:
        cr = [r for r in rows if r["category"] == c]
        got = [r for r in cr if r["matched"]]
        t = {"category": c, "sent": len(cr), "matched": len(got)}
        for k in CHECKS:
            app = [r for r in got if r[k] is not None]
            t[k] = f"{sum(bool(r[k]) for r in app)}/{len(app)}" if len(app) != len(got) else sum(bool(r[k]) for r in got)
        t["id_in_name_only"] = sum(bool(r["id_in_name_only"]) for r in got)
        t["coord_ok"] = sum(1 for r in got if best_err(r) is not None and best_err(r) <= COORD_TOL_FT)

        def mx(key, rows=got):
            vals = [r[key] for r in rows if r.get(key) is not None]
            return max(vals) if vals else None
        t["max_line_err_ft"] = mx("line_err_ft")
        t["max_bbox_vs_registry_ft"] = mx("bbox_vs_registry_box_ft")
        t["max_bbox_vs_ifc_ft"] = mx("bbox_vs_ifc_body_ft")
        t["duplicates"] = sum(r["duplicates"] for r in got)
        table.append(t)
    extra = Counter(objs[i]["speckle_type"] + " / " + str(objs[i]["flat"].get("Attributes.type") or
                                                          objs[i]["flat"].get("category") or objs[i].get("category")
                                                          or (objs[i]["path"][-1] if objs[i]["path"] else ""))
                    for i in range(len(objs)) if i not in used)
    report = {"label": label, "version_id": recv["version_id"], "source_application": recv["source_application"],
              "objects_received": len(objs), "speckle_types": recv["speckle_types"], "table": table,
              "lost": [m["id"] for m in lost], "unmatched_received": dict(extra), "rows": rows}
    print(f"\n== {label}: version {recv['version_id']} ({recv['source_application']}), {len(objs)} objects received")
    hdr = ["category", "sent", "matched", *CHECKS, "id_in_name_only", "coord_ok", "max_line_err_ft", "max_bbox_vs_registry_ft",
           "max_bbox_vs_ifc_ft", "duplicates"]
    print("| " + " | ".join(hdr) + " |")
    print("|" + "---|" * len(hdr))
    for t in table:
        print("| " + " | ".join("-" if t[h] is None else str(t[h]) for h in hdr) + " |")
    print(f"lost: {len(lost)} {[m['id'] for m in lost][:10]}")
    print(f"received objects not matched to a member: {dict(extra)}")
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--out", required=True)
    s = sub.add_parser("send")
    s.add_argument("--payload", required=True)
    s.add_argument("--ifc")
    s.add_argument("--skip-ifc", action="store_true")
    s.add_argument("--skip-registry", action="store_true")
    s.add_argument("--project", default=PROJECT_NAME)
    s.add_argument("--project-id", help="send into this existing project instead of finding/creating --project")
    s.add_argument("--out", required=True)
    r = sub.add_parser("receive")
    r.add_argument("--project-id", required=True)
    r.add_argument("--model", required=True, help="model name or id")
    r.add_argument("--version")
    r.add_argument("--out", required=True)
    d = sub.add_parser("diff")
    d.add_argument("--sent", required=True)
    d.add_argument("--recv", required=True)
    d.add_argument("--label", default="round trip")
    d.add_argument("--json-out")
    a = ap.parse_args()
    if a.cmd == "build":
        build(a.out)
    elif a.cmd == "send":
        send(a.payload, a.ifc, a.project, a.out, a.skip_ifc, a.project_id, a.skip_registry)
    elif a.cmd == "receive":
        receive(a.project_id, a.model, a.version, a.out)
    else:
        rep = diff(a.sent, a.recv, a.label)
        if a.json_out:
            json.dump(rep, open(a.json_out, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
