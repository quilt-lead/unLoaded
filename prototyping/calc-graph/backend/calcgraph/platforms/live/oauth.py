"""OAuth 2.0 authorization-code login with a local loopback callback, token refresh, and logout.

    uv run python scripts/platform_auth.py login procore      # Procore Developer Sandbox
    uv run python scripts/platform_auth.py login aps          # Autodesk APS (ACC Build + Forma)

Endpoints (each read from the vendor docs; URLs in docs/platforms-real.md):

  Procore  authorize  {login host}/oauth/authorize    token {login host}/oauth/token
           login host: Developer Sandbox https://login-sandbox.procore.com (API https://sandbox.procore.com),
           Monthly Sandbox https://login-sandbox-monthly.procore.com (API https://api-monthly.procore.com).
           client_id + client_secret in the form body; refresh tokens are SINGLE USE and rotate, so the new
           one is saved on every refresh. PKCE is not documented by Procore and is not sent.
           Production (login.procore.com / api.procore.com, which On-Demand sandboxes also use) is refused here:
           this prototype never authenticates against a production company.
  APS      authorize  https://developer.api.autodesk.com/authentication/v2/authorize
           token      https://developer.api.autodesk.com/authentication/v2/token
           client auth: HTTP Basic header (never also in the body - APS answers 400 to both);
           PKCE S256 sent (supported, optional); access token ~60 min, refresh token 15 days.
           Scopes: data:read data:write data:create account:read.

The callback listener binds the LOOPBACK interface only (127.0.0.1, and ::1 when the redirect host is
"localhost" so either resolution works), serves exactly one request on the registered path, checks
`state`, and shuts down. Tokens go to data/secrets/<platform>_token.json (0600). Nothing secret is printed.
"""
from __future__ import annotations

import base64
import hashlib
import http.server
import json
import secrets as pysecrets
import socket
import threading
import time
import urllib.parse
import webbrowser

import httpx

from . import secrets as store

APS_AUTHORIZE = "https://developer.api.autodesk.com/authentication/v2/authorize"
APS_TOKEN = "https://developer.api.autodesk.com/authentication/v2/token"
APS_SCOPES = "data:read data:write data:create account:read"
PROCORE_ENVS = {
    "sandbox": {"login": "https://login-sandbox.procore.com", "api": "https://sandbox.procore.com"},
    "monthly": {"login": "https://login-sandbox-monthly.procore.com", "api": "https://api-monthly.procore.com"},
}
PRODUCTION_HOSTS = ("login.procore.com", "api.procore.com", "app.procore.com")
DEFAULT_REDIRECT = {"procore": "http://localhost:8791/oauth/callback/procore",
                    "aps": "http://localhost:8791/oauth/callback/aps"}
REFRESH_MARGIN_S = 120
OOB = "urn:ietf:wg:oauth:2.0:oob"   # Procore "installed app" variant: the code is shown on a page, then pasted


class AuthError(RuntimeError):
    pass


def procore_env(cfg: dict | None = None) -> dict:
    cfg = cfg if cfg is not None else store.app_config("procore")
    env = (cfg.get("env") or "sandbox").strip().lower()
    if env not in PROCORE_ENVS:
        raise AuthError(f"PROCORE_ENV={env!r} refused: only {sorted(PROCORE_ENVS)} (never production)")
    return {"name": env, **PROCORE_ENVS[env]}


def redirect_uri(platform: str) -> str:
    return store.app_config(platform).get("redirect_uri") or DEFAULT_REDIRECT[platform]


def _pkce() -> tuple[str, str]:
    verifier = base64.urlsafe_b64encode(pysecrets.token_bytes(48)).rstrip(b"=").decode()
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


def authorize_url(platform: str, state: str, challenge: str | None) -> str:
    cfg = store.app_config(platform)
    if not cfg.get("client_id"):
        raise AuthError(f"no {platform} client id: set it in data/secrets/{platform}_app.json or the env")
    q = {"response_type": "code", "client_id": cfg["client_id"], "redirect_uri": redirect_uri(platform), "state": state}
    if platform == "aps":
        q["scope"] = APS_SCOPES
        if challenge:
            q.update(code_challenge=challenge, code_challenge_method="S256")
        return APS_AUTHORIZE + "?" + urllib.parse.urlencode(q, quote_via=urllib.parse.quote)
    return procore_env(cfg)["login"] + "/oauth/authorize?" + urllib.parse.urlencode(q, quote_via=urllib.parse.quote)


def _token_request(platform: str, form: dict) -> dict:
    cfg = store.app_config(platform)
    if not (cfg.get("client_id") and cfg.get("client_secret")):
        raise AuthError(f"{platform} client id/secret missing (data/secrets/{platform}_app.json or env)")
    headers = {"Accept": "application/json"}
    if platform == "aps":
        basic = base64.b64encode(f"{cfg['client_id']}:{cfg['client_secret']}".encode()).decode()
        headers["Authorization"] = f"Basic {basic}"
        url = APS_TOKEN
    else:
        form = {**form, "client_id": cfg["client_id"], "client_secret": cfg["client_secret"]}
        url = procore_env(cfg)["login"] + "/oauth/token"
    r = httpx.post(url, data=form, headers=headers, timeout=30)
    if r.status_code != 200:
        raise AuthError(f"{platform} token endpoint {r.status_code}: {store.redact(r.text[:300])}")
    tok = r.json()
    now = int(time.time())
    tok["obtained_at"] = now
    tok["expires_at"] = now + int(tok.get("expires_in") or 3600)
    if platform == "procore":
        tok["env"] = procore_env(cfg)["name"]
    return tok


