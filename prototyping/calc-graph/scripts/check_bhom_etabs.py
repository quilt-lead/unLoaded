"""Check the `bhom_etabs` analysis adapter without the desk.

    uv run python scripts/check_bhom_etabs.py            # all three parts (~30 s: part 1 re-runs the design)
    uv run python scripts/check_bhom_etabs.py --quick    # skip the PyNite fallback re-run

1. BRIDGE DOWN (a port nothing listens on): status says down; model objects are labelled
   `mock`; send_change writes a mock job; pull_results falls back to calc-graph's PyNite re-run
   and EVERY row is labelled `calcgraph-pynite`.
2. FAKE BRIDGE (a local HTTP server in this script that answers with the bridge's documented
   reply shapes - windows-bridge/calcgraph_bridge/app.py, csi.py, bhom.py; its NUMBERS ARE
   INVENTED): the csi route sends start/open/run, pulls OAPI-shaped rows, maps them to
   registry element ids and labels every row `csi-oapi`; the bhom route pushes BHoM JSON,
   pulls BHoM-shaped objects/results and labels every row `etabs-via-bhom`. This proves the
   HTTP client and the mapping, NOT the real bridge, BHoM or ETABS.
3. The design as a StructuralBundle -> BHoM JSON -> back: counts, releases, supports and a
   section property survive the BuildingFt(ft, in4) -> SI -> schema trip.
"""
from __future__ import annotations

import json
import os
import socket
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path[:0] = [os.path.join(ROOT, "backend"), ROOT]

from calcgraph.analysis.bhom_etabs import BhomEtabsAdapter  # noqa: E402
from calcgraph.schema.adapters.bhom_json import bhom_to_schema  # noqa: E402
from calcgraph.schema.structural import ResultSource  # noqa: E402

CHANGE = {"moved": {"2B": [5.0, 0.0]}}
FAILS: list[str] = []


def check(cond: bool, what: str):
    print(("  ok   " if cond else "  FAIL ") + what)
    if not cond:
        FAILS.append(what)


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def untagged(res: dict, keys) -> int:
    return sum(1 for k in keys for r in res.get(k, []) if not r.get("source"))


