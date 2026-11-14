"""Sign in to the real construction platforms and pick the sandbox / trial project the live adapters read.

  uv run python scripts/platform_auth.py setup procore|aps            # prompts for client id + secret (hidden), writes 0600
  uv run python scripts/platform_auth.py status
  uv run python scripts/platform_auth.py login procore|aps [--no-browser]
  uv run python scripts/platform_auth.py code procore <code>        # Procore oob variant (paste the code)
  uv run python scripts/platform_auth.py projects procore|aps       # list what the token can see
  uv run python scripts/platform_auth.py use procore <company_id> <project_id>
  uv run python scripts/platform_auth.py use aps <hub_id> <project_id> [<forma pro_ id>]
  uv run python scripts/platform_auth.py allow-seed procore|aps <project_id>   # allowlist a sandbox/trial project for writes
  uv run python scripts/platform_auth.py logout procore|aps

App credentials come from data/secrets/<platform>_app.json (0600, gitignored) or the env (see
backend/calcgraph/platforms/live/secrets.py). This script never prints a secret or a token.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from calcgraph.platforms.live import oauth  # noqa: E402
from calcgraph.platforms.live import secrets as store  # noqa: E402
from calcgraph.platforms.live.transport import Session  # noqa: E402


def projects(platform: str) -> dict:
    if platform == "procore":
        from calcgraph.platforms.live.generated.procore_client import AuthenticatedClient
        from calcgraph.platforms.live.generated.procore_client.api.calcgraph import list_companies, list_projects
        env = oauth.procore_env()
        s = Session("procore", env["api"], AuthenticatedClient)
        comps, _ = s.call(list_companies)
        out = []
        for c in comps or []:
            projs = s.procore_pages(list_projects, company_id=c["id"], procore_company_id=c["id"])
            out.append({"company_id": c["id"], "company": c.get("name"),
                        "projects": [{"project_id": p["id"], "name": p.get("name"), "active": p.get("active")} for p in projs]})
        return {"env": env["name"], "api": env["api"], "companies": out}
    from calcgraph.platforms.live.generated.aps_dm_client import AuthenticatedClient
    from calcgraph.platforms.live.generated.aps_dm_client.api.calcgraph import get_hub_projects, get_hubs
    s = Session("aps", "https://developer.api.autodesk.com", AuthenticatedClient)
    hubs, _ = s.call(get_hubs)
    out = []
    for h in (hubs or {}).get("data") or []:
        projs, _ = s.call(get_hub_projects, hub_id=h["id"])
        out.append({"hub_id": h["id"], "hub": (h.get("attributes") or {}).get("name"),
                    "region": (h.get("attributes") or {}).get("region"),
                    "projects": [{"project_id": p["id"], "name": (p.get("attributes") or {}).get("name")}
                                 for p in (projs or {}).get("data") or []]})
    return {"hubs": out}


def use(platform: str, ids: list[str]) -> dict:
    cfg = store.read_json(f"{platform}_app.json")
    if platform == "procore":
        cfg.update(company_id=int(ids[0]), project_id=int(ids[1]))
    else:
        cfg.update(hub_id=ids[0], project_id=ids[1])
        if len(ids) > 2:
            cfg["forma_project_id"] = ids[2]
    store.write_json(f"{platform}_app.json", cfg)
    return {k: v for k, v in cfg.items() if k not in store.SECRET_FIELDS}


def setup(platform: str) -> dict:
    import getpass
    cfg = store.read_json(f"{platform}_app.json")
    cid = input(f"{platform} client id: ").strip()
    sec = getpass.getpass(f"{platform} client secret (hidden, not echoed): ").strip()
    if not (cid and sec):
        raise SystemExit("client id and secret are both required")
    cfg.update(client_id=cid, client_secret=sec)
    if platform == "procore":
        cfg.setdefault("env", "sandbox")
    store.write_json(f"{platform}_app.json", cfg)
    return {"saved": f"data/secrets/{platform}_app.json (0600)", "redirect_uri_to_register": oauth.redirect_uri(platform)}


def allow_seed(platform: str, project_id: str) -> dict:
    cfg = store.read_json(f"{platform}_app.json")
    ids = list(cfg.get("seed_allowed_project_ids") or [])
    val = int(project_id) if platform == "procore" else project_id
    if val not in ids:
        ids.append(val)
    cfg["seed_allowed_project_ids"] = ids
    store.write_json(f"{platform}_app.json", cfg)
    return {"seed_allowed_project_ids": ids}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["setup", "status", "login", "code", "projects", "use", "allow-seed", "logout"])
    ap.add_argument("platform", nargs="?", choices=["procore", "aps"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args()
    if a.cmd != "status" and not a.platform:
        ap.error("platform required")
    try:
        if a.cmd == "status":
            res = {p: oauth.summary(p) for p in ("procore", "aps")}
            for p in res:
                res[p]["redirect_uri"] = oauth.redirect_uri(p)
        elif a.cmd == "login":
            res = oauth.login(a.platform, open_browser=not a.no_browser)
        elif a.cmd == "code":
            res = oauth.login_with_code(a.platform, a.args[0])
        elif a.cmd == "projects":
            res = projects(a.platform)
        elif a.cmd == "use":
            res = use(a.platform, a.args)
        elif a.cmd == "setup":
            res = setup(a.platform)
        elif a.cmd == "allow-seed":
            res = allow_seed(a.platform, a.args[0])
        else:
            res = {"logged_out": oauth.logout(a.platform)}
    except Exception as e:   # noqa: BLE001
        print(store.redact(f"{type(e).__name__}: {e}"), file=sys.stderr)
        return 1
    print(json.dumps(res, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
