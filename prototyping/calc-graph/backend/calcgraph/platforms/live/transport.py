"""HTTP plumbing shared by the live adapters: generated-client calls, pagination, rate-limit backoff,
redacted logging, and a RECORDED transport for the contract tests.

`Session(platform, base_url)` wraps the generated `AuthenticatedClient` of one platform. Calls go
through the generated operation module's own `_get_kwargs` (so method, path, query and header names
come from the vendor spec), are sent on the client's httpx client, and the generated `_parse_response`
is then run as a CONTRACT CHECK: a typed-parse failure is recorded in `session.parse_errors` (with the
operation name) instead of aborting the read, and the adapter maps from the response JSON. That way a
spec/production drift shows up as a named error rather than as a blank change-order panel.

Recorded mode: `Session(..., recorded=Recorded(path))` swaps the network for an httpx.MockTransport
serving canned responses from a JSON file ([{method, path, query?, status, headers?, body}]); POSTs
are answered from the file too and every request body is kept in `recorded.requests` so a test can
assert exactly what a write would have sent. No network is touched in that mode.
"""
from __future__ import annotations

import json
import logging
import random
import time
import urllib.parse
from dataclasses import dataclass, field
from typing import Any, Callable

import httpx

from . import oauth
from . import secrets as store

log = logging.getLogger("calcgraph.platforms.live")
MAX_RETRIES = 4


class LiveError(RuntimeError):
    """A live call failed (status, auth, contract). Message is already redacted."""


@dataclass
class Recorded:
    path: str
    routes: list[dict] = field(default_factory=list)
    requests: list[dict] = field(default_factory=list)

    def __post_init__(self):
        with open(self.path) as fh:
            self.routes = json.load(fh)["routes"]

    def handler(self, request: httpx.Request) -> httpx.Response:
        q = dict(urllib.parse.parse_qsl(request.url.query.decode()))
        body = json.loads(request.content) if request.content else None
        self.requests.append({"method": request.method, "path": request.url.path, "query": q, "json": body,
                              "headers": {k: v for k, v in request.headers.items()
                                          if k.lower() in ("procore-company-id", "content-type", "x-ads-region", "region")}})
        best = None
        for r in self.routes:
            if r["method"].upper() != request.method or r["path"] != request.url.path:
                continue
            rq = {k: str(v) for k, v in (r.get("query") or {}).items()}
            if all(q.get(k) == v for k, v in rq.items()):
                if best is None or len(rq) > len(best.get("query") or {}):
                    best = r
        if best is None:
            return httpx.Response(404, json={"error": f"no recorded route for {request.method} {request.url.path} {q}"})
        return httpx.Response(best.get("status", 200), headers=best.get("headers") or {}, json=best["body"])


