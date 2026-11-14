// /dev/components - every shared component with real API data where the server has it.
// Anything that is sample data is labelled SAMPLE on screen.
import { useCallback, useMemo, useState } from "react";
import { urls } from "../../api/client";
import { useV2Design, useV2Element, useV2Record, useV2Summary } from "../../api/hooks";
import type { V2Occurrence, V2Record } from "../../api/types";
import { EvidenceCompare } from "../../components/EvidenceCompare";
import { GraphView, type GraphEdge, type GraphLane, type GraphNode } from "../../components/GraphView";
import { Legend } from "../../components/Legend";
import { Panel } from "../../components/Panel";
import { PdfPage, PdfSplit, type PdfSource } from "../../components/PdfPage";
import { StatPill, StatRow } from "../../components/StatPill";
import { Tabs } from "../../components/Tabs";
import { Viewer3D, type MemberStyle } from "../../components/Viewer3D";
import { InfoTip } from "../../help/InfoTip";
import "./dev.css";

const FOCUS_RECORD = "B-COL:2B";
const FOCUS_ELEMENT = "COL-2B";

const TYPE_COL: Record<string, string> = {
  column: "#e15759",
  girder: "#f28e2b",
  beam: "#4e79a7",
  brace: "#59a14f",
  footing: "#9c755f",
  pier: "#9c755f",
  grade_beam: "#9c755f",
};

const LANES: readonly GraphLane[] = [
  { id: "in", label: "Feeds in", info: "graph.lane-inputs" },
  { id: "rec", label: "Selected record", info: "graph.lane-record" },
  { id: "out", label: "Feeds out", info: "graph.lane-downstream" },
];

const occSource = (o: V2Occurrence | undefined, label: string): PdfSource | null =>
  o && o.page && o.bbox
    ? { url: urls.v2DocFile(o.doc), page: o.page, rects: [o.bbox], label, sub: `${o.doc} p.${o.page}${o.sheet ? ` - sheet ${o.sheet}` : ""} - ${o.how}: "${o.text ?? ""}"` }
    : null;

const recSource = (r: V2Record | undefined): PdfSource | null =>
  r && r.page && r.bbox
    ? { url: urls.v2DocFile("calcs"), page: r.page, rects: [r.bbox], label: `${r.id} - ${r.calc_title ?? r.kind}`, sub: `Calc package p.${r.page}${r.sheet ? ` - sheet ${r.sheet}` : ""}${r.uc != null ? ` - UC ${r.uc}` : ""}` }
    : null;

