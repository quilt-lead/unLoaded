"""Drive the Speckle next-gen connector panel (DUI3) inside Revit 2024 with no clicks, over CDP.

Revit 2024 hosts add-in web panels in its own CEF, started with --remote-debugging-port=8088 on
127.0.0.1, and the Speckle panel (https://dui.speckle.systems/) is one of its pages. This script
runs on the desk (any session: the port is loopback) and evaluates JavaScript in that page, so it
presses the panel's own buttons; it never touches the Revit model directly. Needs `websockets`.

    python speckle_dui.py read                          # buttons + visible text
    python speckle_dui.py click "Load"                  # exact label, else a button whose text starts with it
    python speckle_dui.py click-index 0                 # nth <button> (the header's publish icon has no label)
    python speckle_dui.py search "revit-publish"        # type into the wizard's "Search in ..." box
    python speckle_dui.py state                         # model cards in the ACTIVE document (versions loaded)
    python speckle_dui.py selection                     # what is selected in Revit, per the connector

Load flow used on 2026-11-14 (a NEW project document active first - the panel acts on the active
document): click "Load" -> click "<project>" -> click "<model path with spaces>" -> click the
version card ("I cal 2 minutes ago Latest") -> "Model loaded!". Publish: click "Highlight"
(selects the received elements), click-index 0, "<project>", search + click the model,
"Proceed" if it warns about overwriting, "Publish" -> "Version created!".
"""
from __future__ import annotations

import asyncio
import json
import sys
import urllib.request

PORT = 8088

READ_JS = """
(() => {
  const btns = [...document.querySelectorAll('button, [role=button], a, input')]
    .map(b => (b.innerText || b.value || b.placeholder || b.getAttribute('aria-label') || '').trim()).filter(Boolean);
  return JSON.stringify({btns: btns.slice(0, 80), text: document.body.innerText.slice(0, 3000)}, null, 1);
})()
"""

CLICK_JS = """
(async () => {
  const want = %s, waitMs = %d, sleep = ms => new Promise(r => setTimeout(r, ms));
  const norm = s => (s || '').trim().replace(/\\s+/g, ' ');
  let el = [...document.querySelectorAll('button,[role=button],a,li,div,span,h1,h2,h3,h4,p')]
    .filter(e => norm(e.innerText) === want).pop();
  if (!el) el = [...document.querySelectorAll('button,[role=button],a,li')].filter(e => norm(e.innerText).startsWith(want)).pop();
  if (!el) return 'NOT FOUND: ' + want;
  (el.closest('button,[role=button],a,li') || el).click();
  await sleep(waitMs);
  return null;
})()
"""

CLICK_INDEX_JS = """
(async () => { document.querySelectorAll('button')[%d].click(); await new Promise(r => setTimeout(r, %d)); return null; })()
"""

SEARCH_JS = """
(async () => {
  const inp = [...document.querySelectorAll('input')].find(i => (i.placeholder || '').startsWith('Search in'));
  if (!inp) return 'NO SEARCH BOX';
  inp.focus(); inp.value = %s; inp.dispatchEvent(new Event('input', {bubbles: true}));
  await new Promise(r => setTimeout(r, %d)); return null;
})()
"""

STATE_JS = """
(async () => { const s = await baseBinding.getDocumentState();
  return JSON.stringify((s.models || []).map(m => ({type: m.typeDiscriminator, project: m.projectId, model: m.modelId,
    selectedVersion: m.selectedVersionId, latestVersion: m.latestVersionId})), null, 1); })()
"""

SELECTION_JS = """
(async () => { const s = await selectionBinding.getSelection();
  return JSON.stringify({count: (s.selectedObjectIds || []).length, summary: s.summary}); })()
"""


def _target() -> str:
    for t in json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/list", timeout=10)):
        if "dui.speckle" in t.get("url", ""):
            return t["webSocketDebuggerUrl"]
    raise SystemExit(f"no Speckle panel page on 127.0.0.1:{PORT} (Revit not running, or the panel never opened)")


async def _eval(expr: str):
    import websockets
    async with websockets.connect(_target(), max_size=50_000_000, open_timeout=10) as ws:
        await ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {
            "expression": expr, "awaitPromise": True, "returnByValue": True, "timeout": 600000}}))
        while True:
            msg = json.loads(await asyncio.wait_for(ws.recv(), 900))
            if msg.get("id") == 1:
                res = msg.get("result", {})
                if "exceptionDetails" in res:
                    raise SystemExit("JS exception: " + json.dumps(res["exceptionDetails"])[:2000])
                return res.get("result", {}).get("value")


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    cmd, rest = argv[0], argv[1:]
    wait = int(rest[1]) if len(rest) > 1 else 3000
    if cmd == "click":
        out = asyncio.run(_eval(CLICK_JS % (json.dumps(rest[0]), wait)))
    elif cmd == "click-index":
        out = asyncio.run(_eval(CLICK_INDEX_JS % (int(rest[0]), wait)))
    elif cmd == "search":
        out = asyncio.run(_eval(SEARCH_JS % (json.dumps(rest[0]), wait)))
    elif cmd == "state":
        out = asyncio.run(_eval(STATE_JS))
    elif cmd == "selection":
        out = asyncio.run(_eval(SELECTION_JS))
    elif cmd == "read":
        out = None
    else:
        raise SystemExit(f"unknown command {cmd}")
    if out:                                     # an error message or a query result
        print(out)
        if str(out).startswith(("NOT FOUND", "NO SEARCH")):
            return 1
        if cmd in ("state", "selection"):
            return 0
    print(asyncio.run(_eval(READ_JS)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
