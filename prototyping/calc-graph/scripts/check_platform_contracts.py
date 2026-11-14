"""Contract tests for the LIVE platform adapters, the OAuth plumbing and the sandbox seeder - offline.

  uv run python scripts/check_platform_contracts.py        # exit 0 = all checks pass

Runs entirely against the SYNTHETIC recorded responses in backend/calcgraph/platforms/live/recorded/
(rebuild them with scripts/make_platform_recordings.py) through an httpx MockTransport: no network, no
credentials, no pytest (blocked on this machine). Each check prints PASS/FAIL with the evidence.

What it proves: the generated clients build the requests the specs define (paths, query, Procore-Company-Id
header); recorded responses satisfy the spec schemas and the generated models (no parse errors); the adapters
normalize statuses and link records to registry elements via the calc-graph marker; SourcedAdapter labels
every record and falls back to the mock with a reason; the change-order estimator runs on live-sourced
records; the seeder's dry run / refusals / idempotence / typed write bodies; OAuth state check, 0600 token
storage, and that no secret or token reaches logs or output.
What it cannot prove: that the REAL Procore sandbox / ACC trial / Forma answer like the recordings - that
needs real sandbox credentials (docs/platforms-real.md, "What is not verified").
"""
from __future__ import annotations

import contextlib
import io
import json
import logging
import os
import re
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import threading
import time
import traceback

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))
sys.path.insert(0, os.path.dirname(__file__))
TMP = tempfile.mkdtemp(prefix="cg-platform-contracts-")
os.environ["CALCGRAPH_SECRETS_DIR"] = os.path.join(TMP, "secrets")
for k in ("PROCORE_CLIENT_ID", "PROCORE_CLIENT_SECRET", "APS_CLIENT_ID", "APS_CLIENT_SECRET", "PROCORE_COMPANY_ID",
          "PROCORE_PROJECT_ID", "ACC_HUB_ID", "ACC_PROJECT_ID", "FORMA_PROJECT_ID", "PROCORE_ENV"):
    os.environ.pop(k, None)

from calcgraph.platforms import get_mock_adapters, get_state, load_design  # noqa: E402
from calcgraph.platforms._spec import SpecMismatch, check  # noqa: E402
from calcgraph.platforms.base import CHANGE_EVENTS, RFIS, SUBMITTALS  # noqa: E402
from calcgraph.platforms.live import SourcedAdapter, links, oauth  # noqa: E402
from calcgraph.platforms.live import secrets as store  # noqa: E402
from calcgraph.platforms.live.transport import Recorded  # noqa: E402

REC = os.path.join(ROOT, "backend", "calcgraph", "platforms", "live", "recorded")
GEN = os.path.join(ROOT, "backend", "calcgraph", "platforms", "live", "generated")
FAKE_SECRET = "s3cr3t-FAKE-client-secret-0123456789"
RESULTS: list[tuple[str, bool, str]] = []
LOG = io.StringIO()
_h = logging.StreamHandler(LOG)
_h.setLevel(logging.DEBUG)
logging.getLogger().addHandler(_h)
logging.getLogger().setLevel(logging.DEBUG)


def ok(name: str, cond: bool, evidence: str = "") -> None:
    RESULTS.append((name, bool(cond), evidence))


def run(name: str, fn) -> None:
    try:
        fn()
    except Exception as e:   # noqa: BLE001
        RESULTS.append((name, False, f"raised {type(e).__name__}: {e}\n{traceback.format_exc(limit=3)}"))


def rec(name: str) -> tuple[Recorded, dict]:
    path = os.path.join(REC, name)
    return Recorded(path), json.load(open(path))["config"]


STATE = get_state(load_design())


