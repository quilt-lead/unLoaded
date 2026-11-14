"""Generate TYPED models for the mock platform adapters from official OpenAPI specs.

  uv run python scripts/gen_platform_models.py [--refresh]

Procore: Procore publishes its full REST OpenAPI document (developers.procore.com, "download OAS";
endpoint below). It is ~60 MB with every schema inlined, so this script extracts only the GET
responses the Procore mock adapter emits, lifts each into a named component (flattening a top-level
`allOf`, picking the default `oneOf` serializer view, dropping `example`s), writes the subset to
backend/calcgraph/platforms/generated/procore_subset.openapi.json, and runs openapi-python-client
(pinned, see pyproject [project.optional-dependencies] codegen) on it. Only the generated `models/`
and `types.py` are kept (the httpx client is not needed: the adapters never call the network).

Autodesk APS / ACC: the official spec repo (github.com/autodesk-platform-services/aps-sdk-openapi,
Apache-2.0) publishes no Submittals, RFIs, Cost Management or Sheets spec (checked 2026-11-14), so
nothing is generated for ACC; autodesk_build.py keeps its hand shapes, read from the APS reference
pages and labelled there.

The full spec is cached under data/store/specs/ (gitignored); the run is reproducible from the cache.
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
import os
import shutil
import subprocess
import sys
import urllib.request

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
GEN = os.path.join(ROOT, "backend", "calcgraph", "platforms", "generated")
CACHE = os.path.join(ROOT, "data", "store", "specs")
GENERATOR = "openapi-python-client==0.29.1"
PROCORE_URL = "https://developers.procore.com/api/v1/resource_groups/full_oas?version=1"

# component name -> (path, method, pick): the objects ProcoreAdapter emits
PROCORE_OPS = {
    "ProcoreSubmittal": ("/rest/v1.1/projects/{project_id}/submittals/{id}", "get", None),
    "ProcoreRfi": ("/rest/v1.0/projects/{project_id}/rfis/{id}", "get", None),
    "ProcoreChangeEvent": ("/rest/v1.1/change_events/{id}", "get", None),
    "ProcoreChangeOrderPackage": ("/rest/v1.0/change_order_packages/{id}", "get", None),
    "ProcoreBudgetLineItem": ("/rest/v1.1/budget_line_items/{id}", "get", None),
    "ProcoreCostCode": ("/rest/v1.0/cost_codes/{id}", "get", None),
    "ProcoreTask": ("/rest/v1.0/tasks/{id}", "get", None),
    "ProcoreDrawing": ("/rest/v1.1/drawing_areas/{drawing_area_id}/drawings", "get", "items"),
}


def fetch(url: str, dest: str, refresh: bool) -> dict:
    if refresh or not os.path.exists(dest):
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        req = urllib.request.Request(url, headers={"User-Agent": "calc-graph-codegen"})
        with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as fh:
            shutil.copyfileobj(r, fh)
    raw = open(dest, "rb").read()
    return {"spec": json.loads(raw), "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw),
            "fetched": dt.datetime.fromtimestamp(os.path.getmtime(dest)).isoformat(timespec="minutes")}


def _strip(o):
    if isinstance(o, dict):
        return {k: _strip(v) for k, v in o.items() if k not in ("example", "examples")}
    if isinstance(o, list):
        return [_strip(v) for v in o]
    return o


def _flatten(s: dict) -> dict:
    s = copy.deepcopy(s)
    if "oneOf" in s:   # serializer views: take the default / richest object variant
        objs = [v for v in s["oneOf"] if v.get("type") == "array" and isinstance(v.get("items"), dict)
                and v["items"].get("type") == "object"] or [v for v in s["oneOf"] if v.get("type") == "object"]
        default = [v for v in objs if v.get("title") == "default"]
        s = (default or objs)[0]
    if "allOf" in s:
        out = {"type": "object", "properties": {}, "required": []}
        for part in s["allOf"]:
            part = _flatten(part)
            out["properties"].update(part.get("properties", {}))
            out["required"] += [r for r in part.get("required", []) if r not in out["required"]]
        if s.get("description"):
            out["description"] = s["description"]
        if not out["required"]:
            out.pop("required")
        s = out
    if "properties" in s:   # nested allOf/oneOf
        s["properties"] = {k: _flatten(v) for k, v in s["properties"].items()}
    if s.get("type") == "array" and isinstance(s.get("items"), dict):
        s["items"] = _flatten(s["items"])
    return s


def procore_subset(spec: dict, meta: dict) -> dict:
    comps, paths = {}, {}
    for name, (path, method, pick) in PROCORE_OPS.items():
        op = spec["paths"][path][method]
        sch = op["responses"]["200"]["content"]["application/json"]["schema"]
        sch = _flatten(_strip(sch))
        if pick == "items" or sch.get("type") == "array":
            sch = sch["items"]
        sch.pop("title", None)   # a top-level title would override the component name in codegen
        sch["x-source"] = f"{method.upper()} {path} (operationId {op.get('operationId')}) 200 response"
        comps[name] = sch
        # endpoints are not generated (the adapters are offline): only the response models matter
    return {"openapi": "3.0.0",
            "info": {"title": "Procore REST API - subset used by the calc-graph mock adapter", "version": spec["info"]["version"],
                     "description": f"Extracted by scripts/gen_platform_models.py from {PROCORE_URL} "
                                    f"(x-created-at {spec['info'].get('x-created-at')}, sha256 {meta['sha256']}, "
                                    f"fetched {meta['fetched']}). No licence is stated in the document; use is under "
                                    "Procore's developer terms."},
            "paths": paths, "components": {"schemas": comps}}


def generate(subset_path: str, pkg: str) -> None:
    out = os.path.join(GEN, "_tmp_" + pkg)
    shutil.rmtree(out, ignore_errors=True)
    cfg = os.path.join(GEN, "_codegen_config.yaml")
    with open(cfg, "w") as fh:
        fh.write(f"package_name_override: {pkg}\nproject_name_override: {pkg}\n")
    subprocess.run(["uvx", "--from", GENERATOR, "openapi-python-client", "generate", "--path", subset_path,
                    "--meta", "none", "--output-path", out, "--config", cfg, "--overwrite"], check=True)
    os.remove(cfg)
    dest = os.path.join(GEN, pkg)
    shutil.rmtree(dest, ignore_errors=True)
    os.makedirs(dest)
    shutil.copytree(os.path.join(out, "models"), os.path.join(dest, "models"))
    shutil.copy(os.path.join(out, "types.py"), os.path.join(dest, "types.py"))
    with open(os.path.join(dest, "__init__.py"), "w") as fh:
        fh.write(f'"""Models generated by {GENERATOR} from {os.path.basename(subset_path)}. Do not edit;\n'
                 'regenerate with scripts/gen_platform_models.py. HTTP client omitted (adapters are offline)."""\n')
    shutil.rmtree(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="re-download the specs")
    a = ap.parse_args()
    os.makedirs(GEN, exist_ok=True)
    meta = fetch(PROCORE_URL, os.path.join(CACHE, "procore_rest_v1_full_oas.json"), a.refresh)
    sub = procore_subset(meta["spec"], meta)
    sp = os.path.join(GEN, "procore_subset.openapi.json")
    with open(sp, "w") as fh:
        json.dump(sub, fh, indent=1, sort_keys=True)
    generate(sp, "procore_rest")
    print(json.dumps({"procore": {"url": PROCORE_URL, "sha256": meta["sha256"], "bytes": meta["bytes"],
                                  "fetched": meta["fetched"], "x-created-at": meta["spec"]["info"].get("x-created-at"),
                                  "schemas": list(PROCORE_OPS)},
                      "acc": "no official OpenAPI spec for submittals / RFIs / cost / sheets; hand shapes kept"}, indent=1))


if __name__ == "__main__":
    sys.exit(main())
