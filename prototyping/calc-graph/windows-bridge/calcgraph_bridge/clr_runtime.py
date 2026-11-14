"""One .NET runtime per bridge process, driven from ONE thread.

pythonnet loads a single CLR into the process (``CALCGRAPH_CLR`` = ``netfx`` (default:
BHoM and the CSI OAPI assemblies target .NET Framework) or ``coreclr``). Every .NET call
goes through :func:`on_clr`, which runs it on a single dedicated worker thread: ETABS and
the BHoM adapters are not thread-safe, and FastAPI would otherwise call in from its pool.

Calls into vendor APIs go through :func:`invoke`, which uses reflection instead of
pythonnet's overload/out-parameter guessing: by-ref parameters get typed placeholders,
missing optional parameters get their declared defaults, and every by-ref value is returned
by name. That keeps one code path working across CSI API versions whose signatures differ.
"""

from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

_lock = threading.Lock()
_state: dict[str, Any] = {"loaded": False, "kind": None, "error": None}
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="clr")
_probe_dirs: list[str] = []
_handlers: list[Any] = []  # keep the AssemblyResolve delegate alive

CLR_TIMEOUT_S = float(os.environ.get("CALCGRAPH_CLR_TIMEOUT_S", "900"))


def on_clr(fn: Callable[..., Any], *args: Any, timeout: float | None = None, **kwargs: Any) -> Any:
    """Run ``fn`` on the single CLR thread (loading the runtime first) and return its result."""

    def _run() -> Any:
        _ensure_loaded()
        return fn(*args, **kwargs)

    return _executor.submit(_run).result(timeout=timeout or CLR_TIMEOUT_S)


def add_probe_dir(path: str) -> None:
    """Let the runtime resolve dependencies from ``path`` (e.g. BHoM's Assemblies folder)."""
    if path not in _probe_dirs:
        _probe_dirs.append(path)


def state() -> dict[str, Any]:
    return dict(_state)


def _ensure_loaded() -> None:
    with _lock:
        if _state["loaded"]:
            return
        kind = os.environ.get("CALCGRAPH_CLR", "netfx")
        try:
            from pythonnet import load

            load(kind)
            import clr  # noqa: F401  (side effect: enables `import System`)
            from System import AppDomain, ResolveEventHandler
            from System.Reflection import Assembly, AssemblyName

            def _resolve(_sender: Any, args: Any) -> Any:
                name = AssemblyName(args.Name).Name
                for d in _probe_dirs:
                    p = os.path.join(d, name + ".dll")
                    if os.path.isfile(p):
                        return Assembly.LoadFrom(p)
                return None

            handler = ResolveEventHandler(_resolve)
            AppDomain.CurrentDomain.AssemblyResolve += handler
            _handlers.append(handler)
            _state.update(loaded=True, kind=kind, error=None)
        except Exception as exc:  # surfaced by /health and /dotnet/probe
            _state.update(error=f"{type(exc).__name__}: {exc}", kind=kind)
            raise


def add_reference(path: str) -> Any:
    """Load an assembly by full path and return it (CLR thread only)."""
    import clr

    add_probe_dir(os.path.dirname(path))
    return clr.AddReference(path)


def find_type(full_name: str) -> Any:
    """Resolve a type by full name across every loaded assembly (CLR thread only)."""
    from System import AppDomain

    for asm in AppDomain.CurrentDomain.GetAssemblies():
        try:
            t = asm.GetType(full_name)
        except Exception:
            continue
        if t is not None:
            return t
    raise LookupError(f".NET type not loaded: {full_name}")


def _placeholder(ptype: Any) -> Any:
    from System import Activator, Array, Enum

    t = ptype.GetElementType() if ptype.IsByRef else ptype
    if t.IsArray:
        return Array.CreateInstance(t.GetElementType(), 0)
    if t.FullName == "System.String":
        return ""
    if t.IsEnum:
        return Enum.ToObject(t, 0)
    if t.IsValueType:
        return Activator.CreateInstance(t)
    return None


def _coerce(value: Any, ptype: Any) -> Any:
    from System import Array, Convert, Enum

    t = ptype.GetElementType() if ptype.IsByRef else ptype
    if value is None:
        return None
    if t.IsEnum:
        if isinstance(value, str):
            return Enum.Parse(t, value)
        return Enum.ToObject(t, int(value))
    if t.IsArray and isinstance(value, (list, tuple)):
        arr = Array.CreateInstance(t.GetElementType(), len(value))
        for i, v in enumerate(value):
            arr[i] = v  # typed indexer: pythonnet converts to the element type
        return arr
    if t.IsPrimitive or t.FullName in ("System.String", "System.Decimal"):
        return Convert.ChangeType(value, t)
    return value


