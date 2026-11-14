"""FastAPI surface of the bridge. Start with ``python -m calcgraph_bridge`` (127.0.0.1 only).

Endpoints
- GET  /health              process + CLR state (never loads the CLR)
- GET  /inventory           desk software inventory (read-only, never loads the CLR)
- GET  /dotnet/probe        loads the CLR through pythonnet and runs a .NET computation
- GET  /dotnet/selftest     the reflection invoke path (by-ref, enum, array, positional)
- POST /dotnet/inspect      reflection-only look at an installed .NET assembly (types, framework)
- GET  /bhom/status         BHoM install + loads its core assemblies
- POST /bhom/roundtrip      BHoM JSON -> .NET -> BHoM JSON (Serialiser, no vendor app)
- POST /bhom/etabs/pull     ETABS -> BHoM objects / results (ETABS_Toolkit adapter)
- POST /bhom/etabs/push     BHoM objects -> ETABS (ETABS_Toolkit adapter)
- GET  /csi/status          CSI installs + attached session
- GET  /csi/api             load the OAPI assembly and resolve its entry types (no app started)
- POST /csi/start           start (hidden) or attach to ETABS/SAP2000 via the OAPI helper
- POST /csi/open            open a COPY of an .e2k/.edb (desk path, or e2k text from the Mac)
- POST /csi/run             save the copy as .edb and run the analysis
- POST /csi/results         frame forces / joint reactions / story drifts / steel D/C
- POST /csi/call            any OAPI method by property path (exploration)
- POST /csi/close           exit the CSI app if this bridge started it

Errors: 503 ``not_installed`` (software missing: the body says what to install),
409 ``no_session`` (call order), 500 with the .NET exception text otherwise.
"""

from __future__ import annotations

import os
import socket
import time
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from . import __version__, bhom, csi
from . import clr_runtime as rt
from .inventory import inventory

STARTED = time.time()
app = FastAPI(title="calc-graph Windows bridge", version=__version__)


@app.exception_handler(Exception)
async def _errors(_req: Request, exc: Exception) -> JSONResponse:
    if "0x800711C7" in str(exc):  # Windows Application Control (Smart App Control / WDAC)
        return JSONResponse(status_code=503, content={
            "error": "blocked_by_application_control",
            "detail": "Windows Application Control (Smart App Control on this desk, see "
                      "/inventory smart_app_control) refused to load an unsigned assembly. "
                      "BHoM's assemblies are unsigned, so BHoM cannot load here while it is on.",
            "dotnet_error": str(exc).splitlines()[0]})
    if isinstance(exc, (bhom.NotInstalled, csi.NotInstalled)):
        return JSONResponse(status_code=503, content={"error": "not_installed", "detail": str(exc)})
    if isinstance(exc, csi.NoSession):
        return JSONResponse(status_code=409, content={"error": "no_session", "detail": str(exc)})
    if isinstance(exc, (ValueError, LookupError, FileNotFoundError)):
        return JSONResponse(status_code=400, content={"error": "bad_request", "detail": str(exc)})
    return JSONResponse(status_code=500, content={"error": type(exc).__name__, "detail": str(exc)})


@app.get("/health")
def health() -> dict[str, Any]:
    return {"ok": True, "service": "calcgraph-windows-bridge", "version": __version__,
            "host": socket.gethostname(), "pid": os.getpid(),
            "uptime_s": round(time.time() - STARTED, 1), "clr": rt.state()}


@app.get("/inventory")
def get_inventory() -> dict[str, Any]:
    return inventory()


def _probe() -> dict[str, Any]:
    from System import AppDomain, BitConverter, Environment
    from System.Runtime.InteropServices import RuntimeInformation
    from System.Security.Cryptography import SHA256
    from System.Text import Encoding

    digest = SHA256.Create().ComputeHash(Encoding.UTF8.GetBytes("calc-graph"))
    return {
        "clr": rt.state(),
        "framework": RuntimeInformation.FrameworkDescription,
        "clr_version": str(Environment.Version),
        "is_64bit_process": Environment.Is64BitProcess,
        "machine": Environment.MachineName,
        "sha256_calc_graph": BitConverter.ToString(digest).replace("-", "").lower(),
        "loaded_assemblies": len(AppDomain.CurrentDomain.GetAssemblies()),
        "source": "pythonnet -> .NET runtime on the desk",
    }


