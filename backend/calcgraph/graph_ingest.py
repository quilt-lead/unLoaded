"""Serialized element graph -> the element rows and load-path edges the calc engine maps onto.

The element graph is built ONCE, by the TypeScript packages the UI runs (packages/ifc-parser ->
packages/element-graph, `ElementGraph.serialize()`; in Node: backend/scripts/build_graph.mjs). The
backend never parses an IFC for elements or topology: it reads that graph, so the UI and the calc
engine can never disagree about what is in a model.

Format: {"format": "unloaded.element-graph", "version": 1, meta, levels, nodes, edges}
(packages/element-graph/src/model/graph-types.ts). Mapping to the engine's element row:

  global_id  node.id                     (IFC GlobalId - stable across revisions)
  express_id node.source.nativeId
  ifc_type   node.source.nativeType      (falls back to the node kind)
  cat        node.kind -> Beam / Column / Slab / Wall / Footing / Pile / Brace / Connection / Other
             (connections are elements; fasteners count as Connection, as the v1 reader did)
  mark, name node.mark, node.name
  type_name  params["Attr.ObjectType"]
  profile    node.profile                (the parser's normalised section designation)
  storey     name of node.levelId in graph.levels ("" when the file states no storey)
  params     node.params                 (open bag, keys namespaced by origin)
  geom       bbox min / max + axis start / end (p1 / p2) when the graph has them

Load path = the graph's `supports` edges (a is supported by b: load flows a -> b) as
{src: a, dst: b, kind: "supports", rule: first evidence rule, gap_m}. `connects` edges are
physical connectivity, not load path; `connectivity()` returns them for the export.
"""
from __future__ import annotations

import json

FORMAT = "unloaded.element-graph"
VERSION = 1

CAT = {"beam": "Beam", "column": "Column", "slab": "Slab", "wall": "Wall", "footing": "Footing", "pile": "Pile",
       "brace": "Brace", "connection": "Connection", "fastener": "Connection"}


class GraphError(ValueError):
    """The upload is not a serialized element graph this engine reads (message is user-facing)."""


def parse(raw: bytes | str) -> dict:
    """Decode and validate a serialized graph. Raises GraphError with the reason."""
    try:
        g = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise GraphError(f"graph is not valid JSON: {e}") from None
    if not isinstance(g, dict):
        raise GraphError("graph must be a JSON object")
    if g.get("format") != FORMAT:
        raise GraphError(f"graph format must be {FORMAT!r} (got {g.get('format')!r}) - send ElementGraph.serialize()")
    if g.get("version") != VERSION:
        raise GraphError(f"graph version {g.get('version')!r} is not supported (this engine reads version {VERSION})")
    for key in ("levels", "nodes", "edges"):
        if not isinstance(g.get(key), list):
            raise GraphError(f"graph.{key} must be a list")
    ids = set()
    for i, n in enumerate(g["nodes"]):
        if not isinstance(n, dict) or not isinstance(n.get("id"), str) or not n["id"] or not isinstance(n.get("kind"), str):
            raise GraphError(f"graph.nodes[{i}] needs a string id and kind")
        if n["id"] in ids:
            raise GraphError(f"graph.nodes[{i}]: duplicate node id {n['id']!r}")
        ids.add(n["id"])
    for i, e in enumerate(g["edges"]):
        if not isinstance(e, dict) or not isinstance(e.get("kind"), str):
            raise GraphError(f"graph.edges[{i}] needs a string kind")
        if e.get("a") not in ids or e.get("b") not in ids:
            raise GraphError(f"graph.edges[{i}] ({e.get('id')!r}) references a node that is not in graph.nodes")
    return g


def _rule(e: dict) -> str:
    ev = e.get("evidence") or []
    return str(ev[0].get("rule") or "") if ev and isinstance(ev[0], dict) else ""


def _gap(e: dict):
    for ev in e.get("evidence") or []:
        gap = (ev.get("detail") or {}).get("gap_m") if isinstance(ev, dict) else None
        if isinstance(gap, (int, float)):
            return gap
    return None


def _geom(n: dict) -> dict | None:
    g = n.get("geometry") or {}
    bb = g.get("bbox")
    if not bb:
        return None
    out = {"min": list(bb["min"]), "max": list(bb["max"])}
    ax = g.get("axis")
    if ax:
        out["p1"], out["p2"] = list(ax["start"]), list(ax["end"])
    return out


def elements(g: dict) -> list[dict]:
    levels = {lv["id"]: lv.get("name") or "" for lv in g["levels"] if isinstance(lv, dict) and "id" in lv}
    out = []
    for n in g["nodes"]:
        src = n.get("source") or {}
        params = n.get("params") or {}
        out.append({
            "global_id": n["id"], "express_id": src.get("nativeId"),
            "ifc_type": src.get("nativeType") or n["kind"], "cat": CAT.get(n["kind"], "Other"),
            "mark": n.get("mark") or "", "name": n.get("name") or "",
            "type_name": str(params.get("Attr.ObjectType") or ""), "profile": n.get("profile") or "",
            "storey": levels.get(n.get("levelId"), ""), "params": params, "geom": _geom(n),
        })
    return out


def load_path(g: dict) -> list[dict]:
    """The graph's `supports` edges, src -> dst = a -> b (load flows a -> b)."""
    return sorted(({"src": e["a"], "dst": e["b"], "kind": "supports", "rule": _rule(e), "gap_m": _gap(e)}
                   for e in g["edges"] if e["kind"] == "supports"), key=lambda e: (e["src"], e["dst"]))


def connectivity(g: dict) -> list[dict]:
    """The graph's `connects` edges (undirected, a < b as the graph stores them)."""
    return sorted(({"a": e["a"], "b": e["b"], "rule": _rule(e),
                    "explicit": any(isinstance(ev, dict) and ev.get("source") == "explicit" for ev in e.get("evidence") or [])}
                   for e in g["edges"] if e["kind"] == "connects"), key=lambda e: (e["a"], e["b"]))
