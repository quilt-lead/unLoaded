"""Read every synthetic INCOMING inbox item with the AI step and score each reading against what the
generator intended (platforms/inbox_synth.py answer key). Readings go through calcgraph.inbox.read_item,
i.e. the same calcgraph.ai.extract call the inbox route makes, so they land in the same content-hash
cache the app serves from (a re-run costs nothing).

  uv run --extra ai python scripts/read_inbox.py [--cache-only] [--out data/store/inbox/score.json]

Real calls need CALCGRAPH_AI_ENABLE_REAL=1, ANTHROPIC_API_KEY and CALCGRAPH_AI_MAX_RUN_USD (> 0); without
them only cached readings are scored. Prints per-item score, total, and the run's spend.

Score per item (1.0 max): change type 0.4; primary element 0.3 (an ambiguous item scores it when NO single
primary is claimed); move vector within 0.05 ft / new section exact 0.2 (items without either get it when
none is invented); unresolved used correctly 0.1 (non-empty exactly when the item is ambiguous).
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from calcgraph import ai, inbox  # noqa: E402
from calcgraph.platforms import get_mock_adapters, get_state, load_design  # noqa: E402

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))


def score(truth: dict, r: dict | None) -> tuple[float, list[str]]:
    if r is None:
        return 0.0, ["no reading"]
    notes, s = [], 0.0
    if r["change_type"] == truth["change_type"]:
        s += 0.4
    else:
        notes.append(f"type {r['change_type']} != {truth['change_type']}")
    prim = [e["element_id"] for e in r["elements"] if e["role"] == "primary"]
    amb = bool(truth.get("ambiguous"))
    if amb:
        if len(prim) != 1:
            s += 0.3
        else:
            notes.append(f"claimed one primary {prim} for an ambiguous item")
    elif truth["elements"]:
        if prim[:1] == truth["elements"][:1]:
            s += 0.3
        else:
            notes.append(f"primary {prim} != {truth['elements'][:1]}")
    else:
        if not prim:
            s += 0.3
        else:
            notes.append(f"primary {prim} for an item with no element")
    if "move" in truth:
        mv = r.get("move")
        if mv and abs(mv["dx_ft"] - truth["move"][0]) <= 0.05 and abs(mv["dy_ft"] - truth["move"][1]) <= 0.05:
            s += 0.2
        else:
            notes.append(f"move {mv} != {truth['move']}")
    elif "new_section" in truth:
        if (r.get("new_section") or "").upper().replace(" ", "") == truth["new_section"]:
            s += 0.2
        else:
            notes.append(f"section {r.get('new_section')} != {truth['new_section']}")
    else:
        if amb or (not r.get("move") and not r.get("new_section")):
            s += 0.2
        else:
            notes.append(f"invented move/section {r.get('move')} {r.get('new_section')}")
    if bool(r.get("unresolved")) == amb:
        s += 0.1
    else:
        notes.append(f"unresolved={r.get('unresolved')} (ambiguous={amb})")
    return round(s, 2), notes


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache-only", action="store_true")
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "store", "inbox", "score.json"))
    a = ap.parse_args()
    d = load_design()
    key = {k["ref"]: k for k in get_state(d).inbox_key}
    adapter = get_mock_adapters(d, ["procore"])[0]
    items = [i for i in inbox.list_items(adapter) if i["ref"] in key]
    run = ai.Run()
    rows, total = [], 0.0
    for it in sorted(items, key=lambda i: i["number"]):
        t = key[it["ref"]]
        try:
            out = inbox.read_item(it, d, cache_only=a.cache_only, run=run)
            r, err = out["reading"], None
            cached = out.get("cached")
            usage = out.get("usage")
        except Exception as e:   # noqa: BLE001 - reported per item
            r, err, cached, usage = None, f"{type(e).__name__}: {e}", None, None
        sc, notes = score(t, r)
        total += sc
        rows.append({"ref": it["ref"], "number": it["number"], "truth": t, "reading": r, "score": sc, "notes": notes,
                     "cached": cached, "usage": usage, "error": err})
        print(f"{it['number']:8} {sc:4.2f}  intended {t['change_type']:18} {','.join(t['elements'][:1]) or '-':12} "
              f"| read {r['change_type'] if r else '-':18} "
              f"{','.join(e['element_id'] for e in r['elements'] if e['role'] == 'primary') if r else '-':12} "
              f"conf {r['confidence'] if r else '-'}  {'cached' if cached else ''} {err or ''} {'; '.join(notes)}")
    summary = {"items": len(rows), "score": round(total, 2), "max": len(rows), "pct": round(100 * total / max(len(rows), 1), 1),
               "run": run.summary(), "provider": inbox.PROVIDER, "model": ai.get_provider(inbox.PROVIDER).model_id}
    print(json.dumps(summary))
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w") as fh:
        json.dump({"summary": summary, "rows": rows, "computed_at": inbox.now_et()}, fh, indent=1)


if __name__ == "__main__":
    main()