@app.get("/dotnet/probe")
def dotnet_probe() -> dict[str, Any]:
    return rt.on_clr(_probe)


def _selftest() -> dict[str, Any]:
    """Exercise clr_runtime.invoke (the path every CSI/BHoM call takes) on .NET Framework
    methods with the same parameter shapes the OAPI uses: by-ref outputs, enums, arrays."""
    from System import String

    int_t, str_t = rt.find_type("System.Int32"), rt.find_type("System.String")
    checks = {
        # static, by-ref out int, overload picked by parameter count
        "byref_out": (rt.invoke(None, int_t, "TryParse", {"s": "42"}, nparams=2),
                      {"ret": True, "result": 42}),
        # instance, char[] array input, enum given by name, string[] return
        "array_enum": (rt.invoke(String("a,,b"), str_t, "Split",
                                 {"separator": [","], "options": "RemoveEmptyEntries"}),
                       {"ret": ["a", "b"]}),
        # positional inputs
        "positional": (rt.invoke(String("calc-graph"), str_t, "Substring", [5], nparams=1),
                       {"ret": "graph"}),
    }
    out = {k: {"got": got, "want": want, "ok": got == want} for k, (got, want) in checks.items()}
    try:
        rt.invoke(None, int_t, "TryParse", {"nope": 1}, nparams=2)
        out["bad_param_reports_signature"] = {"ok": False}
    except ValueError as exc:
        out["bad_param_reports_signature"] = {"ok": "signature" in str(exc), "detail": str(exc)}
    out["all_ok"] = all(v["ok"] for v in out.values() if isinstance(v, dict))
    return out


@app.get("/dotnet/selftest")
def dotnet_selftest() -> dict[str, Any]:
    return rt.on_clr(_selftest)


class InspectBody(BaseModel):
    path: str
    max_types: int = 40


_ro_handlers: list[Any] = []


def _ensure_reflection_only_resolver() -> None:
    """Reflection-only loads do not resolve dependencies on their own: a netstandard 2.0
    assembly (CSI's ETABSv1.dll) needs ``netstandard`` from the framework, and vendor
    assemblies need their siblings. Resolve by name, then from the requester's folder."""
    if _ro_handlers:
        return
    from System import AppDomain, ResolveEventHandler
    from System.Reflection import Assembly, AssemblyName

    def _resolve(_sender: Any, args: Any) -> Any:
        try:
            return Assembly.ReflectionOnlyLoad(args.Name)
        except Exception:
            pass
        if args.RequestingAssembly is not None:
            cand = os.path.join(os.path.dirname(args.RequestingAssembly.Location),
                                AssemblyName(args.Name).Name + ".dll")
            if os.path.isfile(cand):
                return Assembly.ReflectionOnlyLoadFrom(cand)
        return None

    h = ResolveEventHandler(_resolve)
    AppDomain.CurrentDomain.ReflectionOnlyAssemblyResolve += h
    _ro_handlers.append(h)


def _inspect(path: str, max_types: int) -> dict[str, Any]:
    from System.Reflection import Assembly, AssemblyName, CustomAttributeData, ReflectionTypeLoadException

    name = AssemblyName.GetAssemblyName(path)
    out: dict[str, Any] = {"path": path, "name": name.Name, "version": str(name.Version)}
    _ensure_reflection_only_resolver()
    try:
        asm = Assembly.ReflectionOnlyLoadFrom(path)
    except Exception as exc:  # coreclr has no reflection-only context
        out["types_error"] = f"{type(exc).__name__}: {exc}"
        return out
    for cad in CustomAttributeData.GetCustomAttributes(asm):
        if cad.AttributeType.Name == "TargetFrameworkAttribute":
            out["target_framework"] = str(cad.ConstructorArguments[0].Value)
    try:
        types = list(asm.GetTypes())
    except ReflectionTypeLoadException as exc:
        types = [t for t in exc.Types if t is not None]
        out["partial_types_note"] = "some types need dependencies not loaded (reflection-only)"
    public = sorted(t.FullName for t in types if t.IsPublic)
    out.update(public_type_count=len(public), sample_types=public[:max_types])
    return out


