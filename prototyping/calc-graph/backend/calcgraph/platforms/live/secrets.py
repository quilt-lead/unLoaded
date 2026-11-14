"""Local, gitignored storage for platform app credentials and OAuth tokens.

Layout (all under data/secrets/, which .gitignore excludes; directory 0700, files 0600):

  data/secrets/procore_app.json   {"client_id", "client_secret", "env": "sandbox", "redirect_uri"?, "company_id"?, "project_id"?}
  data/secrets/aps_app.json       {"client_id", "client_secret", "redirect_uri"?, "hub_id"?, "project_id"?, "forma_project_id"?}
  data/secrets/<platform>_token.json   written by oauth.py: access/refresh token + expiry

Environment variables override the app file (never the token file):
  PROCORE_CLIENT_ID, PROCORE_CLIENT_SECRET, PROCORE_ENV (sandbox | monthly), PROCORE_COMPANY_ID, PROCORE_PROJECT_ID
  APS_CLIENT_ID, APS_CLIENT_SECRET, ACC_HUB_ID, ACC_PROJECT_ID, FORMA_PROJECT_ID
  CALCGRAPH_SECRETS_DIR (relocate the directory, e.g. for the contract tests)

Nothing here ever prints a secret: `redact()` is what every log line and error message goes through.
"""
from __future__ import annotations

import json
import os
import re
import stat
import tempfile

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
ENV_KEYS = {
    "procore": {"client_id": "PROCORE_CLIENT_ID", "client_secret": "PROCORE_CLIENT_SECRET", "env": "PROCORE_ENV",
                "company_id": "PROCORE_COMPANY_ID", "project_id": "PROCORE_PROJECT_ID",
                "redirect_uri": "PROCORE_REDIRECT_URI"},
    "aps": {"client_id": "APS_CLIENT_ID", "client_secret": "APS_CLIENT_SECRET", "hub_id": "ACC_HUB_ID",
            "project_id": "ACC_PROJECT_ID", "forma_project_id": "FORMA_PROJECT_ID", "redirect_uri": "APS_REDIRECT_URI"},
}
SECRET_FIELDS = ("client_secret", "access_token", "refresh_token", "id_token", "code", "code_verifier")


def secrets_dir() -> str:
    d = os.environ.get("CALCGRAPH_SECRETS_DIR") or os.path.join(ROOT, "data", "secrets")
    os.makedirs(d, mode=0o700, exist_ok=True)
    try:
        os.chmod(d, 0o700)
    except OSError:
        pass
    return d


def _path(name: str) -> str:
    return os.path.join(secrets_dir(), name)


def _check_mode(p: str) -> None:
    mode = stat.S_IMODE(os.stat(p).st_mode)
    if mode & 0o077:
        os.chmod(p, 0o600)


def read_json(name: str) -> dict:
    p = _path(name)
    if not os.path.exists(p):
        return {}
    _check_mode(p)
    with open(p) as fh:
        return json.load(fh)


def write_json(name: str, data: dict) -> str:
    """Atomic write, created 0600 (never world/group readable even for an instant)."""
    d = secrets_dir()
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".tmp-", suffix=".json")
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w") as fh:
            json.dump(data, fh, indent=1, sort_keys=True)
        os.replace(tmp, _path(name))
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    return _path(name)


def delete(name: str) -> bool:
    p = _path(name)
    if os.path.exists(p):
        os.remove(p)
        return True
    return False


def app_config(platform: str) -> dict:
    """Client id/secret and ids for `platform` ("procore" | "aps"): app file, overridden by env."""
    cfg = dict(read_json(f"{platform}_app.json"))
    for key, env in ENV_KEYS[platform].items():
        v = os.environ.get(env)
        if v:
            cfg[key] = v
    return cfg


def has_app(platform: str) -> bool:
    c = app_config(platform)
    return bool(c.get("client_id") and c.get("client_secret"))


def token(platform: str) -> dict:
    return read_json(f"{platform}_token.json")


def save_token(platform: str, tok: dict) -> str:
    return write_json(f"{platform}_token.json", tok)


_BEARER = re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+")
_KV = re.compile(r'(?i)("?(?:%s)"?\s*[:=]\s*"?)([^"&\s,}]+)' % "|".join(SECRET_FIELDS))
_BASIC = re.compile(r"(?i)(basic\s+)[A-Za-z0-9+/=]+")


def redact(text) -> str:
    """Mask bearer/basic credentials and any secret-named key=value / "key": "value" in a string."""
    s = str(text)
    s = _BEARER.sub(r"\1***", s)
    s = _BASIC.sub(r"\1***", s)
    s = _KV.sub(r"\1***", s)
    for platform in ENV_KEYS:
        sec = app_config(platform).get("client_secret") if os.path.exists(_path(f"{platform}_app.json")) or os.environ.get(ENV_KEYS[platform]["client_secret"]) else None
        if sec and len(sec) >= 8:
            s = s.replace(sec, "***")
    return s