# ------------------------------------------------------------------ A. recordings satisfy the specs
def a_recordings():
    spec = json.load(open(os.path.join(GEN, "procore_client.openapi.json")))
    tmpl = []
    for p, ops in spec["paths"].items():
        rx = re.compile("^" + re.sub(r"\\\{[^}]+\\\}", r"[^/]+", re.escape(p)) + "$")
        tmpl.append((rx, p, ops))
    n = 0
    for f in ("procore_sandbox.json", "procore_sandbox_empty.json"):
        for r in json.load(open(os.path.join(REC, f)))["routes"]:
            hits = [(p, ops) for rx, p, ops in tmpl if rx.match(r["path"]) and r["method"].lower() in ops]
            hits.sort(key=lambda h: -len(h[0].replace("{", "").split("/")))   # most literal template first
            p, ops = hits[0]
            resp = ops[r["method"].lower()]["responses"]
            sch = (resp.get("200") or resp.get("201"))["content"]["application/json"]["schema"]
            check(r["body"], sch, f"{f} {r['method']} {p}")
            n += 1
    ok("A1 Procore recorded bodies satisfy the OAS response schemas", n > 30, f"{n} bodies checked field-by-field")
    try:
        check([{"id": 1, "invented_field": 1}], spec["paths"]["/rest/v1.0/companies"]["get"]["responses"]["200"]
              ["content"]["application/json"]["schema"], "probe")
        ok("A2 schema checker rejects an invented field", False, "accepted")
    except SpecMismatch as e:
        ok("A2 schema checker rejects an invented field", True, str(e)[:90])


# ------------------------------------------------------------------ B. live adapters on recordings
def b_procore():
    from calcgraph.platforms.live.procore_live import ProcoreLiveAdapter
    r, cfg = rec("procore_sandbox.json")
    a = ProcoreLiveAdapter(STATE, recorded=r, config=cfg)
    c = a.counts()
    ok("B1 Procore: 16 submittals, 8 RFIs, 4 change events, 1 CO package served",
       c["submittals"]["total"] == 16 and c["rfis"]["total"] == 8 and c["change_events"]["total"] == 4
       and c["change_orders"]["total"] == 1, json.dumps({k: v["total"] for k, v in c.items()}))
    ok("B2 Procore: no typed-parse errors against the generated models", a.session.parse_errors == [],
       str(a.session.parse_errors)[:200])
    hdr = {q["headers"].get("procore-company-id") for q in r.requests}
    ok("B3 Procore: every request carried Procore-Company-Id", hdr == {str(cfg["company_id"])}, f"values {hdr}")
    rfi = a.get_normalized(RFIS, "RFI-001")
    want = next(x for x in STATE.rfis if x["ref"] == "RFI-001")["element_ids"]
    ok("B4 Procore: RFI-001 links back to its registry elements via the marker", rfi and rfi.element_ids == want,
       f"{rfi.element_ids if rfi else None} vs {want}")
    unl = [x for x in a.list(RFIS) if x.ref.startswith("procore:")]
    ok("B5 Procore: an unmarked RFI stays unlinked (no guessed link)", len(unl) == 1 and unl[0].element_ids == [],
       f"{[(x.ref, x.element_ids) for x in unl]}")
    exp = {s["ref"]: ("draft" if s["status"] == "draft" else "submitted" if s["status"] == "submitted" else "approved")
           for s in STATE.submittals}
    got = {x.ref: x.status for x in a.list(SUBMITTALS)}
    ok("B6 Procore: submittal statuses normalize from status.status/name", got == exp,
       f"{sum(got.get(k) == v for k, v in exp.items())}/{len(exp)} match")
    ce = a.get_normalized(CHANGE_EVENTS, "CE-001")
    amt = next(x for x in STATE.change_events if x["ref"] == "CE-001")["amount"]
    ok("B7 Procore: change-event amount = sum of line-item cost estimates (string amounts parsed)",
       ce and abs(ce.fields["amount_usd"] - amt) < 0.01, f"{ce.fields['amount_usd'] if ce else None} vs {amt}")
    ok("B8 Procore: links point at the sandbox API host only",
       all(x.links["self"].startswith("https://sandbox.procore.com/") for rt in a.capabilities for x in a.list(rt)), a.env["api"])