def to_py(value: Any) -> Any:
    """Convert a .NET value (arrays, enums, primitives) into JSON-safe Python."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    try:
        from System import Array, Enum

        if isinstance(value, Array):
            return [to_py(v) for v in value]
        if isinstance(value, Enum):
            return str(value)
    except Exception:
        pass
    return str(value)


def _set_slot(args: Any, i: int, value: Any, ptype: Any) -> None:
    """Store ``value`` in the object[] ``args`` as the parameter's .NET type.

    pythonnet 3 turns a Python int/float/bool placed in an ``object`` slot into a PyObject
    wrapper (``Python.Runtime.PyInt``), which reflection cannot bind to ``Int32&``. Value
    types therefore go through a one-element typed array (whose indexer converts) and an
    Array.Copy, which boxes inside .NET.
    """
    from System import Array

    t = ptype.GetElementType() if ptype.IsByRef else ptype
    if value is not None and t.IsValueType:
        typed = Array.CreateInstance(t, 1)
        typed[0] = value
        Array.Copy(typed, 0, args, i, 1)
    else:
        args.SetValue(value, i)


def pick_method(iface: Any, name: str, nparams: int | None = None,
                names: set[str] | None = None) -> Any:
    """Choose an overload: exact ``nparams`` if given; else, when inputs are named, the
    SMALLEST overload that has every named parameter (so unnamed extras such as a count
    are not silently zero); with no inputs, the largest (every by-ref output)."""
    methods = [m for m in iface.GetMethods() if m.Name == name]
    if not methods:
        # members declared on inherited interfaces
        for base in iface.GetInterfaces():
            methods += [m for m in base.GetMethods() if m.Name == name]
    if nparams is not None:
        exact = [m for m in methods if len(m.GetParameters()) == nparams]
        methods = exact or [m for m in methods if len(m.GetParameters()) > nparams]
    if not methods:
        raise LookupError(f"{iface.FullName}.{name} not found")
    if nparams is None and names:
        named = [m for m in methods if names <= {p.Name for p in m.GetParameters()}]
        if named:
            return min(named, key=lambda m: len(m.GetParameters()))
    return max(methods, key=lambda m: len(m.GetParameters()))


def invoke(target: Any, iface: Any, name: str,
           inputs: dict[str, Any] | list[Any] | None = None,
           nparams: int | None = None, raw_ret: bool = False) -> dict[str, Any]:
    """Call ``iface.name`` on ``target`` by reflection.

    Returns ``{"ret": <return value>, "<by-ref param>": <value>, ...}``. ``inputs`` maps
    parameter names to values (or is a positional list); unnamed by-ref parameters get typed placeholders and unnamed
    optional parameters their declared defaults.
    """
    from System import Array, Reflection, Type

    if isinstance(inputs, (list, tuple)):
        mi = pick_method(iface, name, len(inputs) if nparams is None else nparams)
        params = list(mi.GetParameters())
        inputs = {p.Name: v for p, v in zip(params, inputs)}
    else:
        inputs = inputs or {}
        mi = pick_method(iface, name, nparams, set(inputs))
        params = list(mi.GetParameters())
    unknown = set(inputs) - {p.Name for p in params}
    if unknown:
        sig = ", ".join(f"{p.ParameterType.Name} {p.Name}" for p in params)
        raise ValueError(f"{name} has no parameter(s) {sorted(unknown)}; signature: ({sig})")
    args = Array.CreateInstance(Type.GetType("System.Object"), len(params))
    for i, p in enumerate(params):
        if p.Name in inputs:
            v = _coerce(inputs[p.Name], p.ParameterType)
        elif p.ParameterType.IsByRef:
            v = _placeholder(p.ParameterType)
        elif p.HasDefaultValue:
            # an enum default comes back from reflection as its underlying int
            v = _coerce(p.DefaultValue, p.ParameterType)
        else:
            v = _placeholder(p.ParameterType)
        _set_slot(args, i, v, p.ParameterType)
    try:
        ret = mi.Invoke(target, args)
    except Reflection.TargetInvocationException as exc:
        raise RuntimeError(f"{iface.Name}.{name} threw: {exc.InnerException}") from None
    out: dict[str, Any] = {"ret": ret if raw_ret else to_py(ret)}
    for i, p in enumerate(params):
        if p.ParameterType.IsByRef:
            out[p.Name] = to_py(args.GetValue(i))
    return out
