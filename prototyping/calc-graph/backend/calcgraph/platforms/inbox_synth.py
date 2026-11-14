"""INCOMING platform items for the synthetic project: RFIs, change events and a change order request that
arrived in the last few days and are waiting on the engineer of record. Part of the ONE construction-state
generator (synthetic.build_state calls `incoming`), so every adapter serves them exactly like the rest.

As they would arrive from a GC: free text naming elements the way site people do (an id, a grid, a size,
or only a description), with NO registry element ids linked on the platform record (element_ids = []).
Reading them is the inbox's AI step; until an engineer confirms a reading they touch no element, so they
change no health meter, construction status or change-order estimate.

`incoming(...)` also returns the answer key (what each item was written to mean) for scoring the AI
reading. The key never goes onto a platform record or into anything the AI step is shown.

Everything is SYNTHETIC: fictional project, companies and people.
"""
from __future__ import annotations

from typing import Callable

# (ref, kind, number, subject/title, body, sender key, created offset, due offset, sheet, spec, truth)
# offsets are working days from the data date (negative = before it). truth: change_type, elements
# (primary first), move (dx, dy ft; +x east = toward higher grid numbers, +y north = toward line D),
# new_section, ambiguous (True when the item genuinely cannot be resolved to one element/change).
ITEMS: list[dict] = [
    {"ref": "RFI-008", "kind": "rfi", "subject": "Column COL-2B vs Level 2 supply duct main",
     "body": "Mechanical coordination (clash report MC-14): the 30x18 supply duct main on Level 2 runs north-south "
             "and hits column COL-2B at grid 2/B. Can COL-2B shift 2 ft east to clear the duct? Please confirm "
             "and advise the framing impact before we release the duct shop drawings.",
     "from": "gc_pm", "created": -1, "due": 8, "sheet": "S-201", "spec": "05 12 00",
     "truth": {"change_type": "move_column", "elements": ["COL-2B"], "move": [2.0, 0.0]}},
    {"ref": "RFI-009", "kind": "rfi", "subject": "Web penetration for roof drain leader at Level 2 beam",
     "body": "Plumbing needs a 6 in. diameter penetration through the web of beam B-L2-23-BC1 at midspan for a "
             "roof drain leader. Is a web opening acceptable, and what reinforcement is required?",
     "from": "gc_super", "created": -2, "due": 5, "sheet": "S-201", "spec": "05 12 00",
     "truth": {"change_type": "add_opening", "elements": ["B-L2-23-BC1"]}},
    {"ref": "RFI-010", "kind": "rfi", "subject": "Column near stair in the way of door swing",
     "body": "The column on the north side of bay 2-3 next to the stair is in the way of the new door swing shown "
             "on A-201 rev 3. Can it move about 18 inches?",
     "from": "architect", "created": -1, "due": 7, "sheet": "S-201", "spec": "05 12 00",
     "truth": {"change_type": "move_column", "elements": [], "candidates": ["COL-2C", "COL-3C", "COL-2D", "COL-3D"],
               "ambiguous": True}},
    {"ref": "RFI-011", "kind": "rfi", "subject": "Lobby exposed deck paint color and stair rail finish",
     "body": "Please confirm the paint color for the exposed lobby ceiling deck and the finish for the stair "
             "guard rails. Finish schedule on A-601 is blank for both.",
     "from": "gc_pm", "created": -3, "due": 4, "sheet": "S-001", "spec": "09 91 00",
     "truth": {"change_type": "not_structural", "elements": []}},
    {"ref": "RFI-012", "kind": "rfi", "subject": "Shift column at grid 4/B to suit revised partitions",
     "body": "Tenant fit-out revision TF-2 moves the corridor wall on Level 2. Request that the column at grid "
             "4/B move 3 ft north, toward line C, so it lands inside the new partition.",
     "from": "architect", "created": -2, "due": 10, "sheet": "S-201", "spec": "05 12 00",
     "truth": {"change_type": "move_column", "elements": ["COL-4B"], "move": [0.0, 3.0]}},
    {"ref": "CE-005", "kind": "change_event", "subject": "Substitution request: W10x54 for W10x49 at COL-3C",
     "body": "Keelson Steel requests to substitute a W10x54 for the specified W10x49 at column COL-3C (mill "
             "rolling schedule; W10x49 not available until January). Submitted as price neutral; EOR to review.",
     "from": "steel_pm", "created": -1, "reason": "Substitution Request", "amount": 0.0, "cost_code": "05 12 00",
     "truth": {"change_type": "substitute_section", "elements": ["COL-3C"], "new_section": "W10X54"}},
    {"ref": "CE-006", "kind": "change_event", "subject": "Owner request: delete interior column at lobby",
     "body": "Owner-directed change (OD-03): delete the interior column at grid 2/C so the Level 1 lobby is "
             "column-free. EOR to advise the framing transfer and cost before the owner decides.",
     "from": "owner_rep", "created": -3, "reason": "Owner Change", "amount": 0.0, "cost_code": "05 12 00",
     "truth": {"change_type": "remove_column", "elements": ["COL-2C"]}},
    {"ref": "CE-007", "kind": "change_event", "co_ref": "CO-004",
     "subject": "COR-07: field-modify shear tab at G-L3-2-BC to COL-2B",
     "body": "Change order request from Keelson Steel: added cost for field-modifying the extended shear tab at "
             "girder G-L3-2-BC where it frames into COL-2B, per the pending RFI-002 response. Requesting "
             "$1,950 (2 ironworkers x 6 h + plate).",
     "from": "steel_pm", "created": -2, "reason": "Change Order Request", "amount": 1950.0, "cost_code": "05 12 10",
     "truth": {"change_type": "modify_connection", "elements": ["CX-G-L3-2-BC-i", "G-L3-2-BC", "COL-2B"]}},
]