# ------------------------------------------------------------------ fake bridge
class Fake:
    """State + canned replies in the bridge's shapes. Invented numbers."""

    def __init__(self, adapter: BhomEtabsAdapter):
        self.calls: list[str] = []
        self.pushed: list[dict] = []
        frames = [o for o in adapter.mock.model_objects() if o.kind == "frame"]
        self.labels = {o.props["unique_name"]: (o.label, o.story) for o in frames}
        self.frames = frames[:6]
        self.bhom_model = adapter.to_bhom()

    def reply(self, method: str, path: str, body: dict) -> tuple[int, dict]:
        self.calls.append(f"{method} {path}")
        if path == "/health":
            return 200, {"ok": True, "service": "calcgraph-windows-bridge", "version": "fake"}
        if path == "/csi/start":
            return 200, {"started": {"ret": 0}, "attached": True, "product": "ETABS", "version": "fake",
                         "source": "real ETABS fake via CSI OAPI"}
        if path == "/csi/open":
            return 200, {"model": "C:\\calcgraph\\work\\x\\m.e2k", "summary": {"present_units": 4},
                         "source": "real ETABS fake via CSI OAPI"}
        if path == "/csi/run":
            return 200, {"saved": "m.edb", "seconds": 1.5, "source": "real ETABS fake via CSI OAPI"}
        if path == "/csi/call":
            lab, st = self.labels.get(body["inputs"]["Name"], ("", ""))
            return 200, {"ret": 0, "Label": lab, "Story": st, "source": "fake"}
        if path == "/csi/results":
            ff, dc = [], []
            for o in self.frames:
                n = o.props["unique_name"]
                for sta in (0.0, 15.0, 30.0):
                    ff.append({"Obj": n, "ObjSta": sta, "Elm": n, "ElmSta": sta, "LoadCase": "1.4D", "StepType": "",
                               "StepNum": 0.0, "P": -10.0, "V2": 5.0 - sta / 3, "V3": 0.0, "T": 0.0, "M2": 0.0,
                               "M3": 40.0})
                dc.append({"FrameName": n, "Ratio": 0.62, "RatioType": 1, "Location": 15.0, "ComboName": "1.4D",
                           "ErrorSummary": "", "WarningSummary": ""})
            jr = [{"Obj": "1@Base", "Elm": "1@Base", "LoadCase": "1.4D", "StepType": "", "StepNum": 0.0, "F1": 0.0,
                   "F2": 0.0, "F3": 120.0, "M1": 0.0, "M2": 0.0, "M3": 0.0}]
            sd = [{"Story": "Story1", "LoadCase": "EQX", "StepType": "", "StepNum": 0.0, "Direction": "X",
                   "Drift": 0.0071, "Label": "1", "X": 0.0, "Y": 0.0, "Z": 14.0}]
            return 200, {"cases": [], "combos": body.get("combos", []), "source": "real ETABS fake via CSI OAPI",
                         "frame_forces": ff, "joint_reactions": jr, "story_drifts": sd, "steel_dc": dc}
        if path == "/bhom/etabs/push":
            self.pushed = body["objects"]
            return 200, {"pushed": len(body["objects"]), "echoed": 0, "objects": [], "source": "real ETABS via BHoM fake"}
        if path == "/bhom/etabs/pull":
            if body.get("type"):
                t = body["type"]
                return 200, {"count": 0, "objects": [o for o in self.bhom_model if o["_t"] == t], "source": "fake"}
            rt = body["request"]["ResultType"]
            out = []
            if rt == "BarForce":
                for o in self.frames[:2]:
                    for pos in (0.0, 0.5, 1.0):
                        out.append({"_t": "BH.oM.Structure.Results.BarForce", "ObjectId": o.props["unique_name"],
                                    "ResultCase": "1.4D", "ModeNumber": 0, "TimeStep": 0.0, "Position": pos,
                                    "Divisions": 3, "FX": 0.0, "FY": 0.0, "FZ": 1000.0, "MX": 0.0, "MY": 2000.0,
                                    "MZ": 0.0})
            if rt == "StoreyDrifts":
                out.append({"_t": "BH.oM.Structure.Results.StoreyDrift", "ObjectId": "", "ResultCase": "EQX",
                            "ModeNumber": 0, "TimeStep": 0.0, "Storey": "Story1",
                            "Direction": {"_t": "BH.oM.Geometry.Vector", "X": 1.0, "Y": 0.0, "Z": 0.0}, "Ratio": 0.0065})
            return 200, {"count": len(out), "objects": out, "source": "fake"}
        return 404, {"error": "not_found", "detail": path}