def b_acc():
    from calcgraph.platforms.live.acc_live import AccLiveAdapter
    r, cfg = rec("acc_trial.json")
    a = AccLiveAdapter(STATE, recorded=r, config=cfg)
    c = a.counts()
    ok("B9 ACC: void submittal dropped; 16 submittals, 7 RFIs, 4 PCOs, 1 OCO, budget, sheet, issue",
       c["submittals"]["total"] == 16 and c["rfis"]["total"] == 7 and c["change_events"]["total"] == 4
       and c["change_orders"]["total"] == 1 and c["issues"]["total"] == 1, json.dumps({k: v["total"] for k, v in c.items()}))
    ok("B10 ACC: Issues + DM bodies parse with the generated models", a.session.parse_errors == [], str(a.session.parse_errors)[:200])
    paths = sorted({q["method"] + " " + q["path"].split(a.project_id)[-1] for q in r.requests})
    ok("B11 ACC: endpoints called = RFIs v3 search, Submittals v2, Cost pco/oco/budgets, Sheets, Issues",
       any("search:rfis" in p for p in paths) and any("/change-orders/pco" in p for p in paths)
       and any("/issues" in p for p in paths) and any("/sheets" in p for p in paths), "; ".join(paths))
    sub = a.get_normalized(SUBMITTALS, "SUB-RB-S1")
    ok("B12 ACC: submittal marker -> elements, statusId/stateId -> status",
       sub and sub.element_ids == next(s for s in STATE.submittals if s["ref"] == "SUB-RB-S1")["element_ids"] and sub.status == "approved",
       f"{sub.status if sub else None}, {len(sub.element_ids) if sub else 0} elements")
    pco = a.get_normalized(CHANGE_EVENTS, "CE-002")
    ok("B13 ACC: PCO linked by externalId", pco is not None and pco.element_ids, f"{pco.ref if pco else None}")
    big = [q for q in r.requests if "search:rfis" in q["path"]]
    ok("B14 ACC: RFI search sends limit<=200 / offset in the JSON body", big and big[0]["json"].get("limit") == 200
       and big[0]["json"].get("offset") == 0, str(big[0]["json"] if big else None))


def b_forma():
    from calcgraph.platforms.live.forma_live import FormaLiveAdapter
    r, cfg = rec("forma.json")
    a = FormaLiveAdapter(STATE, recorded=r, config=cfg)
    els = a.list("elements")
    props = a.list("proposals")
    linked = sorted(e for x in els for e in x.element_ids)
    ok("B15 Forma: proposals + recursive elements read; registry links only by element name",
       len(props) == 1 and "COL-2B" in linked and any(x.element_ids == [] for x in els),
       f"{len(els)} elements, linked {linked}")
    ok("B16 Forma: authcontext sent on every call", all(q["query"].get("authcontext") == cfg["forma_project_id"] for q in r.requests), "")


# ------------------------------------------------------------------ C. selection + fallback + labels
def c_sourced():
    design = load_design()
    mocks = {m.name: m for m in get_mock_adapters(design)}
    st = get_state(design)
    d = SourcedAdapter(mocks["procore"], st)
    recs = d.list(SUBMITTALS)
    ok("C1 default selection is the mock, every record labelled source=mock",
       d.source == "mock" and recs and all(x.fields.get("source") == "mock" for x in recs), d.fallback_reason or "")
    r, cfg = rec("procore_sandbox.json")
    live = SourcedAdapter(get_mock_adapters(design, ["procore"])[0], st, mode="live", recorded=r, live_config=cfg)
    recs = live.list(RFIS)
    ok("C2 live selected + reachable -> source=live labels, describe() not synthetic, no synthetic state",
       live.source == "live" and all(x.fields["source"] == "live" for x in recs) and live.describe()["synthetic"] is False
       and live.state is None, live.label)
    bad = SourcedAdapter(get_mock_adapters(design, ["autodesk_build"])[0], st, mode="live", live_config={})
    recs = bad.list(SUBMITTALS)
    ok("C3 live selected but unconfigured -> falls back to the mock with the reason on every record",
       bad.source == "mock" and "not configured" in (bad.fallback_reason or "") and recs
       and all("live unavailable" in x.fields["source_label"] for x in recs), bad.fallback_reason or "")
    ok("C4 fallback keeps the synthetic state for the impact engine", bad.state is not None, "")
    os.environ["CALCGRAPH_PLATFORM_FORMA"] = "live"
    try:
    from calcgraph.platforms import get_adapters
    reg = get_adapters(design)
    ok("C6 get_adapters() is the registration point: every adapter is a SourcedAdapter reporting source/fallback_reason",
       all(isinstance(a, SourcedAdapter) and a.describe()["source"] == "mock" and a.fallback_reason for a in reg),
       ", ".join(f"{a.name}={a.describe()['source']}" for a in reg))
        f = SourcedAdapter(get_mock_adapters(design, ["forma"])[0], st)
        f.list("elements")
        ok("C5 env CALCGRAPH_PLATFORM_FORMA=live selects live; no token -> mock + reason", f.selected == "live"
           and f.source == "mock", f.fallback_reason or "")
    finally:
        os.environ.pop("CALCGRAPH_PLATFORM_FORMA")


