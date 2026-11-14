import { memo, useMemo, type ReactNode } from "react";
import {
  Background,
  Controls,
  Handle,
  MarkerType,
  Position,
  ReactFlow,
  type Edge,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import dagre from "@dagrejs/dagre";
import { InfoTip } from "../help/InfoTip";
import type { HelpId } from "../help/registry";
import { useTheme } from "../theme/ThemeProvider";

/** exact = shared label (solid), inferred = by coordinates (dashed), absent = no support found (red dotted) */
export type EdgeStyle = "exact" | "inferred" | "absent" | "plain";

export interface GraphNode<D = unknown> {
  id: string;
  label: string;
  sub?: string;
  /** lane (column) id, when the graph has lanes */
  lane?: string;
  /** accent colour of the node's left bar */
  color?: string;
  /** "gap" draws a dashed red placeholder (e.g. "no support found") */
  kind?: "normal" | "gap";
  title?: string;
  data?: D;
}

export interface GraphEdge<D = unknown> {
  id: string;
  source: string;
  target: string;
  style?: EdgeStyle;
  label?: string;
  title?: string;
  data?: D;
}

export interface GraphLane {
  id: string;
  label: string;
  /** help id for the lane header (required) */
  info: HelpId;
}

export interface GraphViewProps<N = unknown, E = unknown> {
  nodes: readonly GraphNode<N>[];
  edges: readonly GraphEdge<E>[];
  /** columns, left to right; nodes are placed in their lane and ordered by the dagre layout */
  lanes?: readonly GraphLane[];
  /** layout direction when there are no lanes */
  direction?: "LR" | "TB";
  /** help id for the graph as a whole */
  info: HelpId;
  selectedId?: string | null;
  selectedEdgeId?: string | null;
  onNodeClick?: (n: GraphNode<N>) => void;
  onEdgeClick?: (e: GraphEdge<E>) => void;
  /** CSS height of the graph area (default 420px) */
  height?: number | string;
  /** drawn under the graph, e.g. a Legend */
  footer?: ReactNode;
}

const NW = 176, NH = 44, LANE_GAP = 90, ROW_GAP = 12, HEAD = 34, PAD = 14;

interface CgData extends Record<string, unknown> {
  g: GraphNode;
  selected: boolean;
  dir: "LR" | "TB";
}
interface LaneData extends Record<string, unknown> {
  lane: GraphLane;
  w: number;
  h: number;
}

const CgNode = memo(function CgNode({ data }: NodeProps<Node<CgData>>) {
  const { g, selected, dir } = data;
  return (
    <div
      className={`cg-gnode${g.kind === "gap" ? " gap" : ""}${selected ? " sel" : ""}`}
      style={{ borderLeftColor: g.kind === "gap" ? undefined : g.color ?? "var(--accent)" }}
      title={g.title ?? [g.label, g.sub].filter(Boolean).join("\n")}
    >
      <Handle type="target" position={dir === "LR" ? Position.Left : Position.Top} isConnectable={false} />
      <div className="cg-gnode-l">{g.label}</div>
      {g.sub && <div className="cg-gnode-s">{g.sub}</div>}
      <Handle type="source" position={dir === "LR" ? Position.Right : Position.Bottom} isConnectable={false} />
    </div>
  );
});

const LaneNode = memo(function LaneNode({ data }: NodeProps<Node<LaneData>>) {
  return (
    <div className="cg-lane" style={{ width: data.w, height: data.h }}>
      <div className="cg-lane-head nodrag nopan">
        {data.lane.label}
        <InfoTip id={data.lane.info} />
      </div>
    </div>
  );
});

const nodeTypes = { cg: CgNode, lane: LaneNode };

function edgeVisual(style: EdgeStyle | undefined, selected: boolean) {
  const c = style === "absent" ? "var(--bad)" : selected ? "var(--accent)" : "var(--edge)";
  return {
    style: {
      stroke: c,
      strokeWidth: selected ? 2.6 : style === "exact" ? 1.8 : 1.5,
      strokeDasharray: style === "inferred" ? "6 4" : style === "absent" ? "1.5 4" : undefined,
      strokeLinecap: "round" as const,
    },
    markerEnd: { type: MarkerType.ArrowClosed, color: c, width: 16, height: 16 },
  };
}

function layout(nodes: readonly GraphNode[], edges: readonly GraphEdge[], lanes: readonly GraphLane[] | undefined, direction: "LR" | "TB") {
  const g = new dagre.graphlib.Graph();
  g.setGraph({ rankdir: lanes ? "LR" : direction, nodesep: ROW_GAP + 6, ranksep: 70, marginx: PAD, marginy: PAD });
  g.setDefaultEdgeLabel(() => ({}));
  const ids = new Set(nodes.map((n) => n.id));
  nodes.forEach((n) => g.setNode(n.id, { width: NW, height: NH }));
  edges.forEach((e) => ids.has(e.source) && ids.has(e.target) && g.setEdge(e.source, e.target));
  dagre.layout(g);
  const pos = new Map<string, { x: number; y: number }>();
  nodes.forEach((n) => {
    const p = g.node(n.id);
    pos.set(n.id, { x: p.x - NW / 2, y: p.y - NH / 2 });
  });
  const laneBoxes: { lane: GraphLane; x: number; w: number; h: number }[] = [];
  if (lanes?.length) {
    // columns: x from the lane, order inside a lane from dagre's y, overlaps pushed down
    let maxH = 0;
    lanes.forEach((lane, li) => {
      const inLane = nodes.filter((n) => n.lane === lane.id).sort((a, b) => pos.get(a.id)!.y - pos.get(b.id)!.y);
      const x = PAD + li * (NW + 2 * PAD + LANE_GAP);
      let y = HEAD + PAD;
      for (const n of inLane) {
        y = Math.max(y, pos.get(n.id)!.y + HEAD);
        pos.set(n.id, { x: x + PAD, y });
        y += NH + ROW_GAP;
      }
      maxH = Math.max(maxH, y + PAD);
      laneBoxes.push({ lane, x, w: NW + 2 * PAD, h: 0 });
    });
    laneBoxes.forEach((b) => (b.h = maxH));
  }
  return { pos, laneBoxes };
}

/** Graph on React Flow, laid out by dagre: optional lanes, edge styles exact / inferred / absent, clickable nodes and edges. */
export function GraphView<N, E>({
  nodes,
  edges,
  lanes,
  direction = "LR",
  info,
  selectedId,
  selectedEdgeId,
  onNodeClick,
  onEdgeClick,
  height = 420,
  footer,
}: GraphViewProps<N, E>) {
  const { resolved } = useTheme();
  const dir = lanes?.length ? "LR" : direction;
  const geo = useMemo(() => layout(nodes, edges, lanes, direction), [nodes, edges, lanes, direction]);
  const byId = useMemo(() => new Map(nodes.map((n) => [n.id, n])), [nodes]);
  const edgeById = useMemo(() => new Map(edges.map((e) => [e.id, e])), [edges]);

  const rfNodes = useMemo<Node[]>(() => {
    const laneNodes: Node<LaneData>[] = geo.laneBoxes.map((b) => ({
      id: `lane:${b.lane.id}`,
      type: "lane",
      position: { x: b.x, y: 0 },
      data: { lane: b.lane, w: b.w, h: b.h },
      draggable: false,
      selectable: false,
      focusable: false,
      zIndex: -1,
    }));
    const main: Node<CgData>[] = nodes.map((n) => ({
      id: n.id,
      type: "cg",
      position: geo.pos.get(n.id)!,
      data: { g: n as GraphNode, selected: n.id === selectedId, dir },
      draggable: false,
      width: NW,
      height: NH,
    }));
    return [...laneNodes, ...main];
  }, [geo, nodes, selectedId, dir]);

  const rfEdges = useMemo<Edge[]>(
    () =>
      edges
        .filter((e) => byId.has(e.source) && byId.has(e.target))
        .map((e) => ({
          id: e.id,
          source: e.source,
          target: e.target,
          label: e.label,
          interactionWidth: 18,
          ...edgeVisual(e.style, e.id === selectedEdgeId),
          ariaLabel: e.title ?? `${e.source} to ${e.target}${e.style ? ` (${e.style})` : ""}`,
        })),
    [edges, byId, selectedEdgeId],
  );

  // remount (and so re-fit) when the node set changes, not on selection
  const fitKey = useMemo(() => nodes.map((n) => n.id).join("|"), [nodes]);

  return (
    <div className="cg-graph">
      <div className="cg-graph-info">
        <InfoTip id={info} />
      </div>
      <div className="cg-graph-canvas" style={{ height }}>
        <ReactFlow
          key={fitKey}
          nodes={rfNodes}
          edges={rfEdges}
          nodeTypes={nodeTypes}
          colorMode={resolved}
          fitView
          fitViewOptions={{ padding: 0.08 }}
          minZoom={0.1}
          maxZoom={2.5}
          nodesConnectable={false}
          nodesDraggable={false}
          elementsSelectable
          proOptions={{ hideAttribution: false }}
          onNodeClick={(_, n) => {
            const g = byId.get(n.id);
            if (g) onNodeClick?.(g);
          }}
          onEdgeClick={(_, e) => {
            const g = edgeById.get(e.id);
            if (g) onEdgeClick?.(g);
          }}
        >
          <Background gap={18} size={1} />
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>
      {footer}
    </div>
  );
}
