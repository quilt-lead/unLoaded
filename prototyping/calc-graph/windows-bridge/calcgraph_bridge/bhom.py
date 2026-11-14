"""BHoM through pythonnet: the UNMODIFIED assemblies from the BHoM installer
(``C:\\ProgramData\\BHoM\\Assemblies``), never BHoM source in this repo.

Objects cross the wire as BHoM JSON (``BH.Engine.Serialiser.Convert.ToJson / FromJson``);
the Mac maps them through the A5 BHoM<->schema mapping. Adapter calls are made by
reflection so optional parameters (PullType, ActionConfig, ...) get the defaults BHoM
declares, whichever BHoM version is installed.
"""

from __future__ import annotations

import glob
import json
import os
from typing import Any

from . import clr_runtime as rt
from .inventory import BHOM_ROOT, bhom as bhom_inventory

ASSEMBLIES = os.path.join(BHOM_ROOT, "Assemblies")
CORE = ("BHoM", "BHoM_Engine", "Serialiser_Engine", "Data_oM", "Adapter_oM", "Adapter_Engine",
        "BHoM_Adapter", "Structure_oM", "Analytical_oM", "Geometry_oM")


class NotInstalled(RuntimeError):
    """BHoM (or the requested toolkit) is not installed on this desk."""


_loaded: dict[str, Any] = {}
_adapters: dict[str, Any] = {}


def _require() -> None:
    if not os.path.isdir(ASSEMBLIES):
        raise NotInstalled(f"BHoM is not installed ({ASSEMBLIES} missing): run the BHoM installer")


def load_core() -> dict[str, Any]:
    """Load the core BHoM assemblies (CLR thread)."""
    _require()
    rt.add_probe_dir(ASSEMBLIES)
    for name in CORE:
        if name in _loaded:
            continue
        p = os.path.join(ASSEMBLIES, name + ".dll")
        if os.path.isfile(p):
            _loaded[name] = str(rt.add_reference(p).GetName().Version)
    missing = [n for n in ("BHoM", "Serialiser_Engine", "BHoM_Adapter") if n not in _loaded]
    if missing:
        raise NotInstalled(f"BHoM core assemblies missing: {missing}")
    return dict(_loaded)


def _serialiser() -> Any:
    return rt.find_type("BH.Engine.Serialiser.Convert")


def to_json(obj: Any) -> Any:
    s = rt.invoke(None, _serialiser(), "ToJson", [obj], nparams=1)["ret"]
    return json.loads(s)


def from_json(doc: Any) -> Any:
    text = doc if isinstance(doc, str) else json.dumps(doc)
    conv = _serialiser()
    return rt.invoke(None, conv, "FromJson", [text], nparams=1, raw_ret=True)["ret"]


def status() -> dict[str, Any]:
    inv = bhom_inventory()
    if not inv.get("installed"):
        return inv
    try:
        inv["loaded_core"] = rt.on_clr(load_core)
    except Exception as exc:
        inv["load_error"] = f"{type(exc).__name__}: {exc}"
    return inv


def roundtrip(doc: Any) -> dict[str, Any]:
    """BHoM JSON -> .NET object -> BHoM JSON: proves the Serialiser without any vendor app."""

    def _go() -> dict[str, Any]:
        load_core()
        obj = from_json(doc)
        return {"dotnet_type": obj.GetType().FullName if obj is not None else None,
                "json": to_json(obj), "source": "BHoM Serialiser_Engine (no vendor app)"}

    return rt.on_clr(_go)


# ETABS_Adapter.dll is the toolkit's adapter for ETABS v18+ (the ETABSv1 API); the
# numbered ones (Etabs2016_Adapter, ETABS17_Adapter) target retired ETABS versions and
# must never be preferred just because their file name carries a bigger number.
ETABS_ADAPTER_DLL = os.environ.get("CALCGRAPH_BHOM_ETABS_ADAPTER", "ETABS_Adapter.dll")


