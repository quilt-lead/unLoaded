"""`bhom_etabs` analysis adapter: real ETABS through the Windows bridge, the mock when not.

The bridge (windows-bridge/, FastAPI on the office Windows desk, reached at
http://127.0.0.1:8765 through `windows-bridge/bridge.sh tunnel`) exposes two real routes:

- route "csi"  (default; complete in the bridge today): POST /csi/start -> /csi/open with the
  .e2k this adapter writes (the changed geometry, sizes carried) -> /csi/run -> /csi/results.
  Values come straight from CSI's OAPI: source `csi-oapi`.
- route "bhom": POST /bhom/etabs/push with the model as BHoM JSON (schema/adapters/bhom_json.py)
  and POST /bhom/etabs/pull with BHoM result requests. Values: source `etabs-via-bhom`.
  The bridge has no "run analysis" call for the BHoM adapter's ETABS session yet, so a BHoM
  push is NOT analysed by this adapter; pull_results on that route reads whatever results the
  ETABS model already holds (none, for a fresh push) and says so.

When the bridge does not answer, or answers without the software (503 not_installed), every
call falls back to the mock `EtabsAdapter` (analysis/etabs.py): model objects are design.json
mapped to ETABS-style objects (source `mock`), results are calc-graph's own PyNite re-run
(source `calcgraph-pynite`). EVERY object and result row carries `source` (+ `source_detail`);
the job / results dict carries `bridge` (what was tried and why it fell back). Nothing here
may present a mock or PyNite number as an ETABS one.

    from calcgraph.analysis.bhom_etabs import BhomEtabsAdapter
    a = BhomEtabsAdapter()                     # CALCGRAPH_BRIDGE_URL, CALCGRAPH_BRIDGE_ROUTE
    a.bridge_status()                          # {"up": False, "error": "...", ...}
    job = a.send_change(None, {"moved": {"2B": [5, 0]}})
    res = a.pull_results(job)                  # res["source"] in csi-oapi / etabs-via-bhom / calcgraph-pynite
    bundle = a.structural_bundle()             # the design as schema.structural.StructuralBundle
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.request

from ..schema.adapters.bhom_json import bhom_to_schema, schema_to_bhom
from ..schema.frames import BuildingFt, Point3
from ..schema.models import Method, ModelEvidence, Provenance
from ..schema.structural import (AnalyticalBar, AnalyticalNode, BarForceResult, CombinationTerm, EndReleases,
                                 ExternalRef, Fixity6, LoadCase, LoadCombination, LoadNature, MaterialGrade,
                                 MaterialKind, NodeReactionResult, ResultKind, ResultRequest, ResultSource,
                                 SectionPropertySet, SectionShape, StoreyDriftResult, StructuralBundle,
                                 StructuralUsage, Support, UtilisationResult)
from ..schema.units import Quantity
from . import etabs as mock_etabs
from .base import DESIGN_PATH, SOURCE_DETAIL, AnalysisAdapter, AnalysisObject, tag_source

DEFAULT_URL = "http://127.0.0.1:8765"
ENGINE = "calcgraph.analysis.bhom_etabs/1.0"
BUILDING = "synthetic-v2"
# CSI eUnits (ETABS OAPI enum, from memory of the API reference - unverified against a desk)
CSI_UNITS = {1: ("lbf", "in"), 2: ("lbf", "ft"), 3: ("kip", "in"), 4: ("kip", "ft"), 5: ("kN", "mm"), 6: ("kN", "m"),
             9: ("N", "mm"), 10: ("N", "m")}
CSI_UNIT_NAMES = {"lb_in_F": 1, "lb_ft_F": 2, "kip_in_F": 3, "kip_ft_F": 4, "kN_mm_C": 5, "kN_m_C": 6, "N_mm_C": 9,
                  "N_m_C": 10}
NATURE = {"Dead": LoadNature.dead, "SDL": LoadNature.superimposed_dead, "Live": LoadNature.live,
          "Lr": LoadNature.roof_live, "EQX": LoadNature.seismic, "EQY": LoadNature.seismic, "WX": LoadNature.wind,
          "WY": LoadNature.wind}
USAGE = {"COLUMN": StructuralUsage.column, "BEAM": StructuralUsage.beam, "BRACE": StructuralUsage.brace}


class BridgeError(RuntimeError):
    """The bridge did not answer, or answered with an error (status + body kept)."""

    def __init__(self, msg: str, status: int | None = None, body: dict | None = None):
        super().__init__(msg)
        self.status, self.body = status, body or {}


class BridgeClient:
    """Tiny JSON-over-HTTP client for windows-bridge/calcgraph_bridge/app.py."""

    def __init__(self, url: str | None = None, timeout: float = 5.0, long_timeout: float = 900.0):
        self.url = (url or os.environ.get("CALCGRAPH_BRIDGE_URL") or DEFAULT_URL).rstrip("/")
        self.timeout, self.long_timeout = timeout, long_timeout

    def call(self, method: str, path: str, body: dict | None = None, long: bool = False) -> dict:
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(self.url + path, data=data, method=method,
                                     headers={"Content-Type": "application/json"} if data else {})
        try:
            with urllib.request.urlopen(req, timeout=self.long_timeout if long else self.timeout) as r:
                return json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            try:
                b = json.loads(e.read() or b"{}")
            except ValueError:
                b = {}
            raise BridgeError(f"{method} {path}: HTTP {e.code} {b.get('error', '')} {b.get('detail', '')}".strip(),
                              e.code, b) from None
        except (urllib.error.URLError, OSError, TimeoutError) as e:
            raise BridgeError(f"{method} {path}: bridge not reachable at {self.url} ({getattr(e, 'reason', e)})") from None

    def get(self, path):
        return self.call("GET", path)

    def post(self, path, body=None, long=False):
        return self.call("POST", path, body or {}, long)


def _sha_of_design(design) -> str:
    if isinstance(design, dict):
        return hashlib.sha256(json.dumps(design, sort_keys=True).encode()).hexdigest()
    path = design or DESIGN_PATH
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


_tag = tag_source


# ======================================================================== design -> structural schema
def structural_from_objects(objs: list[AnalysisObject], doc_sha: str, building: str = BUILDING) -> StructuralBundle:
    """The mock ETABS objects of a design (analysis/etabs.build_objects) as a StructuralBundle in
    BuildingFt(building). Every fact's evidence is the ETABS-style object in design.json."""
    from synth.v2 import aisc

    frame = BuildingFt(building=building)
    out: dict[str, list] = {c: [] for c in StructuralBundle.COLLECTIONS}

    def prov(o: AnalysisObject, what: str) -> Provenance:
        key = f"etabs:{o.kind}:{o.label}" + (f"@{o.story}" if o.story else "")
        return Provenance(evidence=[ModelEvidence(doc_sha=doc_sha, global_id=key, entity=f"ETABS {o.kind} (mock)",
                                                  text=what[:200])],
                          rule_id=f"etabs-objects->structural/{o.kind}", rule_version="1.0", engine=ENGINE,
                          method=Method.deterministic, confidence=1.0)

    def refs(o: AnalysisObject, uid: str | None = None) -> list[ExternalRef]:
        ids = {"etabs_label": o.label}
        if o.story:
            ids["etabs_story"] = o.story
        if uid:
            ids["etabs"] = uid
        return [ExternalRef(system="etabs", type=o.kind, name=o.label, ids=ids)]

    for o in objs:
        p = o.props
        if o.kind == "material":
            out["materials"].append(MaterialGrade(
                id=f"mat:{o.label}", name=o.label, refs=refs(o), provenance=prov(o, o.label), kind=MaterialKind.steel,
                standard="ASTM A992" if o.label.startswith("A992") else "ASTM A500", grade=p["grade"],
                E=Quantity(value=p["E_ksi"], unit="ksi"), nu=Quantity(value=p["nu"], unit="1"),
                unit_weight=Quantity(value=p["weight_kcf"] * 1000.0, unit="pcf"),
                fy=Quantity(value=p["Fy_ksi"], unit="ksi"), fu=Quantity(value=p["Fu_ksi"], unit="ksi"),
                fy_expected=Quantity(value=p["Fye_ksi"], unit="ksi"), fu_expected=Quantity(value=p["Fue_ksi"], unit="ksi")))
        elif o.kind == "section":
            a = aisc.get(o.label)
            qq = lambda k, u: Quantity(value=a[k], unit=u) if a.get(k) is not None else None  # noqa: E731
            hss = o.label.startswith("HSS")
            out["sections"].append(SectionPropertySet(
                id=f"sec:{o.label}", name=o.label, refs=refs(o), provenance=prov(o, o.label), designation=o.label,
                shape=SectionShape.rect_hollow if hss else SectionShape.i, material_id=f"mat:{p['material']}",
                catalogue="AISC Shapes Database v16.0 (synth/v2/data/aisc_v16_subset.csv)",
                fabrication="cold-formed" if hss else "hot-rolled",
                d=qq("d", "in"), bf=qq("bf", "in") if not hss else qq("B", "in"), tw=qq("tw", "in"), tf=qq("tf", "in"),
                t_design=qq("tdes", "in"), A=qq("A", "in2"), Ix=qq("Ix", "in4"), Iy=qq("Iy", "in4"), J=qq("J", "in4"),
                Cw=qq("Cw", "in6"), Sx=qq("Sx", "in3"), Sy=qq("Sy", "in3"), Zx=qq("Zx", "in3"), Zy=qq("Zy", "in3"),
                rx=qq("rx", "in"), ry=qq("ry", "in"), weight_per_length=qq("W", "plf")))
        elif o.kind == "point":
            nid = f"node:{o.label}@{o.story}"
            sup = None
            if any(p["restraint"]):
                sup = f"sup:{o.label}@{o.story}"
                out["supports"].append(Support(id=sup, node_id=nid, fixity=Fixity6.from_flags(p["restraint"]),
                                               refs=refs(o), provenance=prov(o, "PointObj.GetRestraint")))
            out["nodes"].append(AnalyticalNode(
                id=nid, name=f"{o.label}@{o.story}", refs=refs(o, f"{o.label}@{o.story}"),
                position=Point3(frame=frame, x=p["x_ft"], y=p["y_ft"], z=p["z_ft"]), support_id=sup,
                physical_id=o.element_id, story=o.story or "", provenance=prov(o, "PointObj.GetCoordCartesian")))
    for o in objs:
        p = o.props
        if o.kind == "frame":
            pts = o.raw["FrameObj.GetPoints"]
            rel = o.raw["FrameObj.GetReleases"]
            out["bars"].append(AnalyticalBar(
                id=f"bar:{p['unique_name']}", name=f"{o.label}@{o.story}", refs=refs(o, p["unique_name"]),
                start_node=f"node:{pts['Point1']}", end_node=f"node:{pts['Point2']}", section_id=f"sec:{p['section']}",
                orientation_angle=Quantity(value=p.get("angle_deg", 0.0), unit="deg"),
                releases=EndReleases.from_etabs_released(rel["II"], rel["JJ"], "PINNED" if p.get("release") else ""),
                usage=USAGE[p["etabs_type"]], physical_id=o.element_id, story=o.story or "",
                provenance=prov(o, f"{o.label} {p['section']}")))
        elif o.kind == "load_pattern":
            out["load_cases"].append(LoadCase(
                id=f"case:{o.label}", name=o.label, refs=refs(o), nature=NATURE.get(o.label, LoadNature.other),
                self_weight_multiplier=Quantity(value=p["self_weight"], unit="1"), description=p.get("description", ""),
                provenance=prov(o, p.get("description", ""))))
    for o in objs:
        if o.kind == "combo":
            p = o.props
            out["combinations"].append(LoadCombination(
                id=f"combo:{o.label}", name=o.label, refs=refs(o), group=p.get("group", ""), code_ref=p.get("code", ""),
                terms=[CombinationTerm(case_id=f"case:{c}", factor=Quantity(value=f, unit="1")) for c, f in p["terms"]],
                provenance=prov(o, p.get("code", ""))))
    return StructuralBundle(source=f"design.json via mock ETABS objects ({ENGINE})",
                            model_frame=f"BuildingFt({building})", **out)