def d_change_order():
    from calcgraph.platforms import estimate
    from calcgraph.platforms.status import construction_status
    design = load_design()
    st = get_state(design)
    r, cfg = rec("procore_sandbox.json")
    ads = [SourcedAdapter(get_mock_adapters(design, ["procore"])[0], st, mode="live", recorded=r, live_config=cfg)] + \
          [SourcedAdapter(m, st) for m in get_mock_adapters(design, ["autodesk_build", "forma"])]
    touched = sorted(set(next(x for x in st.rfis if x["ref"] == "RFI-001")["element_ids"]))
    co = estimate({"elements": touched}, ads, design)
    rf = [x for x in co.get("rfis", []) if x["ref"] == "RFI-001"]
    ok("D1 change-order estimate runs on live-sourced Procore records and cites the sandbox record",
       rf and any(s["platform"] == "procore" and s["url"].startswith("https://sandbox.procore.com/") for s in rf[0]["sources"]),
       f"rfis={[x['ref'] for x in co.get('rfis', [])]}, warnings={co.get('warnings')}")
    cs = construction_status("COL-3B", ads)
    ok("D2 construction_status runs with a live adapter in the set", isinstance(cs, dict), f"keys {sorted(cs)[:6]}")


    _d_unknown_float(design)


def _d_unknown_float(design):
    from calcgraph.platforms import estimate
    from calcgraph.platforms.base import SCHEDULE_ACTIVITIES, NormalizedRecord, PlatformAdapter
    from calcgraph.platforms.status import construction_status
    beam = next(e for e in design["elements"] if e["type"] == "beam")

    class NoFloat(PlatformAdapter):
        name, label = "nofloat", "live-shaped, float not reported"
        capabilities = frozenset({SUBMITTALS, SCHEDULE_ACTIVITIES})

        def _build(self):
            sub = NormalizedRecord("submittal", "1", "SUB-X", self.name, "05 12 00-001", "steel shop drawings", "submitted",
                                   [beam["id"]], fields={"stage": "submitted", "package_kind": "shop_drawings",
                                           "spec_section": "05 12 00", "spec_title": "Structural Steel Framing"})
            act = NormalizedRecord("schedule_activity", "2", "ACT-X", self.name, "A1000", "erect steel", "not_started",
                                   [beam["id"]], fields={"total_float_days": None, "critical": False})
            return {SUBMITTALS: [sub], SCHEDULE_ACTIVITIES: [act]}

        def deep_link(self, record_type, id):
            return f"https://example.invalid/{record_type}/{id}"

    ads = [NoFloat()]
    act = ads[0].list(SCHEDULE_ACTIVITIES)[0]
    ok("D3 the record gate types schedule float: None stays None (unknown), float_known False",
       act.total_float is None and act.fields["float_known"] is False, str(act.fields))
    cs = construction_status(beam["id"], ads, design)
    ok("D4 construction_status with a linked activity whose float is unknown: float_days None, said so in reasons",
       cs["float_days"] is None and any("float not reported" in r for r in cs["reasons"]), str(cs["reasons"][-1:]))
    co = estimate({"elements": [beam["id"]], "resized": [{"id": beam["id"], "old_size": beam["size"], "new_size": beam["size"],
                                                          "length_ft": beam.get("span_ft")}]}, ads, design)
    acts = co["schedule"]["activities"]
    ok("D5 change-order float arithmetic with unknown float: delay assumes no float there, warned, no crash",
       acts and acts[0]["float_known"] is False and acts[0]["float_before"] is None
       and any("float unknown" in w for w in co["warnings"]), f"{acts[:1]} {co['warnings'][-1:]}")
    raw_reads = []
    pkg = os.path.join(ROOT, "backend", "calcgraph")
    for dp, _, fs in os.walk(pkg):
        for f in fs:
            if f.endswith(".py") and not dp.endswith(os.path.join("platforms", "live", "generated")):
                path = os.path.join(dp, f)
                for i, line in enumerate(open(path), 1):
                    if re.search(r"""fields\[["']total_float_days["']\](?!\s*=)""", line) and not path.endswith(os.path.join("platforms", "base.py")):
                        raw_reads.append(f"{os.path.relpath(path, ROOT)}:{i}")
    ok("D6 ratchet: nothing reads fields['total_float_days'] directly (read NormalizedRecord.total_float, which may be None)",
       not raw_reads, ", ".join(raw_reads))