def serve(fake: Fake) -> tuple[ThreadingHTTPServer, str]:
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _go(self, method):
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(n) or b"{}") if n else {}
            code, out = fake.reply(method, self.path, body)
            data = json.dumps(out).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            self._go("GET")

        def do_POST(self):
            self._go("POST")

    srv = ThreadingHTTPServer(("127.0.0.1", free_port()), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def main(quick: bool) -> int:
    print("1. bridge down")
    a = BhomEtabsAdapter(bridge_url=f"http://127.0.0.1:{free_port()}")
    st = a.bridge_status(force=True)
    check(not st["up"] and "not reachable" in st.get("error", ""), f"status down: {st.get('error')}")
    objs = a.model_objects()
    check(objs and all(o.props.get("source") == "mock" for o in objs), f"{len(objs)} model objects all labelled mock")
    job = a.send_change(None, CHANGE)
    check(job["source"] == "mock" and job["bridge"]["used"] is False, f"send_change -> mock job {job['job_id']}")
    if not quick:
        res = a.pull_results(job)
        n = sum(len(res.get(k, [])) for k in ("story_drifts", "frame_design", "base_reactions"))
        check(res["source"] == "calcgraph-pynite" and n > 0 and untagged(res, ("story_drifts", "frame_design",
                                                                             "base_reactions")) == 0,
              f"pull_results -> calcgraph-pynite fallback, {n} rows, all labelled; reason: {res['bridge']['fallback_reason']}")
    else:
        print("  skip PyNite fallback re-run (--quick)")

    print("2. FAKE bridge (invented numbers; proves client + mapping only)")
    probe = BhomEtabsAdapter()
    fake = Fake(probe)
    srv, url = serve(fake)
    try:
        a = BhomEtabsAdapter(bridge_url=url, route="csi")
        job = a.send_change(None, CHANGE)
        check(job["source"] == "csi-oapi" and job["status"] == "analysed",
              f"csi route: job {job['source']} / {job['status']}; calls {fake.calls[1:4]}")
        res = a.pull_results(job)
        rows = res["bar_forces"] + res["frame_design"] + res["story_drifts"] + res["node_reactions"]
        mapped = [r for r in res["frame_design"] if r["element_id"]]
        check(res["source"] == "csi-oapi" and rows and all(r["source"] == "csi-oapi" for r in rows),
              f"csi route: {len(rows)} result rows, all labelled csi-oapi")
        check(len(mapped) == len(res["frame_design"]) > 0,
              f"csi route: {len(mapped)}/{len(res['frame_design'])} D/C rows mapped to registry ids "
              f"(e.g. {mapped[0]['Label']}@{mapped[0]['Story']} -> {mapped[0]['element_id']})" if mapped else "csi mapping")
        check(res["bar_forces"][0]["mz"]["unit"] == "kip*ft", f"csi units from present_units 4: {res['bar_forces'][0]['mz']}")

        fake.calls.clear()
        a = BhomEtabsAdapter(bridge_url=url, route="bhom")
        job = a.send_change(None, CHANGE)
        check(job["source"] == "etabs-via-bhom" and job["status"] == "pushed" and len(fake.pushed) > 0,
              f"bhom route: pushed {len(fake.pushed)} BHoM objects ({job['note'][:60]}...)")
        res = a.pull_results(job)
        rows = res["bar_forces"] + res["story_drifts"]
        check(res["source"] == "etabs-via-bhom" and rows and all(r["source"] == "etabs-via-bhom" for r in rows),
              f"bhom route: {len(rows)} result rows, all labelled etabs-via-bhom")
        check(all(r["element_id"] for r in res["bar_forces"]),
              f"bhom route: bar forces mapped to registry ids via ETABSId fragments "
              f"({res['bar_forces'][0]['Label']}@{res['bar_forces'][0]['Story']} -> {res['bar_forces'][0]['element_id']})")
        check(res["conversion"]["lossless"], f"bhom route conversion report: {res['conversion']['unmapped'] or 'lossless'}")
    finally:
        srv.shutdown()

    print("3. design -> StructuralBundle -> BHoM JSON -> StructuralBundle")
    b1 = probe.structural_bundle()
    objs = probe.to_bhom()
    b2, rep = bhom_to_schema(json.loads(json.dumps(objs)), doc_sha="0" * 64, source=ResultSource.imported_file)
    c1, c2 = b1.counts(), b2.counts()
    check(c1 == c2, f"counts equal: {c1}")
    check(rep.lossless(), f"lossless: {rep.to_dict()['unmapped'] or 'yes'}")
    rel1 = sorted(b.releases.start.code() + b.releases.end.code() for b in b1.bars)
    rel2 = sorted(b.releases.start.code() + b.releases.end.code() for b in b2.bars)
    check(rel1 == rel2, f"end releases equal ({sum(1 for r in rel1 if 'R' in r)} released bars)")
    s1 = {s.designation: s for s in b1.sections}["W18X40"]
    s2 = {s.designation: s for s in b2.sections}["W18X40"]
    check(s1.Ix.close_to(s2.Ix, rel=1e-12), f"W18X40 Ix {s1.Ix.value} {s1.Ix.unit} == {s2.Ix.value:.6e} {s2.Ix.unit}")
    sup1 = sorted(s.fixity.code() for s in b1.supports)
    sup2 = sorted(s.fixity.code() for s in b2.supports)
    check(sup1 == sup2, f"supports equal: {dict((c, sup1.count(c)) for c in set(sup1))}")
    n1 = {n.name: n for n in b1.nodes}
    n2 = {r.ids.get('etabs'): n for n in b2.nodes for r in n.refs if r.ids.get('etabs')}
    k = next(n for n in n1 if n1[n].position.x and n in n2)
    check(abs(n1[k].position.x * 0.3048 - n2[k].position.x) < 1e-9,
          f"node {k}: {n1[k].position.x} ft (BuildingFt) == {n2[k].position.x:.4f} m (ModelM)")
    print("RESULT:", "PASS" if not FAILS else f"FAIL ({len(FAILS)}): " + "; ".join(FAILS))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main("--quick" in sys.argv))