# ======================================================================== the adapter
class BhomEtabsAdapter(AnalysisAdapter):
    name = "ETABS (Windows bridge)"
    doc = "etabs"

    def __init__(self, design=None, bridge_url: str | None = None, route: str | None = None,
                 client: BridgeClient | None = None, status_ttl_s: float = 30.0):
        self.mock = mock_etabs.EtabsAdapter(design)
        self._design_src = design
        self.client = client or BridgeClient(bridge_url)
        self.route = (route or os.environ.get("CALCGRAPH_BRIDGE_ROUTE") or "csi").lower()
        if self.route not in ("csi", "bhom"):
            raise ValueError("route must be 'csi' or 'bhom'")
        self._status, self._status_at, self.status_ttl_s = None, 0.0, status_ttl_s

    # ---- bridge state
    def bridge_status(self, force: bool = False) -> dict:
        """{"up", "url", "route", "health" | "error", "checked_at"} (cached status_ttl_s)."""
        if self._status is not None and not force and time.time() - self._status_at < self.status_ttl_s:
            return self._status
        st = {"url": self.client.url, "route": self.route, "checked_at": mock_etabs._now_et()}
        try:
            h = self.client.get("/health")
            st.update(up=bool(h.get("ok")), health=h)
        except BridgeError as e:
            st.update(up=False, error=str(e))
        self._status, self._status_at = st, time.time()
        return st

    def _down(self, why: str) -> dict:
        return {**self.bridge_status(), "used": False, "fallback_reason": why}

    # ---- model
    def model_objects(self) -> list[AnalysisObject]:
        """The design's objects as ETABS would hold them: the mock's, already source `mock` (the
        AnalysisAdapter contract) - reading the model back out of a live ETABS is pull_results' job."""
        return self.mock.model_objects()

    def occurrences(self) -> list[dict]:
        return mock_etabs.occurrences_of(self.mock.model_objects(), self.doc)

    def export_model(self, path: str, design: dict | None = None, change: dict | None = None,
                     redesign: bool = False) -> dict:
        return {**self.mock.export_model(path, design, change, redesign), "source": "calc-graph .e2k writer"}

    def structural_bundle(self, change: dict | None = None) -> StructuralBundle:
        """The design (or the design with `change`, sizes carried) as a StructuralBundle."""
        exp = self.mock.design
        objs = self.mock._objects_for(exp, change, False)[0] if change else self.mock.model_objects()
        return structural_from_objects(objs, _sha_of_design(self._design_src))

    def to_bhom(self, change: dict | None = None) -> list[dict]:
        """The design as BHoM JSON objects (SI), ready for POST /bhom/etabs/push."""
        return schema_to_bhom(self.structural_bundle(change), include_results=False)

    # ---- send / pull
    def send_change(self, design: dict | None, change: dict) -> dict:
        """Writes the local job (analysis/etabs: change.json, model.e2k) and, when the bridge is
        up, sends it to real ETABS on the configured route. job["source"] says what happened."""
        job = self.mock.send_change(design, change)
        st = self.bridge_status(force=True)
        if not st.get("up"):
            job.update(source=ResultSource.mock.value, bridge=self._down("bridge not reachable"),
                       note=job["note"] + "; bridge down, nothing sent")
            return self._save_job(job)
        try:
            if self.route == "csi":
                started = self.client.post("/csi/start", {"product": "ETABS", "attach": False, "visible": False}, long=True)
                with open(job["files"]["e2k"]) as fh:
                    opened = self.client.post("/csi/open", {"e2k_text": fh.read(), "filename": f"{job['job_id']}.e2k"},
                                              long=True)
                ran = self.client.post("/csi/run", long=True)
                job.update(status="analysed", source=ResultSource.csi_oapi.value,
                           bridge={**st, "used": True, "start": _brief(started), "open": _brief(opened), "run": ran},
                           note=f"sent to real ETABS via CSI OAPI ({ran.get('source', '')}); analysis ran in "
                                f"{ran.get('seconds')} s")
            else:
                objs = self.to_bhom(job["change"])
                pushed = self.client.post("/bhom/etabs/push", {"objects": objs, "tag": job["job_id"]}, long=True)
                job.update(status="pushed", source=ResultSource.etabs_via_bhom.value,
                           bridge={**st, "used": True, "push": _brief(pushed), "objects_sent": len(objs)},
                           note="pushed to real ETABS via BHoM; NOT analysed (the bridge has no analyse call for the "
                                "BHoM adapter session yet)")
        except BridgeError as e:
            job.update(source=ResultSource.mock.value, bridge={**st, "used": False, "error": str(e),
                                                               "status": e.status, "body": e.body,
                                                               "fallback_reason": "bridge call failed"},
                       note=job["note"] + f"; bridge call failed ({e}), nothing analysed in ETABS")
        return self._save_job(job)

    def _save_job(self, job: dict) -> dict:
        with open(job["files"]["job"], "w") as fh:
            json.dump(job, fh, indent=1, sort_keys=True, default=str)
        return job

    def pull_results(self, job: dict | str, force: bool = False) -> dict:
        jid = job if isinstance(job, str) else job["job_id"]
        with open(os.path.join(mock_etabs.jobs_dir(), jid, "job.json")) as fh:
            job = json.load(fh)
        src = job.get("source")
        if src in (ResultSource.csi_oapi.value, ResultSource.etabs_via_bhom.value):
            st = self.bridge_status(force=True)
            if st.get("up"):
                try:
                    res = self._pull_csi(job) if src == ResultSource.csi_oapi.value else self._pull_bhom(job)
                    with open(os.path.join(mock_etabs.jobs_dir(), jid, f"results_{src}.json"), "w") as fh:
                        json.dump(res, fh, indent=1, sort_keys=True, default=str)
                    return res
                except BridgeError as e:
                    why = f"bridge call failed at pull ({e})"
            else:
                why = "bridge down at pull time"
        else:
            why = "job was not sent to ETABS (" + str((job.get("bridge") or {}).get("fallback_reason", "mock job")) + ")"
        return self._pull_fallback(job, why, force)

    def _pull_fallback(self, job: dict, why: str, force: bool) -> dict:
        res = self.mock.pull_results(job["job_id"], force=force)   # rows already tagged calcgraph-pynite
        res.update(bridge=self._down(why), adapter="bhom_etabs")
        return res

    # ---- real routes
    def _registry_maps(self) -> dict:
        lm = self.mock.label_map()
        frames = {}
        for eid, items in lm["by_element"].items():
            for it in items:
                frames[(it["label"], it["story"])] = eid
        return {"frames": frames}

    def _pull_csi(self, job: dict) -> dict:
        combos = [o.label for o in self.mock.model_objects() if o.kind == "combo"]
        raw = self.client.post("/csi/results", {"kinds": ["frame_forces", "joint_reactions", "story_drifts", "steel_dc"],
                                                "cases": [], "combos": combos}, long=True)
        units = (((job.get("bridge") or {}).get("open") or {}).get("present_units"))
        res = csi_results_to_schema(raw, units, doc_key=job["job_id"], label_of=self._csi_labels(raw))
        maps = self._registry_maps()
        return self._shape(job, res, maps, ResultSource.csi_oapi, raw.get("source", ""),
                           errors={k: v["error"] for k, v in raw.items() if isinstance(v, dict) and "error" in v})

    def _csi_labels(self, raw: dict):
        """unique name -> (label, story) via FrameObj/PointObj.GetLabelFromName (one call each)."""
        cache: dict[tuple[str, str], tuple[str, str]] = {}

        def label_of(kind: str, name: str):
            key = (kind, name)
            if key not in cache:
                path = "SapModel.FrameObj" if kind == "frame" else "SapModel.PointObj"
                try:
                    r = self.client.post("/csi/call", {"path": path, "method": "GetLabelFromName", "inputs": {"Name": name}})
                    cache[key] = (str(r.get("Label", "")), str(r.get("Story", "")))
                except BridgeError:
                    cache[key] = ("", "")
            return cache[key]
        return label_of

    def _pull_bhom(self, job: dict) -> dict:
        objs = []
        for t in ("BH.oM.Structure.Elements.Node", "BH.oM.Structure.Elements.Bar", "BH.oM.Structure.Loads.Loadcase",
                  "BH.oM.Structure.Loads.LoadCombination"):
            objs += self.client.post("/bhom/etabs/pull", {"type": t}, long=True).get("objects", [])
        reqs = [{"_t": "BH.oM.Structure.Requests.BarResultRequest", "ResultType": "BarForce",
                 "DivisionType": "EvenlyDistributed", "Divisions": 3, "Cases": [], "Modes": [], "ObjectIds": []},
                {"_t": "BH.oM.Structure.Requests.NodeResultRequest", "ResultType": "NodeReaction", "Axis": "Global",
                 "Cases": [], "Modes": [], "ObjectIds": []},
                {"_t": "BH.oM.Structure.Requests.GlobalResultRequest", "ResultType": "StoreyDrifts", "Cases": [],
                 "Modes": [], "ObjectIds": []}]
        results, errors = [], {}
        for r in reqs:
            try:
                results += self.client.post("/bhom/etabs/pull", {"request": r}, long=True).get("objects", [])
            except BridgeError as e:
                errors[r["ResultType"]] = str(e)
        sha = hashlib.sha256(json.dumps(objs + results, sort_keys=True).encode()).hexdigest()
        bundle, rep = bhom_to_schema(objs + results, doc_sha=sha, source=ResultSource.etabs_via_bhom,
                                     source_name=f"bridge pull {job['job_id']}")
        out = self._shape(job, bundle, self._registry_maps(), ResultSource.etabs_via_bhom, "BHoM ETABS_Toolkit",
                          errors=errors)
        out["conversion"] = rep.to_dict()
        if not bundle.results:
            out["note"] = "no results in the ETABS model: a BHoM push is not analysed by this adapter (see module doc)"
        return out

    def _shape(self, job, bundle: StructuralBundle, maps, source: ResultSource, detail: str, errors: dict) -> dict:
        bars = {b.id: b for b in bundle.bars}

        def element_of(r):
            b = bars.get(r.object_id)
            holder = b if b is not None else r          # BHoM: via the bar; CSI: via the result's refs
            ids = next((x.ids for x in holder.refs if x.ids), {})
            lab, story = ids.get("etabs_label"), ids.get("etabs_story")
            return maps["frames"].get((lab, story)), lab, story

        rows = {"bar_forces": [], "frame_design": [], "story_drifts": [], "node_reactions": []}
        for r in bundle.results:
            d = r.model_dump(mode="json", exclude={"provenance"})
            if isinstance(r, (BarForceResult, UtilisationResult)):
                eid, lab, story = element_of(r)
                d.update(element_id=eid, Label=lab, Story=story)
                rows["frame_design" if isinstance(r, UtilisationResult) else "bar_forces"].append(_tag(d, source))
            elif isinstance(r, StoreyDriftResult):
                rows["story_drifts"].append(_tag(d, source))
            elif isinstance(r, NodeReactionResult):
                rows["node_reactions"].append(_tag(d, source))
        ratios = [x["ratio"]["value"] for x in rows["frame_design"]]
        drifts = [x["ratio"]["value"] for x in rows["story_drifts"]]
        return {"job_id": job["job_id"], "adapter": "bhom_etabs", "status": "complete", "completed_at": mock_etabs._now_et(),
                "change": job.get("change"), "source": source.value, "source_detail": f"{SOURCE_DETAIL[source]} ({detail})",
                **rows, "errors": errors,
                "summary": _tag({"max_ratio": max(ratios, default=None), "max_drift_ratio": max(drifts, default=None),
                                 "frames_over_1": sorted(f"{x['Label']}@{x['Story']}" for x in rows["frame_design"]
                                                         if x["ratio"]["value"] > 1.0),
                                 "unmapped_frames": sum(1 for x in rows["bar_forces"] + rows["frame_design"]
                                                        if not x["element_id"])}, source),
                "structural": bundle.model_dump(mode="json"), "bridge": {**self.bridge_status(), "used": True}}