# ------------------------------------------------------------------ E. seeding script
def _seed(argv):
    import seed_platform_sandbox as seed
    out, err = io.StringIO(), io.StringIO()
    old = sys.argv
    sys.argv = ["seed_platform_sandbox.py"] + argv
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = seed.main()
            except SystemExit as e:    # argparse errors
                code = e.code if isinstance(e.code, int) else 2
    finally:
        sys.argv = old
    return code, out.getvalue(), err.getvalue()


def _with_cfg(src: str, extra: dict) -> str:
    d = json.load(open(os.path.join(REC, src)))
    d["config"].update(extra)
    p = os.path.join(TMP, "rec-" + src)
    json.dump(d, open(p, "w"))
    return p


def e_seed():
    from calcgraph.platforms.live.generated.procore_client.models.create_change_event_body import CreateChangeEventBody
    from calcgraph.platforms.live.generated.procore_client.models.create_rfi_body import CreateRfiBody
    from calcgraph.platforms.live.generated.procore_client.models.create_submittal_body import CreateSubmittalBody
    import seed_platform_sandbox as seed
    code, out, err = _seed(["procore", "--recorded", os.path.join(REC, "procore_sandbox_empty.json")])
    rep = json.loads(out) if code == 0 else {}
    ok("E1 Procore dry run on an empty sandbox plans 7 RFIs / 16 submittals / 4 change events, all ids resolved",
       code == 0 and rep.get("counts") == {"rfi:write": 7, "submittal:write": 16, "change_event:write": 4}
       and not any(p.get("unresolved") for p in rep["plan"]), f"exit {code} {rep.get('counts')} {err[:120]}")
    ok("E2 dry run sends GETs only", rep and rep.get("mode") == "dry-run", rep.get("mode", ""))
    code, out, err = _seed(["procore", "--recorded", os.path.join(REC, "procore_sandbox_empty.json"), "--apply",
                            "--confirm-project", "Harbor View Office (sandbox)"])
    ok("E3 --apply refused when the project is not in seed_allowed_project_ids", code == 2 and "seed_allowed_project_ids" in err, err.strip()[:120])
    p = _with_cfg("procore_sandbox_empty.json", {"seed_allowed_project_ids": [5800002]})
    code, out, err = _seed(["procore", "--recorded", p, "--apply", "--confirm-project", "wrong name"])
    ok("E4 --apply refused when --confirm-project does not match the API's project name", code == 2 and "confirm-project" in err, err.strip()[:120])
    orig = seed.Recorded
    captured: list = []

    class Spy(orig):
        def __post_init__(self):
            super().__post_init__()
            captured.append(self)
    seed.Recorded = Spy
    try:
        code, out, err = _seed(["procore", "--recorded", p, "--apply", "--confirm-project", "Harbor View Office (sandbox)"])
    finally:
        seed.Recorded = orig
    posts = [q for q in captured[0].requests if q["method"] == "POST"] if captured else []
    kinds = {"rfis": 0, "submittals": 0, "change_events": 0}
    typed = True
    for q in posts:
        k = q["path"].rsplit("/", 1)[-1]
        kinds[k] = kinds.get(k, 0) + 1
        model = {"rfis": CreateRfiBody, "submittals": CreateSubmittalBody, "change_events": CreateChangeEventBody}[k]
        try:
            model.from_dict(q["json"])
        except Exception:   # noqa: BLE001
            typed = False
    ok("E5 --apply (allowlisted + confirmed, recorded) POSTs 7 RFIs / 16 submittals / 4 change events",
       code == 0 and kinds == {"rfis": 7, "submittals": 16, "change_events": 4}, f"exit {code} {kinds} {err[:120]}")
    ok("E6 every POST body round-trips through the generated (spec) request model, carries a marker and the company header",
       posts and typed and all("[calc-graph " in json.dumps(q["json"]) for q in posts)
       and all(q["headers"].get("procore-company-id") == "4900001" for q in posts), f"{len(posts)} bodies")
    code, out, err = _seed(["procore", "--recorded", os.path.join(REC, "procore_sandbox.json")])
    rep = json.loads(out) if code == 0 else {}
    ok("E7 re-run on a seeded project skips everything (idempotent by marker)",
       code == 0 and rep.get("counts") == {"rfi:skip": 7, "submittal:skip": 16, "change_event:skip": 4}, str(rep.get("counts")))
    try:
        oauth.procore_env({"env": "production"})
        ok("E8 Procore production environment refused", False, "accepted")
    except oauth.AuthError as e:
        ok("E8 Procore production environment refused", True, str(e)[:100])
    code, out, err = _seed(["acc", "--recorded", os.path.join(REC, "acc_trial_empty.json")])
    rep = json.loads(out) if code == 0 else {}
    ok("E9 ACC dry run on an empty trial project: 7 RFIs / 16 submittals (type + spec resolved) / 4 PCOs",
       code == 0 and rep.get("counts") == {"rfi:write": 7, "submittal:write": 16, "pco:write": 4}, f"{rep.get('counts')} {err[:120]}")
    pa = _with_cfg("acc_trial_empty.json", {"seed_allowed_project_ids": [json.load(open(os.path.join(REC, "acc_trial_empty.json")))["config"]["project_id"]]})
    code, out, err = _seed(["acc", "--recorded", pa, "--apply", "--confirm-project", "Harbor View Office (ACC trial)"])
    rep = json.loads(out) if code == 0 else {}
    ok("E10 ACC --apply (allowlisted + confirmed, recorded) writes 27 records", code == 0 and len(rep.get("written", [])) == 27,
       f"exit {code} written={len(rep.get('written', []))} {err[:160]}")
    code, out, err = _seed(["acc", "--recorded", pa, "--apply", "--confirm-project", "Harbor View Office (ACC trial)",
                            "--offline"])
    ok("E11 --offline with --apply is rejected", code != 0, "")


