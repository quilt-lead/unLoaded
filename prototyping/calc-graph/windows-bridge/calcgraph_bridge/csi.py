"""Direct CSI OAPI (ETABS / SAP2000) for what BHoM does not cover: open an .e2k, run the
analysis, read member forces, reactions, story drifts and steel D/C ratios.

All navigation and calls go through reflection on the API's interface types
(``clr_runtime.invoke``), so by-ref outputs come back by parameter name and a signature
mismatch reports the real signature instead of a pythonnet overload error.

Models are always opened from a COPY under ``C:\\calcgraph\\work\\<job>`` and saved there;
the bridge never writes next to a caller's file. ETABS is closed on /csi/close only if
this bridge started it.
"""

from __future__ import annotations

import os
import shutil
import time
import uuid
from typing import Any

from . import clr_runtime as rt
from .inventory import csi_installs

WORK_ROOT = os.environ.get("CALCGRAPH_WORK", r"C:\calcgraph\work")

PRODUCTS = {
    # product prefix -> (api dll, namespace, ProgID)
    "ETABS": ("ETABSv1.dll", "ETABSv1", "CSI.ETABS.API.ETABSObject"),
    "SAP2000": ("SAP2000v1.dll", "SAP2000v1", "CSI.SAP2000.API.SapObject"),
}


class NotInstalled(RuntimeError):
    """The CSI product (or its API assembly) is not on this desk."""


class NoSession(RuntimeError):
    """No CSI application is attached: POST /csi/start first."""


class _Session:
    def __init__(self) -> None:
        self.product: str | None = None
        self.install: dict[str, Any] | None = None
        self.ns: str | None = None
        self.asm: Any = None
        self.oapi: Any = None
        self.started_by_us = False
        self.version: str | None = None
        self.job_dir: str | None = None
        self.model_path: str | None = None


S = _Session()


def _pick_install(product: str) -> tuple[dict[str, Any], str, str, str]:
    product = product.upper()
    if product not in PRODUCTS:
        raise ValueError(f"product must be one of {sorted(PRODUCTS)}")
    dll, ns, progid = PRODUCTS[product]
    cands = [i for i in csi_installs() if i["product"].upper().startswith(product)]
    for inst in sorted(cands, key=lambda i: i["product"], reverse=True):
        if dll in inst["api_dlls"]:
            return inst, os.path.join(inst["dir"], dll), ns, progid
        if "CSiAPIv1.dll" in inst["api_dlls"]:
            return inst, os.path.join(inst["dir"], "CSiAPIv1.dll"), "CSiAPIv1", progid
    raise NotInstalled(f"{product} is not installed on this desk (no {dll} under "
                       r"C:\Program Files\Computers and Structures)")


def _iface(name: str) -> Any:
    t = S.asm.GetType(f"{S.ns}.{name}")
    if t is None:
        raise LookupError(f"{S.ns}.{name} not in {S.asm.FullName}")
    return t


def _nav(path: str) -> tuple[Any, Any]:
    """Walk ``SapModel.Results.Setup``-style property paths from the cOAPI root."""
    if S.oapi is None:
        raise NoSession("no CSI application attached: POST /csi/start first")
    obj, t = S.oapi, _iface("cOAPI")
    for part in [p for p in path.split(".") if p]:
        prop = t.GetProperty(part)
        if prop is None:
            raise LookupError(f"{t.Name} has no property {part}")
        obj, t = prop.GetValue(obj, None), prop.PropertyType
    return obj, t


def call(path: str, method: str, inputs: dict[str, Any] | list[Any] | None = None,
         nparams: int | None = None) -> dict[str, Any]:
    obj, t = _nav(path)
    return rt.invoke(obj, t, method, inputs, nparams)


def _ok(res: dict[str, Any], what: str) -> dict[str, Any]:
    if res.get("ret") not in (0, None):
        raise RuntimeError(f"{what} returned {res.get('ret')} (CSI OAPI: nonzero = failure)")
    return res


def source() -> str:
    return f"real {S.product} {S.version or '?'} via CSI OAPI"


def status() -> dict[str, Any]:
    return {
        "installs": csi_installs(),
        "attached": S.oapi is not None,
        "product": S.product,
        "version": S.version,
        "started_by_bridge": S.started_by_us,
        "model": S.model_path,
    }


def start(product: str = "ETABS", attach: bool = False, visible: bool = False) -> dict[str, Any]:
    """Attach to a running instance (``attach``) or start a new one through the API helper.

    ApplicationStart fails with a nonzero code when no licence is available; that code is
    returned, not hidden.
    """
    if S.oapi is not None:
        return {"already_attached": True, **status()}
    inst, dll, ns, progid = _pick_install(product)
    S.asm = rt.add_reference(dll)
    S.ns, S.product, S.install = ns, product.upper(), inst
    helper_cls = rt.find_type(f"{ns}.Helper")
    from System import Activator

    helper = Activator.CreateInstance(helper_cls)
    hif = _iface("cHelper")
    if attach:
        S.oapi = rt.invoke(helper, hif, "GetObject", [progid], raw_ret=True)["ret"]
        S.started_by_us = False
        started = None
    else:
        S.oapi = rt.invoke(helper, hif, "CreateObjectProgID", [progid], raw_ret=True)["ret"]
        started = call("", "ApplicationStart", [], nparams=0)
        if started["ret"] != 0:
            S.oapi = None
            raise RuntimeError(f"{product} ApplicationStart returned {started['ret']} "
                               "(no licence, or the app cannot start in this session)")
        S.started_by_us = True
        if not visible:
            call("", "Hide", [])
    if S.oapi is None:
        raise RuntimeError(f"could not {'attach to' if attach else 'create'} {progid}")
    try:
        S.version = str(call("SapModel", "GetVersion").get("Version"))
    except Exception:
        S.version = inst.get("exe_version")
    return {"started": started, **status(), "source": source()}


