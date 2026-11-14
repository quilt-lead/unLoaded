"""Read-only inventory of the desk: what engineering software the bridge could drive.

Pure Python (registry, filesystem, file version resources): it never loads the CLR and
never starts an application, so it is safe to call while people use the desk.
"""

from __future__ import annotations

import ctypes
import getpass
import glob
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
from ctypes import wintypes
from typing import Any

CSI_ROOTS = [r"C:\Program Files\Computers and Structures",
             r"C:\Program Files (x86)\Computers and Structures"]
CSI_API_DLLS = ("ETABSv1.dll", "SAP2000v1.dll", "SAFEv1.dll", "CSiAPIv1.dll")
BHOM_ROOT = os.environ.get("BHOM_ROOT", r"C:\ProgramData\BHoM")
# Products themselves, not their add-ons ("Batch Print for Autodesk Revit 2024" must not match).
PRODUCT_RE = re.compile(
    r"^(Autodesk )?(ETABS|SAP2000|SAFE|CSiBridge|Revit 20\d\d$|AutoCAD 20\d\d|Civil 3D 20\d\d|"
    r"Robot Structural)|BHoM|^Speckle|^(PTC )?Mathcad|^Oasys GSA|^Tekla Structures|^Rhino|"
    r"^Python 3\.\d+\.\d+ \(64-bit\)$",
    re.I,
)


def file_version(path: str) -> str | None:
    """Fixed file version from the PE version resource, or None."""
    try:
        ver = ctypes.windll.version
        size = ver.GetFileVersionInfoSizeW(path, None)
        if not size:
            return None
        buf = ctypes.create_string_buffer(size)
        if not ver.GetFileVersionInfoW(path, 0, size, buf):
            return None
        ptr, length = ctypes.c_void_p(), wintypes.UINT()
        if not ver.VerQueryValueW(buf, "\\", ctypes.byref(ptr), ctypes.byref(length)):
            return None

        class _VS(ctypes.Structure):
            _fields_ = [(n, wintypes.DWORD) for n in (
                "sig", "struc", "ms", "ls", "pms", "pls", "mask", "flags", "os", "type", "sub",
                "dh", "dl")]

        fi = ctypes.cast(ptr, ctypes.POINTER(_VS)).contents
        return f"{fi.ms >> 16}.{fi.ms & 0xFFFF}.{fi.ls >> 16}.{fi.ls & 0xFFFF}"
    except Exception:
        return None


def _uninstall_entries() -> list[dict[str, str]]:
    import winreg

    roots = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]
    seen, out = set(), []
    for hive, path in roots:
        try:
            key = winreg.OpenKey(hive, path)
        except OSError:
            continue
        for i in range(winreg.QueryInfoKey(key)[0]):
            try:
                sub = winreg.OpenKey(key, winreg.EnumKey(key, i))
                name = winreg.QueryValueEx(sub, "DisplayName")[0]
            except OSError:
                continue
            if not PRODUCT_RE.search(name):
                continue
            try:
                version = winreg.QueryValueEx(sub, "DisplayVersion")[0]
            except OSError:
                version = ""
            if (name, version) in seen:
                continue
            seen.add((name, version))
            out.append({"name": name, "version": version})
    return sorted(out, key=lambda e: e["name"])


def csi_installs() -> list[dict[str, Any]]:
    """CSI products on disk, with the OAPI assembly each exposes (licence state is unknown
    until the product is started: see POST /csi/start)."""
    found = []
    for root in CSI_ROOTS:
        for d in sorted(glob.glob(os.path.join(root, "*"))):
            if not os.path.isdir(d):
                continue
            apis = [n for n in CSI_API_DLLS if os.path.isfile(os.path.join(d, n))]
            exes = [os.path.basename(p) for p in glob.glob(os.path.join(d, "*.exe"))
                    if re.match(r"(ETABS|SAP2000|SAFE|CSiBridge)\.exe$", os.path.basename(p), re.I)]
            if not apis and not exes:
                continue
            exe = os.path.join(d, exes[0]) if exes else None
            found.append({
                "product": os.path.basename(d),
                "dir": d,
                "exe": exe,
                "exe_version": file_version(exe) if exe else None,
                "api_dlls": apis,
            })
    return found