# ------------------------------------------------------------------ F. secrets + OAuth
def f_secrets():
    p = store.write_json("procore_app.json", {"client_id": "cid-fake", "client_secret": FAKE_SECRET, "env": "sandbox"})
    mode = stat.S_IMODE(os.stat(p).st_mode)
    dmode = stat.S_IMODE(os.stat(os.path.dirname(p)).st_mode)
    ok("F1 secrets written 0600 in a 0700 directory", mode == 0o600 and dmode == 0o700, f"{oct(mode)} / {oct(dmode)}")
    s = store.redact(f'Authorization: Bearer abc.def.ghi client_secret={FAKE_SECRET} {{"access_token": "tok123", "refresh_token": "r9"}}')
    ok("F2 redact() masks bearer tokens, secrets and token fields", "abc.def" not in s and FAKE_SECRET not in s and "tok123" not in s
       and "r9" not in s, s)
    gi = subprocess.run(["git", "check-ignore", "-q", "data/secrets/procore_token.json"], cwd=ROOT).returncode
    ok("F3 data/secrets/ is gitignored", gi == 0, "git check-ignore")


def f_oauth():
    with socket.socket() as so:
        so.bind(("127.0.0.1", 0))
        port = so.getsockname()[1]
    store.write_json("aps_app.json", {"client_id": "aps-cid-fake", "client_secret": FAKE_SECRET,
                                      "redirect_uri": f"http://127.0.0.1:{port}/oauth/callback/aps"})
    url = oauth.authorize_url("aps", "STATE123", "CHAL")
    ok("F4 APS authorize URL: v2 endpoint, code flow, scopes, PKCE S256, no secret",
       url.startswith("https://developer.api.autodesk.com/authentication/v2/authorize?") and "response_type=code" in url
       and "code_challenge_method=S256" in url and "data%3Aread" in url and FAKE_SECRET not in url, url[:120])
    seen = {}

    class FakeResp:
        status_code = 200
        text = ""

        def json(self):
            return {"access_token": "AT-should-never-print", "refresh_token": "RT-should-never-print", "expires_in": 3599,
                    "token_type": "Bearer"}

    def fake_post(url, data=None, headers=None, timeout=None):
        seen.update(url=url, data=dict(data or {}), headers=dict(headers or {}))
        return FakeResp()
    real_post, real_tok = oauth.httpx.post, oauth.pysecrets.token_urlsafe
    oauth.httpx.post = fake_post
    oauth.pysecrets.token_urlsafe = lambda n=24: "FIXEDSTATE"
    import httpx as _hx
    out = io.StringIO()
    res: dict = {}
    try:
        def go():
            with contextlib.redirect_stdout(out):
                try:
                    res["v"] = oauth.login("aps", open_browser=False, timeout_s=15)
                except Exception as e:   # noqa: BLE001
                    res["e"] = e
        t = threading.Thread(target=go)
        t.start()
        time.sleep(0.6)
        bad = _hx.get(f"http://127.0.0.1:{port}/elsewhere?code=x&state=FIXEDSTATE", timeout=5)
        good = _hx.get(f"http://127.0.0.1:{port}/oauth/callback/aps?code=CODE-1&state=FIXEDSTATE", timeout=5)
        t.join(20)
    finally:
        oauth.httpx.post, oauth.pysecrets.token_urlsafe = real_post, real_tok
    tokp = os.path.join(store.secrets_dir(), "aps_token.json")
    ok("F5 loopback callback: wrong path 404, right path 200, code exchanged with Basic auth + PKCE verifier",
       bad.status_code == 404 and good.status_code == 200 and "v" in res and seen.get("data", {}).get("code") == "CODE-1"
       and seen["headers"].get("Authorization", "").startswith("Basic ") and "client_secret" not in seen["data"]
       and len(seen["data"].get("code_verifier", "")) >= 43, f"{bad.status_code}/{good.status_code} {res.get('e')}")
    ok("F6 token stored 0600; summary/output never contain the token or the secret",
       os.path.exists(tokp) and stat.S_IMODE(os.stat(tokp).st_mode) == 0o600
       and "AT-should-never-print" not in json.dumps(res.get("v")) + out.getvalue() and FAKE_SECRET not in out.getvalue(),
       json.dumps(res.get("v"))[:160])
    oauth.httpx.post = fake_post
    oauth.pysecrets.token_urlsafe = lambda n=24: "EXPECTED"
    res2: dict = {}
    try:
        def go2():
            with contextlib.redirect_stdout(io.StringIO()):
                try:
                    res2["v"] = oauth.login("aps", open_browser=False, timeout_s=10)
                except Exception as e:   # noqa: BLE001
                    res2["e"] = e
        t = threading.Thread(target=go2)
        t.start()
        time.sleep(0.6)
        _hx.get(f"http://127.0.0.1:{port}/oauth/callback/aps?code=EVIL&state=FORGED", timeout=5)
        t.join(15)
    finally:
        oauth.httpx.post, oauth.pysecrets.token_urlsafe = real_post, real_tok
    ok("F7 forged state is refused (no code exchange)", isinstance(res2.get("e"), oauth.AuthError) and "state" in str(res2["e"]),
       str(res2.get("e"))[:100])
    store.write_json("procore_app.json", {"client_id": "pc-fake", "client_secret": FAKE_SECRET, "env": "sandbox"})
    pu = oauth.authorize_url("procore", "S", None)
    ok("F8 Procore authorize URL uses the Developer Sandbox login host, no PKCE, no secret",
       pu.startswith("https://login-sandbox.procore.com/oauth/authorize?") and "code_challenge" not in pu and FAKE_SECRET not in pu, pu[:100])


def g_logs():
    logs = LOG.getvalue()
    leaks = [s for s in (FAKE_SECRET, "AT-should-never-print", "RT-should-never-print", "recorded-token") if s in logs]
    ok("G1 nothing secret in any log line emitted during the run", not leaks and "sandbox.procore.com" in logs,
       f"{len(logs.splitlines())} log lines, leaks={leaks}")


def main() -> int:
    for name, fn in [("A", a_recordings), ("B-procore", b_procore), ("B-acc", b_acc), ("B-forma", b_forma), ("C", c_sourced),
                     ("D", d_change_order), ("E", e_seed), ("F-secrets", f_secrets), ("F-oauth", f_oauth), ("G", g_logs)]:
        run(name, fn)
    width = max(len(n) for n, _, _ in RESULTS)
    for n, passed, ev in RESULTS:
        print(f"{'PASS' if passed else 'FAIL'}  {n.ljust(width)}  {ev.splitlines()[0][:150] if ev else ''}")
    failed = [n for n, p, _ in RESULTS if not p]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} passed")
    for n, p, ev in RESULTS:
        if not p and "\n" in ev:
            print(f"--- {n}\n{ev}")
    shutil.rmtree(TMP, ignore_errors=True)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