def _new_job_dir() -> str:
    d = os.path.join(WORK_ROOT, time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6])
    os.makedirs(d, exist_ok=True)
    return d


def open_model(path: str | None = None, text: str | None = None,
               filename: str = "model.e2k") -> dict[str, Any]:
    """Open a COPY of ``path`` (on the desk) or of ``text`` (an .e2k body sent by the Mac)."""
    if (path is None) == (text is None):
        raise ValueError("give exactly one of path / text")
    _nav("")  # raises NoSession before anything is written
    job = _new_job_dir()
    if path is not None:
        target = os.path.join(job, os.path.basename(path))
        shutil.copy2(path, target)
    else:
        target = os.path.join(job, os.path.basename(filename))
        with open(target, "w", encoding="utf-8", newline="\r\n") as fh:
            fh.write(text)
    _ok(call("SapModel", "InitializeNewModel"), "InitializeNewModel")
    _ok(call("SapModel.File", "OpenFile", {"FileName": target}), "OpenFile")
    S.job_dir, S.model_path = job, target
    return {"model": target, "summary": summary(), "source": source()}


def _names(path: str) -> list[str]:
    res = call(path, "GetNameList")
    for k, v in res.items():
        if isinstance(v, list):
            return v
    return []


def summary() -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, path in (("frames", "SapModel.FrameObj"), ("points", "SapModel.PointObj"),
                      ("stories", "SapModel.Story"), ("load_patterns", "SapModel.LoadPatterns"),
                      ("load_cases", "SapModel.LoadCases"), ("combos", "SapModel.RespCombo"),
                      ("frame_sections", "SapModel.PropFrame"), ("materials", "SapModel.PropMaterial")):
        try:
            names = _names(path)
            out[key] = {"count": len(names), "names": names[:200]}
        except Exception as exc:
            out[key] = {"error": str(exc)}
    try:
        out["present_units"] = call("SapModel", "GetPresentUnits")["ret"]
    except Exception:
        pass
    return out


def run_analysis() -> dict[str, Any]:
    if not S.model_path:
        raise NoSession("no model open: POST /csi/open first")
    edb = os.path.splitext(S.model_path)[0] + ".edb"
    _ok(call("SapModel.File", "Save", {"FileName": edb}), "Save")
    t0 = time.time()
    _ok(call("SapModel.Analyze", "RunAnalysis"), "RunAnalysis")
    S.model_path = edb
    return {"saved": edb, "seconds": round(time.time() - t0, 2), "source": source()}


def _rows(res: dict[str, Any], skip: tuple[str, ...] = ("ret",)) -> list[dict[str, Any]]:
    cols = {k: v for k, v in res.items() if isinstance(v, list) and k not in skip}
    n = max((len(v) for v in cols.values()), default=0)
    return [{k: (v[i] if i < len(v) else None) for k, v in cols.items()} for i in range(n)]


def _select(cases: list[str], combos: list[str]) -> None:
    _ok(call("SapModel.Results.Setup", "DeselectAllCasesAndCombosForOutput"), "Deselect")
    for c in cases:
        _ok(call("SapModel.Results.Setup", "SetCaseSelectedForOutput", {"Name": c}), f"select case {c}")
    for c in combos:
        _ok(call("SapModel.Results.Setup", "SetComboSelectedForOutput", {"Name": c}), f"select combo {c}")


def results(kinds: list[str], cases: list[str] | None = None, combos: list[str] | None = None,
            group: str = "All") -> dict[str, Any]:
    """``kinds`` from frame_forces, joint_reactions, story_drifts, steel_dc."""
    cases, combos = cases or [], combos or []
    if not cases and not combos:
        cases = _names("SapModel.LoadCases")
    _select(cases, combos)
    out: dict[str, Any] = {"cases": cases, "combos": combos, "source": source()}
    for kind in kinds:
        try:
            if kind == "frame_forces":
                res = _ok(call("SapModel.Results", "FrameForce",
                               {"Name": group, "ItemTypeElm": "GroupElm"}), "FrameForce")
            elif kind == "joint_reactions":
                res = _ok(call("SapModel.Results", "JointReact",
                               {"Name": group, "ItemTypeElm": "GroupElm"}), "JointReact")
            elif kind == "story_drifts":
                res = _ok(call("SapModel.Results", "StoryDrifts"), "StoryDrifts")
            elif kind == "steel_dc":
                _ok(call("SapModel.DesignSteel", "StartDesign"), "DesignSteel.StartDesign")
                res = _ok(call("SapModel.DesignSteel", "GetSummaryResults",
                               {"Name": group, "ItemType": "Group"}), "GetSummaryResults")
            else:
                raise ValueError(f"unknown result kind {kind}")
            out[kind] = _rows(res)
        except Exception as exc:
            out[kind] = {"error": f"{type(exc).__name__}: {exc}"}
    return out


def close() -> dict[str, Any]:
    if S.oapi is None:
        return {"closed": False, "reason": "not attached"}
    exited = False
    if S.started_by_us:
        call("", "ApplicationExit", {"FileSave": False})
        exited = True
    S.__init__()
    return {"closed": True, "application_exited": exited}
