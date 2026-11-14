"""Generate the TYPED HTTP CLIENTS the live platform adapters call, from the vendors' official OpenAPI specs.

  uv run python scripts/gen_platform_clients.py [--refresh]

Generator: openapi-python-client==0.29.1 (pinned, run through uvx; same pin as gen_platform_models.py).
Output: backend/calcgraph/platforms/live/generated/<package>/ (client.py, api/, models/, types.py, errors.py).
These are FULL clients (httpx), unlike gen_platform_models.py which keeps models only for the mocks.

Specs (each subset keeps exactly the operations the live adapters / seeding script call, with their
parameters, request bodies and success responses; `example(s)` are stripped, a top-level `allOf` is
flattened, `oneOf` serializer views collapse to the default view; $refs are carried by closure):

  procore_client      Procore REST "download OAS" (developers.procore.com/api/v1/resource_groups/full_oas?version=1),
                      cached at data/store/specs/procore_rest_v1_full_oas.json (gitignored, 63 MB)
  aps_issues_client   github.com/autodesk-platform-services/aps-sdk-openapi  forma/issues/Issues.yaml        (Apache-2.0)
  aps_dm_client       same repo  datamanagement/datamanagement.yaml                                          (Apache-2.0)
  aps_admin_client    same repo  forma/accountadmin/accountadmin.yaml                                        (Apache-2.0)

The APS repo is pinned to a commit (APS_SHA). ACC RFIs, Submittals, Cost Management and Sheets have NO
official OpenAPI spec in that repo (checked at APS_SHA, 2026-11-14), so their client
(platforms/live/acc_rest.py) is hand-written from the APS reference pages cited in docs/platforms-real.md.

Request-body keys that are Procore templates (`custom_field_%{...}`) are dropped from request bodies: the
generator cannot name them, and the seeding script does not set custom fields.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
import urllib.request

import yaml

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
GEN = os.path.join(ROOT, "backend", "calcgraph", "platforms", "live", "generated")
CACHE = os.path.join(ROOT, "data", "store", "specs")
GENERATOR = "openapi-python-client==0.29.1"
PROCORE_URL = "https://developers.procore.com/api/v1/resource_groups/full_oas?version=1"
APS_SHA = "1e2490246ad3e05c86bc97ca20719054fce54a9e"   # aps-sdk-openapi main, pushed 2026-11-05
APS_RAW = f"https://raw.githubusercontent.com/autodesk-platform-services/aps-sdk-openapi/{APS_SHA}/"

# package -> (spec source, {(path, method): python function name})
PROCORE_OPS = {
    ("/rest/v1.0/companies", "get"): "list_companies",
    ("/rest/v1.1/projects", "get"): "list_projects",
    ("/rest/v1.1/projects/{project_id}/submittals", "get"): "list_submittals",
    ("/rest/v1.1/projects/{project_id}/submittals", "post"): "create_submittal",
    ("/rest/v1.1/projects/{project_id}/submittals/{id}", "get"): "get_submittal",
    ("/rest/v1.0/projects/{project_id}/rfis", "get"): "list_rfis",
    ("/rest/v1.0/projects/{project_id}/rfis", "post"): "create_rfi",
    ("/rest/v1.0/projects/{project_id}/rfis/{id}", "get"): "get_rfi",
    ("/rest/v1.0/projects/{project_id}/rfis/potential_rfi_managers", "get"): "list_potential_rfi_managers",
    ("/rest/v1.1/change_events", "get"): "list_change_events",
    ("/rest/v1.1/change_events", "post"): "create_change_event",
    ("/rest/v1.1/change_events/{id}", "get"): "get_change_event",
    ("/rest/v1.0/change_order_packages", "get"): "list_change_order_packages",
    ("/rest/v1.0/commitments", "get"): "list_commitments",
    ("/rest/v1.0/tasks", "get"): "list_tasks",
    ("/rest/v1.1/projects/{project_id}/drawing_areas", "get"): "list_drawing_areas",
    ("/rest/v1.1/drawing_areas/{drawing_area_id}/drawings", "get"): "list_drawings",
    ("/rest/v1.0/cost_codes", "get"): "list_cost_codes",
    ("/rest/v1.0/specification_sections", "get"): "list_specification_sections",
    ("/rest/v1.0/companies/{company_id}/submittal_statuses", "get"): "list_submittal_statuses",
    ("/rest/v2.0/companies/{company_id}/change_events/statuses", "get"): "list_change_event_statuses",
    ("/rest/v1.0/change_types", "get"): "list_change_types",
}
ISSUES_OPS = {
    ("/construction/issues/v1/projects/{projectId}/users/me", "get"): "get_user_profile",
    ("/construction/issues/v1/projects/{projectId}/issue-types", "get"): "get_issue_types",
    ("/construction/issues/v1/projects/{projectId}/issues", "get"): "get_issues",
    ("/construction/issues/v1/projects/{projectId}/issues", "post"): "create_issue",
    ("/construction/issues/v1/projects/{projectId}/issues/{issueId}", "get"): "get_issue_details",
}
DM_OPS = {
    ("/project/v1/hubs", "get"): "get_hubs",
    ("/project/v1/hubs/{hub_id}/projects", "get"): "get_hub_projects",
    ("/project/v1/hubs/{hub_id}/projects/{project_id}", "get"): "get_project",
}
ADMIN_OPS = {
    ("/construction/admin/v1/projects/{projectId}", "get"): "get_project",
}
PACKAGES = {
    "procore_client": ("procore", PROCORE_OPS),
    "aps_issues_client": ("forma/issues/Issues.yaml", ISSUES_OPS),
    "aps_dm_client": ("datamanagement/datamanagement.yaml", DM_OPS),
    "aps_admin_client": ("forma/accountadmin/accountadmin.yaml", ADMIN_OPS),
}


def _fetch(url: str, dest: str, refresh: bool) -> bytes:
    if refresh or not os.path.exists(dest):
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        req = urllib.request.Request(url, headers={"User-Agent": "calc-graph-codegen"})
        with urllib.request.urlopen(req, timeout=180) as r, open(dest, "wb") as fh:
            shutil.copyfileobj(r, fh)
    return open(dest, "rb").read()


def _strip(o):
    if isinstance(o, dict):
        return {k: _strip(v) for k, v in o.items() if k not in ("example", "examples")}
    if isinstance(o, list):
        return [_strip(v) for v in o]
    return o


def _flatten(s):
    """Procore inlines everything: collapse serializer-view oneOfs and top-level allOfs so the generator
    produces one model per response instead of unions it cannot name."""
    if not isinstance(s, dict) or "$ref" in s:
        return s
    s = copy.deepcopy(s)
    if "oneOf" in s and all(isinstance(v, dict) for v in s["oneOf"]):
        objs = [v for v in s["oneOf"] if v.get("type") in ("object", "array")]
        default = [v for v in objs if v.get("title") == "default"]
        if objs:
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
    if "properties" in s:
        s["properties"] = {k: _flatten(v) for k, v in s["properties"].items()}
    if s.get("type") == "array" and isinstance(s.get("items"), dict):
        s["items"] = _flatten(s["items"])
    s.pop("title", None)
    return s


def _drop_templates(s):
    if isinstance(s, dict):
        if isinstance(s.get("properties"), dict):
            s["properties"] = {k: _drop_templates(v) for k, v in s["properties"].items() if "%{" not in k}
            if "required" in s:
                s["required"] = [r for r in s["required"] if "%{" not in r] or None
                if s["required"] is None:
                    s.pop("required")
        for k, v in list(s.items()):
            if k != "properties":
                s[k] = _drop_templates(v)
    elif isinstance(s, list):
        return [_drop_templates(v) for v in s]
    return s


def _refs(o, acc: set):
    if isinstance(o, dict):
        r = o.get("$ref")
        if isinstance(r, str) and r.startswith("#/components/"):
            acc.add(r)
        for v in o.values():
            _refs(v, acc)
    elif isinstance(o, list):
        for v in o:
            _refs(v, acc)


def subset(spec: dict, ops: dict, title: str, source: str, flatten: bool) -> dict:
    paths: dict = {}
    for (path, method), fn in ops.items():
        item = spec["paths"][path]
        op = copy.deepcopy(_strip(item[method]))
        op["operationId"] = fn
        op["tags"] = ["calcgraph"]
        params = list(item.get("parameters", [])) + list(op.get("parameters", []))
        # Procore list filters (`filters[...]`, `sort[...]`) are dropped: names the generator mangles, unused here
        op["parameters"] = [p for p in params if "[" not in p.get("name", "")]
        if method == "get":
            op.pop("requestBody", None)    # Procore documents GET bodies (filters) - not sent
        elif "requestBody" in op:
            content = op["requestBody"]["content"]
            keep = {k: v for k, v in content.items() if k == "application/json"} or content
            op["requestBody"]["content"] = keep
            for v in keep.values():
                sch = v["schema"]
                v["schema"] = _drop_templates(_flatten(sch) if flatten else sch)
        resp = {}
        for code, r in op["responses"].items():
            if str(code).startswith("2"):
                r = copy.deepcopy(r)
                for v in (r.get("content") or {}).values():
                    if flatten:
                        v["schema"] = _drop_templates(_flatten(v["schema"]))
                resp[str(code)] = r
        op["responses"] = resp or {"default": {"description": "see vendor docs"}}
        paths.setdefault(path, {})[method] = op
    out = {"openapi": spec.get("openapi", "3.0.0") if str(spec.get("openapi", "")).startswith("3.0") else "3.0.0",
           "info": {"title": title, "version": str(spec["info"].get("version")), "description": source},
           "servers": spec.get("servers") or [], "paths": paths}
    comps = spec.get("components") or {}
    need: set = set()
    _refs(paths, need)
    sub: dict = {}
    seen: set = set()
    while need - seen:
        ref = sorted(need - seen)[0]
        seen.add(ref)
        _, _, kind, name = ref.split("/", 3)
        node = comps.get(kind, {}).get(name)
        if node is None:
            raise SystemExit(f"dangling $ref {ref}")
        node = _strip(node)
        sub.setdefault(kind, {})[name] = node
        _refs(node, need)
    if comps.get("securitySchemes"):
        sub["securitySchemes"] = comps["securitySchemes"]
    if sub:
        out["components"] = sub
    return out


def generate(subset_path: str, pkg: str) -> None:
    tmp = os.path.join(GEN, "_tmp_" + pkg)
    shutil.rmtree(tmp, ignore_errors=True)
    cfg = os.path.join(GEN, "_codegen_config.yaml")
    with open(cfg, "w") as fh:
        fh.write(f"package_name_override: {pkg}\nproject_name_override: {pkg}\n")
    subprocess.run(["uvx", "--from", GENERATOR, "openapi-python-client", "generate", "--path", subset_path,
                    "--meta", "none", "--output-path", tmp, "--config", cfg, "--overwrite"], check=True)
    os.remove(cfg)
    dest = os.path.join(GEN, pkg)
    shutil.rmtree(dest, ignore_errors=True)
    shutil.copytree(tmp, dest)
    shutil.rmtree(tmp)
    init = os.path.join(dest, "__init__.py")
    body = open(init).read()
    with open(init, "w") as fh:
        fh.write(f'"""Generated by {GENERATOR} from {os.path.basename(subset_path)}. Do not edit;\n'
                 'regenerate with scripts/gen_platform_clients.py."""\n' + body.split('"""', 2)[-1])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="re-download the specs")
    ap.add_argument("--only", nargs="*", help="package names to regenerate")
    a = ap.parse_args()
    os.makedirs(GEN, exist_ok=True)
    report = {}
    for pkg, (src, ops) in PACKAGES.items():
        if a.only and pkg not in a.only:
            continue
        if src == "procore":
            raw = _fetch(PROCORE_URL, os.path.join(CACHE, "procore_rest_v1_full_oas.json"), a.refresh)
            spec = json.loads(raw)
            source = (f"Subset of {PROCORE_URL} (x-created-at {spec['info'].get('x-created-at')}, "
                      f"sha256 {hashlib.sha256(raw).hexdigest()}). Procore developer terms apply.")
            sub = subset(spec, ops, "Procore REST API - subset called by calc-graph live adapters", source, flatten=True)
        else:
            raw = _fetch(APS_RAW + src, os.path.join(CACHE, "aps", APS_SHA[:12], src), a.refresh)
            spec = yaml.safe_load(raw)
            source = (f"Subset of {APS_RAW}{src} (sha256 {hashlib.sha256(raw).hexdigest()}). Apache-2.0, "
                      "github.com/autodesk-platform-services/aps-sdk-openapi.")
            sub = subset(spec, ops, f"{spec['info'].get('title')} - subset called by calc-graph live adapters",
                         source, flatten=False)
        sp = os.path.join(GEN, f"{pkg}.openapi.json")
        with open(sp, "w") as fh:
            json.dump(sub, fh, indent=1, sort_keys=True)
        generate(sp, pkg)
        report[pkg] = {"source": source, "operations": sorted(ops.values())}
    with open(os.path.join(GEN, "__init__.py"), "w") as fh:
        fh.write('"""Typed HTTP clients generated by scripts/gen_platform_clients.py (openapi-python-client 0.29.1)."""\n')
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    sys.exit(main())