def bhom() -> dict[str, Any]:
    asm = os.path.join(BHOM_ROOT, "Assemblies")
    if not os.path.isdir(asm):
        return {"installed": False, "root": BHOM_ROOT}
    dlls = glob.glob(os.path.join(asm, "*.dll"))
    adapters = sorted(os.path.basename(p)[:-4] for p in dlls if p.endswith("_Adapter.dll"))
    core = os.path.join(asm, "BHoM.dll")
    return {
        "installed": True,
        "root": BHOM_ROOT,
        "assemblies": len(dlls),
        "bhom_dll_version": file_version(core) if os.path.isfile(core) else None,
        "adapters": adapters,
        "etabs_adapters": [a for a in adapters if "ETABS" in a.upper()],
    }


def _apps() -> dict[str, Any]:
    pf = r"C:\Program Files"
    revit = {os.path.basename(d): file_version(os.path.join(d, "Revit.exe"))
             for d in sorted(glob.glob(os.path.join(pf, "Autodesk", "Revit 20*")))
             if os.path.isfile(os.path.join(d, "Revit.exe"))}
    acad = {os.path.basename(d): file_version(os.path.join(d, "acad.exe"))
            for d in sorted(glob.glob(os.path.join(pf, "Autodesk", "AutoCAD 20*")))
            if os.path.isfile(os.path.join(d, "acad.exe"))}
    mathcad = sorted(os.path.basename(d) for d in glob.glob(os.path.join(pf, "PTC", "Mathcad*")))
    speckle = sorted(d for d in (
        os.path.join(os.environ.get("APPDATA", ""), "Speckle"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Speckle"),
        os.path.join(pf, "Speckle"),
    ) if os.path.isdir(d))
    return {"revit": revit, "autocad": acad, "mathcad": mathcad, "speckle_dirs": speckle}


def _dotnet() -> dict[str, Any]:
    out: dict[str, Any] = {"runtimes": [], "netfx_release": None}
    exe = shutil.which("dotnet")
    if exe:
        try:
            r = subprocess.run([exe, "--list-runtimes"], capture_output=True, text=True, timeout=20)
            out["runtimes"] = [ln.split(" [")[0] for ln in r.stdout.splitlines() if ln.strip()]
        except Exception as exc:
            out["runtimes_error"] = str(exc)
    try:
        import winreg

        k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                           r"SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full")
        out["netfx_release"] = winreg.QueryValueEx(k, "Release")[0]
        out["netfx_481_or_later"] = out["netfx_release"] >= 533320
    except OSError:
        pass
    return out


def smart_app_control() -> str:
    """Smart App Control blocks unsigned/unreputed DLLs (all of BHoM) when enforcing."""
    try:
        import winreg

        k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\CI\Policy")
        state = winreg.QueryValueEx(k, "VerifiedAndReputablePolicyState")[0]
        return {0: "off", 1: "enforcing", 2: "evaluation"}.get(state, f"unknown ({state})")
    except OSError:
        return "not present"


def _sessions() -> list[dict[str, Any]]:
    """Interactive Windows sessions, from the owners of explorer.exe (Windows Home has no quser)."""
    ps = ("Get-CimInstance Win32_Process -Filter \"Name='explorer.exe'\" | ForEach-Object { "
          "$o = Invoke-CimMethod -InputObject $_ -MethodName GetOwner; "
          "'{0}|{1}' -f $_.SessionId, $o.User }")
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                           capture_output=True, text=True, timeout=30)
        rows = [ln.split("|") for ln in r.stdout.splitlines() if "|" in ln]
        return [{"session": int(s), "user": u} for s, u in rows]
    except Exception:
        return []


def inventory() -> dict[str, Any]:
    total, _used, free = shutil.disk_usage("C:\\")
    return {
        "host": socket.gethostname(),
        "bridge_user": getpass.getuser(),
        "os": platform.platform(),
        "python": sys.version.split()[0],
        "python_exe": sys.executable,
        "interactive_sessions": _sessions(),
        "disk_c_free_gb": round(free / 2**30, 1),
        "disk_c_total_gb": round(total / 2**30, 1),
        "csi": csi_installs(),
        "bhom": bhom(),
        "apps": _apps(),
        "dotnet": _dotnet(),
        "smart_app_control": smart_app_control(),
        "installed_products": _uninstall_entries(),
    }