class _Catch(http.server.BaseHTTPRequestHandler):
    result: dict = {}
    path_expected = "/"

    def do_GET(self):  # noqa: N802
        u = urllib.parse.urlparse(self.path)
        if u.path.rstrip("/") != self.path_expected.rstrip("/"):
            self.send_response(404)
            self.end_headers()
            return
        q = {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
        type(self).result.update(q)
        ok = "code" in q
        self.send_response(200 if ok else 400)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        msg = "Signed in. You can close this tab and return to the terminal." if ok else \
            f"Sign-in did not return a code ({q.get('error', 'unknown error')}). See the terminal."
        self.wfile.write(f"<!doctype html><meta charset=utf-8><title>calc-graph</title><p>{msg}</p>".encode())

    def log_message(self, *a):   # never log the query string (it carries the code)
        return


class _Server6(http.server.HTTPServer):
    address_family = socket.AF_INET6


def _listen(uri: str, handler) -> list[http.server.HTTPServer]:
    u = urllib.parse.urlparse(uri)
    if u.scheme != "http" or u.hostname not in ("127.0.0.1", "localhost", "::1"):
        raise AuthError(f"redirect URI {uri!r} must be http://127.0.0.1:<port>/... or http://localhost:<port>/...")
    port = u.port or 80
    servers = [http.server.HTTPServer(("127.0.0.1", port), handler)]
    if u.hostname in ("localhost", "::1"):
        try:
            servers.append(_Server6(("::1", port), handler))
        except OSError:
            pass
    return servers


def login(platform: str, open_browser: bool = True, timeout_s: int = 300) -> dict:
    """Run the authorization-code flow end to end; returns a redacted summary of the saved token."""
    state = pysecrets.token_urlsafe(24)
    verifier, challenge = _pkce() if platform == "aps" else (None, None)
    uri = redirect_uri(platform)
    if uri == OOB:
        if platform != "procore":
            raise AuthError("the oob redirect is a Procore feature; APS needs a loopback callback URL")
        print("Open this URL, sign in, and paste the code Procore shows (no secret in the URL):\n  "
              + authorize_url(platform, state, None))
        if open_browser:
            webbrowser.open(authorize_url(platform, state, None))
        return login_with_code(platform, input("code: ").strip())

    class H(_Catch):
        result: dict = {}
        path_expected = urllib.parse.urlparse(uri).path or "/"

    servers = _listen(uri, H)
    for s in servers:
        s.timeout = 1
    url = authorize_url(platform, state, challenge)
    print(f"Open this URL to sign in to {platform} (it carries the client id, no secret):\n  {url}\n"
          f"Waiting up to {timeout_s}s for the redirect to {uri} ...")
    if open_browser:
        webbrowser.open(url)
    stop = time.time() + timeout_s

    def serve(s):
        while not H.result and time.time() < stop:
            s.handle_request()

    threads = [threading.Thread(target=serve, args=(s,), daemon=True) for s in servers]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout_s + 5)
    for s in servers:
        s.server_close()
    res = dict(H.result)
    if not res:
        raise AuthError("timed out waiting for the OAuth redirect")
    if res.get("state") != state:
        raise AuthError("OAuth state mismatch: refusing the code")
    if "code" not in res:
        raise AuthError(f"authorization failed: {res.get('error')} {res.get('error_description', '')}")
    form = {"grant_type": "authorization_code", "code": res["code"], "redirect_uri": uri}
    if verifier:
        form["code_verifier"] = verifier
    tok = _token_request(platform, form)
    store.save_token(platform, tok)
    return summary(platform)


def login_with_code(platform: str, code: str) -> dict:
    """Procore 'installed app' variant: redirect URI urn:ietf:wg:oauth:2.0:oob shows the code on a page;
    paste it here. Only for when a loopback redirect cannot be registered."""
    tok = _token_request(platform, {"grant_type": "authorization_code", "code": code,
                                    "redirect_uri": redirect_uri(platform)})
    store.save_token(platform, tok)
    return summary(platform)


def refresh(platform: str) -> dict:
    tok = store.token(platform)
    if not tok.get("refresh_token"):
        raise AuthError(f"no {platform} refresh token: run scripts/platform_auth.py login {platform}")
    new = _token_request(platform, {"grant_type": "refresh_token", "refresh_token": tok["refresh_token"]})
    if "refresh_token" not in new:      # keep the old one only if the server did not rotate it
        new["refresh_token"] = tok["refresh_token"]
    store.save_token(platform, new)
    return new


def access_token(platform: str) -> str:
    """A valid access token, refreshed when within REFRESH_MARGIN_S of expiry. Raises AuthError when absent."""
    tok = store.token(platform)
    if not tok.get("access_token"):
        raise AuthError(f"not signed in to {platform}: run scripts/platform_auth.py login {platform}")
    if platform == "procore" and tok.get("env") and tok["env"] != procore_env()["name"]:
        raise AuthError(f"saved Procore token is for {tok['env']!r}, config says {procore_env()['name']!r}: log in again")
    if int(tok.get("expires_at") or 0) - REFRESH_MARGIN_S < time.time():
        tok = refresh(platform)
    return tok["access_token"]


def summary(platform: str) -> dict:
    tok = store.token(platform)
    if not tok:
        return {"platform": platform, "signed_in": False, "app_configured": store.has_app(platform)}
    return {"platform": platform, "signed_in": bool(tok.get("access_token")), "app_configured": store.has_app(platform),
            "expires_in_s": int(tok.get("expires_at", 0) - time.time()), "has_refresh_token": bool(tok.get("refresh_token")),
            "scope": tok.get("scope"), "env": tok.get("env")}


def logout(platform: str) -> bool:
    return store.delete(f"{platform}_token.json")


if __name__ == "__main__":
    print(json.dumps({p: summary(p) for p in ("procore", "aps")}, indent=1))
