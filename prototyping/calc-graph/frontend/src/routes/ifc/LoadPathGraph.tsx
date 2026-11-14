// Load-path graph: element lanes (from the BIM model) beside the calc graph (from the calc package),
// with the top live element -> calc mapping drawn between them. Port of the legacy SVG graph onto
// the shared GraphView (React Flow + dagre).
import { useMemo, useState } from "react";
import { GraphView, type GraphEdge, type GraphLane, type GraphNode } from "../../components/GraphView";
import { Legend } from "../../components/Legend";
import type { IfcImpact } from "../../api/types";
import { CAT_COLORS, elLabel, linksFor, type IfcIndex, type Sel } from "./model";

const LANE_DEFS: { id: string; label: string; cats: string[]; info: GraphLane["info"] }[] = [
  { id: "slabs", label: "Slabs", cats: ["Slab"], info: "graph.ifc-lane-slabs" },
  { id: "beams", label: "Beams & braces", cats: ["Beam", "Brace"], info: "graph.ifc-lane-beams" },
  { id: "conns", label: "Connections", cats: ["Connection"], info: "graph.ifc-lane-connections" },
  { id: "cols", label: "Columns & walls", cats: ["Column", "Wall"], info: "graph.ifc-lane-columns" },
  { id: "fdn", label: "Foundations", cats: ["Footing", "Pile"], info: "graph.ifc-lane-foundations" },
  { id: "other", label: "Other", cats: ["Other"], info: "graph.ifc-lane-other" },
];
const CALC_LANE: GraphLane = { id: "calcs", label: "Calc graph", info: "graph.ifc-lane-calcs" };
const MAX_PER_LANE = 18;
const nat = (a: string, b: string) => a.localeCompare(b, undefined, { numeric: true });
const laneOf = (cat: string) => (LANE_DEFS.find((l) => l.cats.includes(cat)) ?? LANE_DEFS[LANE_DEFS.length - 1]).id;

/** what to show: an impact's footprint, else the selected element's path (12 hops down, 2 up) */
function neighbourhood(ix: IfcIndex, sel: Sel, impact: IfcImpact | null): Set<string> {
  const out = new Set<string>();
  if (impact) {
    impact.removed.forEach((g) => out.add(g));
    Object.keys(impact.hit).forEach((g) => out.add(g));
    out.add(impact.global_id);
    return out;
  }
  if (!sel || sel.kind !== "el") return out;
  const down = new Map<string, string[]>(), up = new Map<string, string[]>();
  for (const e of ix.st.edges) {
    (down.get(e.src) ?? down.set(e.src, []).get(e.src)!).push(e.dst);
    (up.get(e.dst) ?? up.set(e.dst, []).get(e.dst)!).push(e.src);
  }
  out.add(sel.id);
  const walk = (x: string, m: Map<string, string[]>, depth: number) => {
    if (depth <= 0) return;
    for (const n of m.get(x) ?? [])
      if (!out.has(n)) {
        out.add(n);
        walk(n, m, depth - 1);
      }
  };
  walk(sel.id, down, 12);
  walk(sel.id, up, 2);
  return out;
}

type EdgeInfo = { text: string };