export default function ComponentsPage() {
  const summary = useV2Summary();
  const design = useV2Design();
  const rec = useV2Record(FOCUS_RECORD);
  const el = useV2Element(FOCUS_ELEMENT);

  const [tab, setTab] = useState<"elements" | "records" | "relations">("elements");
  const [selNode, setSelNode] = useState<string | null>(FOCUS_RECORD);
  const [selEdge, setSelEdge] = useState<GraphEdge | null>(null);
  const [split, setSplit] = useState(false);
  const [picked, setPicked] = useState<string | null>(null);

  const recById = useMemo(() => new Map((design.data?.records ?? []).map((r) => [r.id, r])), [design.data]);
  const typeByGid = useMemo(() => {
    const m = new Map<string, { id: string; type: string; size?: string }>();
    for (const e of design.data?.elements ?? []) if (e.global_id) m.set(e.global_id, { id: e.id, type: e.type, size: e.size });
    return m;
  }, [design.data]);

  // graph: real fed_by / feeds of the focus record, plus two SAMPLE nodes showing the inferred and absent styles
  const graph = useMemo(() => {
    const r = rec.data;
    if (!r) return { nodes: [] as GraphNode<V2Record | undefined>[], edges: [] as GraphEdge[] };
    const node = (id: string, lane: string): GraphNode<V2Record | undefined> => {
      const x = recById.get(id);
      return { id, lane, label: id, sub: x ? `${x.kind.replace(/_/g, " ")}${x.uc != null ? ` - UC ${x.uc}` : ""}` : "", color: x?.uc != null && x.uc > 0.9 ? "var(--warn)" : "var(--accent)", data: x };
    };
    const nodes = [...r.fed_by.map((i) => node(i, "in")), node(r.id, "rec"), ...r.feeds.map((i) => node(i, "out"))];
    nodes.push({ id: "sample:inferred", lane: "in", label: "SAMPLE inferred input", sub: "not real data - edge style demo", color: "var(--muted)" });
    nodes.push({ id: "sample:gap", lane: "out", label: "SAMPLE no support found", sub: "not real data - gap demo", kind: "gap" });
    const edges: GraphEdge[] = [
      ...r.fed_by.map((i) => ({ id: `${i}>${r.id}`, source: i, target: r.id, style: "exact" as const, title: `${i} feeds ${r.id} (recorded input)` })),
      ...r.feeds.map((o) => ({ id: `${r.id}>${o}`, source: r.id, target: o, style: "exact" as const, title: `${r.id} feeds ${o} (recorded input)` })),
      { id: "sample:inferred>rec", source: "sample:inferred", target: r.id, style: "inferred", title: "SAMPLE inferred edge" },
      { id: "rec>sample:gap", source: r.id, target: "sample:gap", style: "absent", title: "SAMPLE absent edge" },
    ];
    return { nodes, edges };
  }, [rec.data, recById]);

  const selRecord = selNode ? recById.get(selNode) : undefined;
  const drawingOcc = el.data?.occurrences.find((o) => o.doc === "drawings" && o.page && o.bbox);
  const calcOcc = el.data?.occurrences.find((o) => o.doc === "calcs" && o.page && o.bbox);

  const styleOf = useCallback(
    (gid: string): MemberStyle | undefined => {
      const t = typeByGid.get(gid);
      if (!t) return undefined;
      if (t.type === "connection") return { color: "#9aa3ad", opacity: 0.6 };
      return { color: TYPE_COL[t.type] ?? "#c3cad3" };
    },
    [typeByGid],
  );
  const pickedEl = picked ? typeByGid.get(picked) : undefined;

  const counts = summary.data ? { elements: summary.data.elements, records: summary.data.records, relations: summary.data.relations }[tab] : null;
  const total = (o?: Record<string, number>) => (o ? Object.values(o).reduce((a, b) => a + b, 0) : "-");

  return (
    <div className="page dev">
      <h1>
        Component gallery <InfoTip id="page.dev-components" />
      </h1>
      <p className="page-lede">
        Each shared component with live data from the synthetic v2 API (<code>/api/v2</code>). Items marked SAMPLE are not real data.
        {summary.error && <span className="dev-err"> API error: {String(summary.error.message)}</span>}
      </p>

      <section className="dev-sec">
        <h2>StatPill</h2>
        <StatRow>
          <StatPill label="elements" value={total(summary.data?.elements)} info="stat.v2-elements" />
          <StatPill label="calc records" value={total(summary.data?.records)} info="stat.v2-records" tone="calc" />
          <StatPill label="relations" value={total(summary.data?.relations)} info="stat.v2-relations" tone="accent" />
          <StatPill label="occurrences" value={summary.data?.occurrences ?? "-"} info="stat.v2-occurrences" tone="good" />
        </StatRow>
      </section>

      <section className="dev-sec dev-grid2">
        <div>
          <h2>Panel + Tabs</h2>
          <Panel title="Synthetic v2 model" info="panel.v2-model" actions={<span>{summary.isLoading ? "loading..." : `${Object.keys(counts ?? {}).length} kinds`}</span>} className="dev-panel">
            <Tabs
              label="Count by"
              info="panel.v2-model"
              value={tab}
              onChange={setTab}
              items={[
                { id: "elements", label: "Elements", info: "tab.elements", badge: total(summary.data?.elements) },
                { id: "records", label: "Calc records", info: "tab.records", badge: total(summary.data?.records) },
                { id: "relations", label: "Relations", info: "tab.relations", badge: total(summary.data?.relations) },
              ]}
            />
            <table className="dev-table" role="tabpanel" aria-labelledby={`tab-${tab}`}>
              <tbody>
                {Object.entries(counts ?? {})
                  .sort((a, b) => b[1] - a[1])
                  .map(([k, v]) => (
                    <tr key={k}>
                      <td>{k.replace(/_/g, " ")}</td>
                      <td className="mono num">{v}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </Panel>
        </div>
        <div>
          <h2>Legend</h2>
          <div className="dev-card">
            <Legend
              title="Edges"
              info="legend.edge-styles"
              items={[
                { label: "exact", color: "var(--edge)", shape: "line", info: "legend.edge-exact" },
                { label: "inferred", color: "var(--edge)", shape: "dashed", info: "legend.edge-inferred" },
                { label: "absent", color: "var(--bad)", shape: "dotted", info: "legend.edge-absent" },
              ]}
            />
            <div style={{ height: 10 }} />
            <Legend
              title="Links"
              info="legend.link-tiers"
              items={[
                { label: ">= 75%", color: "var(--good)", info: "legend.link-high" },
                { label: "55-74%", color: "var(--warn)", info: "legend.link-mid" },
                { label: "< 55%", color: "var(--bad)", info: "legend.link-low" },
              ]}
            />
          </div>
        </div>
      </section>

      <section className="dev-sec">
        <h2>GraphView</h2>
        <p className="dev-note">
          Calc dependencies of <b>{FOCUS_RECORD}</b> (real, from <code>/api/v2/records</code>). Click a node to open its calc page below; click an edge to describe it.
        </p>
        {rec.error && <p className="dev-err">{String(rec.error.message)}</p>}
        <GraphView
          nodes={graph.nodes}
          edges={graph.edges}
          lanes={LANES}
          info="graph.calc-dependency"
          selectedId={selNode}
          selectedEdgeId={selEdge?.id}
          onNodeClick={(n) => {
            setSelNode(n.id);
            setSelEdge(null);
          }}
          onEdgeClick={(e) => setSelEdge(e)}
          height={460}
          footer={
            <Legend
              info="legend.edge-styles"
              items={[
                { label: "exact", color: "var(--edge)", shape: "line", info: "legend.edge-exact" },
                { label: "inferred", color: "var(--edge)", shape: "dashed", info: "legend.edge-inferred" },
                { label: "absent", color: "var(--bad)", shape: "dotted", info: "legend.edge-absent" },
              ]}
            />
          }
        />
        <p className="dev-status" data-testid="graph-status">
          {selEdge ? <>Edge: <b>{selEdge.title}</b> ({selEdge.style})</> : selNode ? <>Selected node: <b>{selNode}</b>{selRecord ? ` - ${selRecord.kind}, calc ${selRecord.calc}, page ${selRecord.page}` : ""}</> : "Nothing selected"}
        </p>
      </section>

      <section className="dev-sec">
        <h2>PdfPage + split view</h2>
        <p className="dev-note">
          The selected record's calc page (pdf.js, highlight = the record's row). <button type="button" className="btn sm" onClick={() => setSplit((v) => !v)} data-testid="split-toggle">{split ? "Close drawing" : "Open the drawing below (split)"}</button>
        </p>
        <div className="dev-pdf">
          <PdfSplit
            primary={recSource(selRecord)}
            secondary={split ? occSource(drawingOcc, `${FOCUS_ELEMENT} on the drawings`) : null}
            onCloseSecondary={() => setSplit(false)}
            splitTitle={`${FOCUS_ELEMENT} - drawing occurrence`}
            info="pdf.split"
            pageInfo="pdf.page"
          />
        </div>
      </section>

      <section className="dev-sec">
        <h2>EvidenceCompare</h2>
        <div className="dev-compare">
          <EvidenceCompare
            left={occSource(calcOcc, `${FOCUS_ELEMENT} in the calc package`)}
            right={occSource(drawingOcc, `${FOCUS_ELEMENT} on the drawings`)}
            leftTitle="Calc package"
            rightTitle="Drawings"
            note={`Every occurrence of ${FOCUS_ELEMENT} comes from /api/v2/elements/${FOCUS_ELEMENT}.`}
            info="evidence.compare"
            pageInfo="pdf.page"
          />
        </div>
      </section>

      <section className="dev-sec">
        <h2>Viewer3D</h2>
        <p className="dev-note">
          Synthetic v2 IFC (<code>/api/v2/model.ifc</code>), coloured by element type. Click a member.{" "}
          <span className="dev-status" data-testid="pick-status">
            {pickedEl ? <>Picked: <b>{pickedEl.id}</b> ({pickedEl.type}{pickedEl.size ? ` ${pickedEl.size}` : ""})</> : picked ? <>Picked GlobalId {picked}</> : "Nothing picked"}
          </span>
        </p>
        <div className="dev-3d">
          <Viewer3D url={urls.v2ModelIfc()} rev="v2" info="viewer3d.model" styleOf={design.data ? styleOf : undefined} selected={picked} onPick={(gid) => setPicked(gid)}>
            <Legend
              variant="overlay"
              title="Members"
              info="legend.member-types"
              items={[
                { label: "column", color: TYPE_COL.column, info: "legend.type-column" },
                { label: "girder", color: TYPE_COL.girder, info: "legend.type-girder" },
                { label: "beam", color: TYPE_COL.beam, info: "legend.type-beam" },
                { label: "brace", color: TYPE_COL.brace, info: "legend.type-brace" },
                { label: "foundation", color: TYPE_COL.footing, info: "legend.type-foundation" },
              ]}
            />
          </Viewer3D>
        </div>
      </section>

      <section className="dev-sec">
        <h2>PdfPage alone</h2>
        <div className="dev-pdf small">
          <PdfPage source={null} info="pdf.page" emptyText="Empty state: nothing selected yet." />
        </div>
      </section>
    </div>
  );
}