def _brief(d: dict) -> dict:
    """A bridge reply without its bulk (object lists)."""
    return {k: (f"[{len(v)} items]" if isinstance(v, list) and len(v) > 20 else v) for k, v in (d or {}).items()
            if k != "objects"} | ({"present_units": d["summary"].get("present_units")}
                                  if isinstance(d, dict) and isinstance(d.get("summary"), dict) else {})


# ======================================================================== CSI OAPI rows -> schema results
def csi_results_to_schema(raw: dict, present_units, doc_key: str, label_of=None) -> StructuralBundle:
    """/csi/results rows (OAPI by-ref output names: FrameForce Obj/ObjSta/LoadCase/P/V2/V3/T/M2/M3,
    JointReact Obj/LoadCase/F1..M3, StoryDrifts Story/LoadCase/Direction/Drift, DesignSteel
    GetSummaryResults FrameName/Ratio/RatioType/ComboName) -> a results-only StructuralBundle.

    Units come from the model's present units (returned by /csi/open); an unknown unit system
    is refused rather than guessed. Drift and D/C ratios are unitless and need none."""
    if isinstance(present_units, str):
        present_units = CSI_UNIT_NAMES.get(present_units, present_units)
    fu = CSI_UNITS.get(present_units) if isinstance(present_units, int) else None
    force_u, len_u = fu or (None, None)
    moment_u = {"kip": {"ft": "kip*ft", "in": "kip*in"}, "kN": {"m": "kN*m"}, "N": {"m": "N*m"},
                "lbf": {"ft": "lbf*ft"}}.get(force_u, {}).get(len_u)
    sha = hashlib.sha256(json.dumps(raw, sort_keys=True, default=str).encode()).hexdigest()
    label_of = label_of or (lambda kind, name: ("", ""))
    out: dict[str, list] = {c: [] for c in StructuralBundle.COLLECTIONS}
    cases: dict[str, str] = {}

    def prov(kind, key, text=""):
        return Provenance(evidence=[ModelEvidence(doc_sha=sha, global_id=key, entity=f"CSI OAPI {kind}", text=text[:200])],
                          rule_id=f"csi-oapi/{kind}", rule_version="1.0", engine=ENGINE, method=Method.deterministic,
                          confidence=1.0)

    def case(name):
        if name not in cases:
            cid = f"case:{name}"
            cases[name] = cid
            out["load_cases"].append(LoadCase(id=cid, name=name, nature=LoadNature.other,
                                              description="named in CSI results; nature not read",
                                              provenance=prov("LoadCase", name)))
        return cases[name]

    def ref(kind, name) -> list[ExternalRef]:
        """CSI result rows carry no geometry, so results point at the ETABS object through refs
        (object_id stays empty) instead of at invented bars/nodes."""
        lab, story = label_of(kind, name)
        return [ExternalRef(system="etabs", type=kind, name=lab,
                            ids={"etabs": str(name), "etabs_label": lab, "etabs_story": story})]

    def need_units(kind):
        if not (force_u and len_u and moment_u):
            raise ValueError(f"{kind}: ETABS present units {present_units!r} unknown - refusing to label forces")

    src = ResultSource.csi_oapi
    rows = raw.get("frame_forces")
    if isinstance(rows, list) and rows:
        need_units("FrameForce")
        lengths: dict[str, float] = {}
        for r in rows:
            lengths[r["Obj"]] = max(lengths.get(r["Obj"], 0.0), float(r["ObjSta"]))
        for i, r in enumerate(rows):
            L = lengths[r["Obj"]] or 1.0
            q = lambda k, u: Quantity(value=float(r[k]), unit=u)  # noqa: E731
            out["results"].append(BarForceResult(
                id=f"res:ff:{i}", source=src, object_id="", refs=ref("frame", r["Obj"]), case_id=case(r["LoadCase"]),
                position=Quantity(value=min(1.0, float(r["ObjSta"]) / L), unit="1"),
                fx=q("P", force_u), fy=q("V2", force_u), fz=q("V3", force_u), mx=q("T", moment_u), my=q("M2", moment_u),
                mz=q("M3", moment_u), provenance=prov("Results.FrameForce", f"{r['Obj']}|{r['LoadCase']}|{r['ObjSta']}")))
    rows = raw.get("joint_reactions")
    if isinstance(rows, list) and rows:
        need_units("JointReact")
        for i, r in enumerate(rows):
            q = lambda k, u: Quantity(value=float(r[k]), unit=u)  # noqa: E731
            out["results"].append(NodeReactionResult(
                id=f"res:jr:{i}", source=src, object_id="", refs=ref("point", r["Obj"]), case_id=case(r["LoadCase"]),
                fx=q("F1", force_u), fy=q("F2", force_u), fz=q("F3", force_u), mx=q("M1", moment_u),
                my=q("M2", moment_u), mz=q("M3", moment_u),
                provenance=prov("Results.JointReact", f"{r['Obj']}|{r['LoadCase']}")))
    rows = raw.get("story_drifts")
    if isinstance(rows, list):
        for i, r in enumerate(rows):
            out["results"].append(StoreyDriftResult(
                id=f"res:sd:{i}", source=src, object_id="", case_id=case(r["LoadCase"]), storey=str(r["Story"]),
                direction="x" if str(r["Direction"]).upper().startswith("X") else "y",
                ratio=Quantity(value=float(r["Drift"]), unit="1"),
                provenance=prov("Results.StoryDrifts", f"{r['Story']}|{r['LoadCase']}|{r['Direction']}")))
    rows = raw.get("steel_dc")
    if isinstance(rows, list):
        for i, r in enumerate(rows):
            out["results"].append(UtilisationResult(
                id=f"res:dc:{i}", source=src, object_id="", refs=ref("frame", r["FrameName"]),
                case_id=case(r.get("ComboName") or "(none)"),
                ratio=Quantity(value=float(r["Ratio"]), unit="1"), ratio_type=str(r.get("RatioType", "")),
                provenance=prov("DesignSteel.GetSummaryResults", f"{r['FrameName']}|{r.get('ComboName')}")))
    out["requests"].append(ResultRequest(id="req:csi", kind=ResultKind.bar_force, provenance=prov("request", "csi/results"),
                                         case_ids=[]))
    return StructuralBundle(source=f"CSI OAPI results ({doc_key})", model_frame=f"BuildingFt(etabs:{doc_key})", **out)


__all__ = ["BhomEtabsAdapter", "BridgeClient", "BridgeError", "structural_from_objects", "csi_results_to_schema"]