def incoming(els: dict, d2s: Callable[[int], str], data_day: int, people: dict, companies: dict) -> dict:
    """{"rfis": [...], "change_events": [...], "change_orders": [...], "key": [...]} shaped exactly like the
    state's own RFIs / change events / change orders (same keys), all unlinked (element_ids = [])."""
    rfis, ces, cos, key = [], [], [], []
    for it in ITEMS:
        missing = [e for e in it["truth"]["elements"] + it["truth"].get("candidates", []) if e not in els]
        if missing:
            raise ValueError(f"inbox item {it['ref']} names elements not in the design: {missing}")
        created = d2s(data_day + it["created"])
        if it["kind"] == "rfi":
            sender = people[it["from"]]
            rfis.append({"ref": it["ref"], "number": it["ref"], "subject": it["subject"], "question": it["body"],
                         "answer": None, "status": "open", "element_ids": [], "drawing_number": it["sheet"],
                         "spec_section": it["spec"], "cost_impact": "tbd", "schedule_impact": "tbd",
                         "assignee": people["eor"], "rfi_manager": people["gc_pm"], "received_from": sender,
                         "ball_in_court": "Assignees", "inbound": True,
                         "dates": {"created": created, "due": d2s(data_day + it["due"]), "answered": None, "closed": None}})
        else:
            ces.append({"ref": it["ref"], "number": it["ref"].split("-")[1], "title": it["subject"],
                        "description": it["body"], "status": "pending", "reason": it["reason"], "element_ids": [],
                        "line_items": [{"cost_code": it["cost_code"], "description": it["subject"], "amount": it["amount"]}],
                        "amount": it["amount"], "created": created, "co_refs": [it["co_ref"]] if it.get("co_ref") else [],
                        "inbound": True, "received_from": people[it["from"]]})
            if it.get("co_ref"):
                cos.append({"ref": it["co_ref"], "number": it["co_ref"].split("-")[1], "title": it["subject"],
                            "status": "pending", "co_type": "potential", "change_event_ref": it["ref"],
                            "amount": it["amount"], "schedule_days": 0, "element_ids": [], "created": created,
                            "approved": None, "inbound": True})
        key.append({"ref": it.get("co_ref") or it["ref"], "kind": "change_order" if it.get("co_ref") else it["kind"],
                    "item_ref": it["ref"], **it["truth"]})
    return {"rfis": rfis, "change_events": ces, "change_orders": cos, "key": key}