class Session:
    def __init__(self, platform: str, base_url: str, client_cls, recorded: Recorded | None = None,
                 token_fn: Callable[[], str] | None = None):
        self.platform = platform     # "procore" | "aps"
        self.base_url = base_url
        self.recorded = recorded
        self.parse_errors: list[dict] = []
        self.calls: list[str] = []
        token = "recorded-token" if recorded else (token_fn or (lambda: oauth.access_token(platform)))()
        httpx_args: dict[str, Any] = {"event_hooks": {"response": [self._log]}}
        if recorded:
            httpx_args["transport"] = httpx.MockTransport(recorded.handler)
        self.client = client_cls(base_url=base_url, token=token, timeout=httpx.Timeout(60.0),
                                 follow_redirects=True, raise_on_unexpected_status=False, httpx_args=httpx_args)

    def _log(self, response: httpx.Response) -> None:
        # method, host, path and status only: never headers, never bodies (tokens / PII)
        log.info("%s %s %s%s -> %s", self.platform, response.request.method, response.request.url.host,
                 response.request.url.path, response.status_code)

    # ------------------------------------------------------------------ sending
    def _send(self, kw: dict) -> httpx.Response:
        http = self.client.get_httpx_client()
        for attempt in range(MAX_RETRIES + 1):
            r = http.request(**kw)
            if r.status_code not in (429, 503) or attempt == MAX_RETRIES:
                return r
            wait = None
            if r.headers.get("Retry-After", "").isdigit():
                wait = int(r.headers["Retry-After"])
            elif r.headers.get("X-Rate-Limit-Reset", "").isdigit():       # Procore: unix seconds
                wait = max(0, int(r.headers["X-Rate-Limit-Reset"]) - int(time.time())) + 1
            wait = min(wait if wait is not None else 2 ** attempt * 5, 120) + random.uniform(0, 1.5)
            log.warning("%s rate-limited (%s) on %s; retrying in %.1fs", self.platform, r.status_code, kw["url"], wait)
            if not self.recorded:
                time.sleep(wait)
        return r

    def _check(self, r: httpx.Response, what: str) -> Any:
        if r.status_code >= 400:
            raise LiveError(f"{self.platform} {what} -> HTTP {r.status_code}: {store.redact(r.text[:400])}")
        return r.json() if r.content else None

    def call(self, op_module, **kwargs) -> tuple[Any, httpx.Headers]:
        """Call a generated operation (module from generated/<pkg>/api/calcgraph/). Returns (json, headers)."""
        name = op_module.__name__.rsplit(".", 1)[-1]
        kw = op_module._get_kwargs(**kwargs)
        self.calls.append(f"{kw['method'].upper()} {kw['url']}")
        r = self._send(kw)
        data = self._check(r, name)
        try:
            op_module._parse_response(client=self.client, response=r)
        except Exception as e:   # contract drift: keep the data, name the mismatch
            self.parse_errors.append({"operation": name, "error": f"{type(e).__name__}: {str(e)[:300]}"})
        return data, r.headers

    def request(self, method: str, url: str, *, params: dict | None = None, json_body: Any = None,
                headers: dict | None = None, what: str = "") -> tuple[Any, httpx.Headers]:
        """Hand-written endpoints (ACC RFIs / Submittals / Cost / Sheets, Forma) that have no official spec."""
        kw: dict[str, Any] = {"method": method.lower(), "url": url, "params": {k: v for k, v in (params or {}).items() if v is not None}}
        if json_body is not None:
            kw["json"] = json_body
        if headers:
            kw["headers"] = headers
        self.calls.append(f"{method.upper()} {url}")
        r = self._send(kw)
        return self._check(r, what or url), r.headers

    # ------------------------------------------------------------------ pagination
    def procore_pages(self, op_module, per_page: int = 100, max_pages: int = 50, **kwargs) -> list:
        """Procore v1: 1-based `page` + `per_page`; stop when the Link header has no rel=next or a page is short."""
        out: list = []
        for page in range(1, max_pages + 1):
            data, headers = self.call(op_module, page=page, per_page=per_page, **kwargs)
            items = data or []
            out += items
            link = headers.get("Link") or ""
            if len(items) < per_page or ('rel="next"' not in link and link):
                break
        return out

    def acc_pages(self, method: str, url: str, *, limit: int, params: dict | None = None, body: dict | None = None,
                  what: str = "", max_pages: int = 100, headers: dict | None = None) -> list:
        """ACC: limit/offset; response {results, pagination{limit, offset, totalResults, nextUrl?}}."""
        out: list = []
        offset = 0
        for _ in range(max_pages):
            if method.upper() == "GET":
                data, _ = self.request("GET", url, params={**(params or {}), "limit": limit, "offset": offset},
                                       headers=headers, what=what)
            else:
                data, _ = self.request(method, url, json_body={**(body or {}), "limit": limit, "offset": offset},
                                       headers=headers, what=what)
            res = (data or {}).get("results") or []
            out += res
            pg = (data or {}).get("pagination") or {}
            total = pg.get("totalResults")
            offset += len(res)
            if not res or (total is not None and offset >= total) or ("nextUrl" in pg and not pg.get("nextUrl")):
                break
        return out