@app.post("/dotnet/inspect")
def dotnet_inspect(body: InspectBody) -> dict[str, Any]:
    if not (body.path.lower().endswith(".dll") and os.path.isfile(body.path)):
        raise FileNotFoundError(f"not an existing .dll: {body.path}")
    return rt.on_clr(_inspect, body.path, body.max_types)


@app.get("/bhom/status")
def bhom_status() -> dict[str, Any]:
    return bhom.status()


@app.post("/bhom/roundtrip")
def bhom_roundtrip(doc: dict[str, Any]) -> dict[str, Any]:
    return bhom.roundtrip(doc)


class PullBody(BaseModel):
    type: str | None = Field(None, description="BHoM type, e.g. BH.oM.Structure.Elements.Bar")
    request: dict[str, Any] | None = Field(None, description="any BHoM IRequest as BHoM JSON")
    model_path: str | None = None


@app.post("/bhom/etabs/pull")
def bhom_etabs_pull(body: PullBody) -> dict[str, Any]:
    if (body.type is None) == (body.request is None):
        raise ValueError("give exactly one of type / request")
    return bhom.pull(body.type, body.request, body.model_path)


class PushBody(BaseModel):
    objects: list[dict[str, Any]]
    tag: str = "calcgraph"
    model_path: str | None = None


@app.post("/bhom/etabs/push")
def bhom_etabs_push(body: PushBody) -> dict[str, Any]:
    return bhom.push(body.objects, body.tag, body.model_path)


@app.get("/csi/status")
def csi_status() -> dict[str, Any]:
    return csi.status()


class StartBody(BaseModel):
    product: str = "ETABS"
    attach: bool = False
    visible: bool = False


@app.get("/csi/api")
def csi_api(product: str = "ETABS") -> dict[str, Any]:
    return rt.on_clr(csi.api_probe, product)


@app.post("/csi/start")
def csi_start(body: StartBody) -> dict[str, Any]:
    return rt.on_clr(csi.start, body.product, body.attach, body.visible)


class OpenBody(BaseModel):
    path: str | None = Field(None, description="model file on the desk (copied before opening)")
    e2k_text: str | None = Field(None, description=".e2k body sent from the Mac")
    filename: str = "model.e2k"


@app.post("/csi/open")
def csi_open(body: OpenBody) -> dict[str, Any]:
    return rt.on_clr(csi.open_model, body.path, body.e2k_text, body.filename)


@app.post("/csi/run")
def csi_run() -> dict[str, Any]:
    return rt.on_clr(csi.run_analysis)


class ResultsBody(BaseModel):
    kinds: list[str] = ["frame_forces", "joint_reactions", "story_drifts", "steel_dc"]
    cases: list[str] = []
    combos: list[str] = []
    group: str = "All"


@app.post("/csi/results")
def csi_results(body: ResultsBody) -> dict[str, Any]:
    return rt.on_clr(csi.results, body.kinds, body.cases, body.combos, body.group)


class CallBody(BaseModel):
    path: str = Field("SapModel", description="property path from cOAPI, e.g. SapModel.FrameObj")
    method: str
    inputs: dict[str, Any] | list[Any] | None = None


@app.post("/csi/call")
def csi_call(body: CallBody) -> dict[str, Any]:
    return {**rt.on_clr(csi.call, body.path, body.method, body.inputs), "source": csi.source()}


@app.post("/csi/close")
def csi_close() -> dict[str, Any]:
    return rt.on_clr(csi.close)