def _etabs_adapter_type() -> Any:
    path = os.path.join(ASSEMBLIES, ETABS_ADAPTER_DLL)
    if not os.path.isfile(path):
        found = sorted(os.path.basename(p) for p in glob.glob(os.path.join(ASSEMBLIES, "ETABS*_Adapter.dll")))
        raise NotInstalled(f"BHoM ETABS adapter {ETABS_ADAPTER_DLL} not in {ASSEMBLIES} "
                           f"(found: {found or 'none'}); it ships with the BHoM installer")
    asm = rt.add_reference(path)
    base = rt.find_type("BH.Adapter.BHoMAdapter")
    for t in asm.GetTypes():
        if t.IsClass and not t.IsAbstract and base.IsAssignableFrom(t):
            return t
    raise NotInstalled(f"no BHoMAdapter subclass in {path}")


def etabs_adapter(model_path: str | None) -> Any:
    """One adapter per model path; ``active`` = True so the adapter starts/attaches ETABS."""
    key = model_path or ""
    if key in _adapters:
        return _adapters[key]
    load_core()
    t = _etabs_adapter_type()
    from System import Activator, Array, Type

    ctor = max(t.GetConstructors(), key=lambda c: len(c.GetParameters()))
    params = list(ctor.GetParameters())
    args = Array.CreateInstance(Type.GetType("System.Object"), len(params))
    for i, p in enumerate(params):
        if p.Name.lower() in ("filepath", "path"):
            v = key
        elif p.Name.lower() == "active":
            v = True
        elif p.HasDefaultValue:
            v = p.DefaultValue
        else:
            v = None
        args.SetValue(v, i)
    adapter = Activator.CreateInstance(t, args)
    _adapters[key] = adapter
    return adapter


def _filter_request(type_name: str) -> Any:
    from System import Activator

    req_t = rt.find_type("BH.oM.Data.Requests.FilterRequest")
    req = Activator.CreateInstance(req_t)
    req_t.GetProperty("Type").SetValue(req, rt.find_type(type_name), None)
    return req


def pull(type_name: str | None = None, request: Any = None,
         model_path: str | None = None) -> dict[str, Any]:
    """Pull objects (``type_name`` e.g. ``BH.oM.Structure.Elements.Bar``) or any BHoM request
    given as BHoM JSON (e.g. a BarResultRequest) from ETABS through the BHoM adapter."""

    def _go() -> dict[str, Any]:
        adapter = etabs_adapter(model_path)
        req = from_json(request) if request is not None else _filter_request(type_name)
        res = rt.invoke(adapter, rt.find_type("BH.Adapter.BHoMAdapter"), "Pull",
                        {"request": req}, raw_ret=True)["ret"]
        items = [to_json(o) for o in res] if res is not None else []
        return {"count": len(items), "objects": items,
                "adapter": adapter.GetType().FullName,
                "source": f"real ETABS via BHoM {adapter.GetType().Assembly.GetName().Name}"}

    return rt.on_clr(_go)


def push(objects: list[Any], tag: str = "calcgraph", model_path: str | None = None) -> dict[str, Any]:
    """Push BHoM-JSON objects into ETABS through the BHoM adapter; returns what BHoM echoes."""

    def _go() -> dict[str, Any]:
        adapter = etabs_adapter(model_path)
        from System.Collections.Generic import List
        from System import Object

        objs = List[Object]()
        for doc in objects:
            objs.Add(from_json(doc))
        res = rt.invoke(adapter, rt.find_type("BH.Adapter.BHoMAdapter"), "Push",
                        {"objects": objs, "tag": tag}, raw_ret=True)["ret"]
        echoed = [to_json(o) for o in res] if res is not None else []
        return {"pushed": len(objects), "echoed": len(echoed), "objects": echoed,
                "source": f"real ETABS via BHoM {adapter.GetType().Assembly.GetName().Name}"}

    return rt.on_clr(_go)