export function LoadPathGraph({ ix, sel, impact, onSelect, height = "max(420px, calc(100vh - 340px))" }: { height?: string; ix: IfcIndex; sel: Sel; impact: IfcImpact | null; onSelect: (s: Sel, focus?: boolean) => void }) {
  const [edgeSel, setEdgeSel] = useState<GraphEdge<EdgeInfo> | null>(null);
  const graph = useMemo(() => {
    const ids = neighbourhood(ix, sel, impact);
    const stale = new Set(Object.keys(impact?.stale ?? {}));
    const removed = new Set(impact?.removed ?? []);
    const hit = (g: string) => impact?.hit[g] !== undefined;
    const nodes: GraphNode[] = [];
    const more: string[] = [];
    const byLane = new Map<string, string[]>();
    for (const g of ids) {
      const e = ix.els.get(g);
      if (e) (byLane.get(laneOf(e.cat)) ?? byLane.set(laneOf(e.cat), []).get(laneOf(e.cat))!).push(g);
    }
    const shown = new Set<string>();
    for (const lane of LANE_DEFS) {
      const list = (byLane.get(lane.id) ?? []).sort((a, b) => {
        const ea = ix.els.get(a)!, eb = ix.els.get(b)!;
        return (sel?.id === a ? -1 : 0) - (sel?.id === b ? -1 : 0) || nat(ea.storey, eb.storey) || nat(ea.mark || a, eb.mark || b);
      });
      if (list.length > MAX_PER_LANE) more.push(`${lane.label}: +${list.length - MAX_PER_LANE} more not shown`);
      for (const g of list.slice(0, MAX_PER_LANE)) {
        const e = ix.els.get(g)!;
        shown.add(g);
        nodes.push({
          id: g,
          lane: lane.id,
          label: elLabel(e),
          sub: e.profile || e.storey,
          color: CAT_COLORS[e.cat] ?? CAT_COLORS.Other,
          tone: removed.has(g) ? "bad" : hit(g) ? "warn" : undefined,
          dashed: removed.has(g),
          title: `${e.mark || elLabel(e)} - ${e.cat} - ${e.storey}${impact?.why[g] ? "\n" + impact.why[g] : ""}`,
        });
      }
    }
    const calcs = ix.st.calcs.filter((c) => !c.front);
    for (const c of calcs)
      nodes.push({
        id: `calc:${c.key}`,
        lane: "calcs",
        label: c.title,
        sub: c.scanned ? "no text - needs OCR" : c.software || c.cat || "",
        color: c.color,
        tone: stale.has(c.key) ? "warn" : "calc",
        title: `${c.title}${stale.has(c.key) ? "\nSTALE: " + impact!.stale[c.key] : ""}`,
      });
    const edges: GraphEdge<EdgeInfo>[] = [];
    ix.st.edges.forEach((e, i) => {
      if (!shown.has(e.src) || !shown.has(e.dst)) return;
      const gone = removed.has(e.src) || removed.has(e.dst);
      const imp = !gone && hit(e.src) && hit(e.dst);
      edges.push({
        id: `lp${i}`,
        source: e.src,
        target: e.dst,
        style: gone ? "inferred" : "exact",
        color: gone ? "var(--bad)" : imp ? "var(--warn)" : undefined,
        width: imp ? 2.4 : undefined,
        title: e.rule,
        data: { text: `Load path: ${labelOf(ix, e.src)} delivers load to ${labelOf(ix, e.dst)} - ${e.rule}${e.gap_m != null ? ` (gap ${e.gap_m} m)` : ""}` },
      });
    });
    ix.st.calc_edges.forEach((e, i) => {
      const both = stale.has(e.src) && stale.has(e.dst);
      edges.push({
        id: `ce${i}`,
        source: `calc:${e.src}`,
        target: `calc:${e.dst}`,
        style: "plain",
        color: both ? "var(--warn)" : "var(--calc)",
        width: both ? 2.2 : undefined,
        title: `${e.src} feeds ${e.dst}: ${e.rules.join("; ")}`,
        data: {
          text: `Calc dependency: ${ix.calcs.get(e.src)?.title ?? e.src} feeds ${ix.calcs.get(e.dst)?.title ?? e.dst} - ${e.rules.join("; ")}${e.evidence[0] ? ` (page ${e.evidence[0].page}: "${e.evidence[0].text}")` : ""}`,
        },
      });
    });
    for (const g of shown) {
      const top = linksFor(ix, g)[0];
      if (!top || !ix.calcs.has(top.calc_key) || ix.calcs.get(top.calc_key)!.front) continue;
      const low = top.conf < 0.8 && top.status === "auto";
      edges.push({
        id: `map:${g}`,
        source: g,
        target: `calc:${top.calc_key}`,
        style: "inferred",
        color: low ? "var(--warn)" : "var(--calc)",
        title: `${Math.round(top.conf * 100)}% - ${top.rule}`,
        data: { text: `Mapping: ${labelOf(ix, g)} is covered by ${ix.calcs.get(top.calc_key)!.title} - ${top.rule} (${top.status === "auto" ? Math.round(top.conf * 100) + "%" : top.status})` },
      });
    }
    const lanes: GraphLane[] = [...LANE_DEFS.filter((l) => byLane.get(l.id)?.length).map((l) => ({ id: l.id, label: l.label, info: l.info })), CALC_LANE];
    return { nodes, edges, lanes, more, empty: !ids.size };
  }, [ix, sel, impact]);

  const selectedId = sel ? (sel.kind === "calc" ? `calc:${sel.id}` : sel.id) : null;
  return (
    <div className="ifc-graph">
      <div className="ifc-graph-note muted">
        {graph.empty
          ? "Select an element (3D view or lists) to see its load path, or run an impact check from the inspector."
          : impact
            ? "Impact footprint: removed members in red, members on the impacted load path and stale calcs in orange."
            : "Selected element: full downstream path, two levels upstream."}
        {graph.more.length > 0 && <span> {graph.more.join(" - ")}</span>}
      </div>
      <GraphView
        nodes={graph.nodes}
        edges={graph.edges}
        lanes={graph.lanes}
        info="graph.ifc-load-path"
        height={height}
        fitMinZoom={0.5}
        selectedId={selectedId}
        selectedEdgeId={edgeSel?.id}
        onNodeClick={(n) => (n.id.startsWith("calc:") ? onSelect({ kind: "calc", id: n.id.slice(5) }) : onSelect({ kind: "el", id: n.id }))}
        onEdgeClick={(e) => setEdgeSel(e)}
        footer={
          <>
            {edgeSel?.data && (
              <div className="ifc-edge-why" role="status">
                {edgeSel.data.text}{" "}
                <button type="button" className="btn sm" onClick={() => setEdgeSel(null)}>
                  Clear
                </button>
              </div>
            )}
            <Legend
              info="legend.ifc-graph"
              items={[
                { label: "load path (model)", color: "var(--edge)", shape: "line", info: "legend.ifc-graph-load-path" },
                { label: "calc dependency", color: "var(--calc)", shape: "line", info: "legend.ifc-graph-calc-dep" },
                { label: "element to calc mapping", color: "var(--calc)", shape: "dashed", info: "legend.ifc-graph-mapping" },
                { label: "mapping to review", color: "var(--warn)", shape: "dashed", info: "legend.ifc-graph-mapping-low" },
                { label: "impacted / stale", color: "var(--warn)", shape: "box", info: "legend.ifc-impacted" },
                { label: "removed", color: "var(--bad)", shape: "box", info: "legend.ifc-removed" },
              ]}
            />
          </>
        }
      />
    </div>
  );
}

const labelOf = (ix: IfcIndex, g: string) => {
  const e = ix.els.get(g);
  return e ? elLabel(e) : g;
};
