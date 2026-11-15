import { useCallback, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { InfoTip } from "../../help/InfoTip";
import { Panel } from "../../components/Panel";
import { StatPill, StatRow } from "../../components/StatPill";
import { PdfPage, type PdfSource } from "../../components/PdfPage";
import { Viewer3D, type Viewer3DHandle } from "../../components/Viewer3D";
import { GraphView, type GraphEdge, type GraphNode } from "../../components/GraphView";
import { Legend } from "../../components/Legend";
import { useV2Element } from "../../api/hooks";
import { urls } from "../../api/client";
import type { V2Occurrence } from "../../api/types";
import { useConstructionStatus } from "./api";
import { MockLink, PlatformRecordDialog, PlatformSourceBadge } from "./PlatformRecord";
import { InboxHistory } from "./InboxHistory";
import { howLabel, occSource, recordSource, useDesignIndex, type DesignIndex } from "./util";

type Group = "ifc" | "drawings" | "specs" | "calcs" | "etabs" | "platforms";
const GROUPS: { id: Group; label: string; info: "stat.reg-ifc" | "stat.reg-drawings" | "stat.reg-specs" | "stat.reg-calcs" | "stat.reg-etabs" | "stat.reg-platforms" }[] = [
  { id: "ifc", label: "IFC model", info: "stat.reg-ifc" },
  { id: "drawings", label: "Drawings", info: "stat.reg-drawings" },
  { id: "specs", label: "Specs", info: "stat.reg-specs" },
  { id: "calcs", label: "Calcs", info: "stat.reg-calcs" },
  { id: "etabs", label: "ETABS", info: "stat.reg-etabs" },
  { id: "platforms", label: "Platforms", info: "stat.reg-platforms" },
];

type View = { kind: "pdf"; src: PdfSource; key: string } | { kind: "ifc"; gid: string; key: string } | { kind: "etabs"; occ: V2Occurrence; key: string } | null;

const REL_COLOR: Record<string, string> = {
  "frames-into": "#2f6fed",
  "bears-on": "#1f9d5b",
  supports: "#1f9d5b",
  "connected-by": "#e0a020",
  "instance-of": "#7c4dde",
  "specified-by": "#b5650f",
  "designed-by": "#8a5cf0",
  "detailed-by": "#e2622b",
  "member-of": "#5f6773",
};
const nodeColor = (id: string) =>
  id.startsWith("SPEC:") ? "#b5650f" : id.startsWith("TYPE:") || id.startsWith("MAT:") ? "#7c4dde" : id.includes(":") && !id.startsWith("DET") ? "#8a5cf0" : "#2f6fed";

const MAX_LANE = 14;

function specSource(idx: DesignIndex, id: string): PdfSource | null {
  const a = idx.specArticles.get(id);
  return a ? { url: urls.v2DocFile("specs"), page: a.page, rects: [a.bbox], label: id.replace("SPEC:", ""), sub: `${a.section_title ?? ""} - ${a.title}: ${a.text.slice(0, 120)}` } : null;
}

function detailSource(idx: DesignIndex, id: string): PdfSource | null {
  const det = ((idx.design as Record<string, unknown>).details as { id: string; page: number; bbox: number[]; title: string; sheet: string }[] | undefined)?.find(
    (d) => d.id === id,
  );
  return det ? { url: urls.v2DocFile("drawings"), page: det.page, rects: [det.bbox], label: `${det.id} - ${det.title}`, sub: `Sheet ${det.sheet}` } : null;
}

/** Registry element page: every place the element appears (each opens its source) and its relations as a graph. */
export default function ElementPage() {
  const { eid = "" } = useParams();
  const nav = useNavigate();
  const q = useV2Element(eid);
  const { idx } = useDesignIndex();
  const cs = useConstructionStatus(q.data?.element?.type ? eid : null);
  const [view, setView] = useState<View>(null);
  const [mock, setMock] = useState<string | null>(null);
  const v3 = useRef<Viewer3DHandle>(null);
  const el = q.data?.element;
  const recSelf = q.data?.record;

  const grouped = useMemo(() => {
    const g: Record<Group, V2Occurrence[]> = { ifc: [], drawings: [], specs: [], calcs: [], etabs: [], platforms: [] };
    for (const o of q.data?.occurrences ?? []) (g[o.doc as Group] ?? (g[o.doc as Group] = [])).push(o);
    return g;
  }, [q.data]);
  const platformItems = grouped.platforms;

  // relations graph: incoming on the left, the element in the middle, outgoing on the right
  const graph = useMemo(() => {
    if (!q.data) return { nodes: [] as GraphNode[], edges: [] as GraphEdge[] };
    const center: GraphNode = { id: eid, label: eid, sub: el ? `${el.type}${el.size ? ` ${el.size}` : ""}` : recSelf?.kind, lane: "self", color: "#ffb000" };
    const nodes: GraphNode[] = [center];
    const edges: GraphEdge[] = [];
    const add = (rels: { src: string; dst: string; kind: string }[], lane: "in" | "out") => {
      const seen = new Set<string>();
      let extra = 0;
      for (const r of rels) {
        const other = lane === "in" ? r.src : r.dst;
        if (seen.has(other)) continue;
        if (seen.size >= MAX_LANE) {
          extra++;
          continue;
        }
        seen.add(other);
        const oe = idx?.el.get(other);
        nodes.push({ id: `${lane}:${other}`, label: other, sub: `${r.kind}${oe?.size ? ` - ${oe.size}` : ""}`, lane, color: nodeColor(other), data: other });
        edges.push({
          id: `${lane}:${other}:${r.kind}`,
          source: lane === "in" ? `${lane}:${other}` : eid,
          target: lane === "in" ? eid : `${lane}:${other}`,
          label: r.kind,
          style: "exact",
        });
      }
      if (extra) nodes.push({ id: `${lane}:more`, label: `+${extra} more`, sub: "listed under Occurrences / relations", lane, kind: "gap" });
    };
    add(q.data.relations_in, "in");
    add([...q.data.relations_out, ...q.data.designed_by.map((r) => ({ src: eid, dst: r.id, kind: "designed-by" }))], "out");
    return { nodes, edges };
  }, [q.data, eid, el, recSelf, idx]);

  const openNode = useCallback(
    (n: GraphNode) => {
      const id = (n.data as string | undefined) ?? (n.id === eid ? null : null);
      if (!id || !idx) return;
      if (id.startsWith("SPEC:")) {
        const s = specSource(idx, id);
        if (s) setView({ kind: "pdf", src: s, key: id });
        return;
      }
      if (id.startsWith("DET:")) {
        const s = detailSource(idx, id);
        if (s) setView({ kind: "pdf", src: s, key: id });
        return;
      }
      nav(`/v2/element/${encodeURIComponent(id)}`);
      setView(null);
    },
    [idx, nav, eid],
  );

  if (q.isLoading) return <div className="page muted">Loading {eid}...</div>;
  if (q.error) return <div className="page v2-error">Could not load {eid}: {(q.error as Error).message}</div>;
  if (!q.data) return null;

  const openOcc = (o: V2Occurrence, i: number) => {
    const key = `${o.doc}-${i}`;
    if (o.doc === "ifc" && o.global_id) setView({ kind: "ifc", gid: o.global_id, key });
    else if (o.doc === "etabs") setView({ kind: "etabs", occ: o, key });
    else {
      const s = occSource(o);
      if (s) setView({ kind: "pdf", src: s, key });
    }
  };
  const KIND_LABEL: Record<string, string> = { spec_article: "spec article", detail: "drawing detail", record: "calc record", type: "type" };
  const elType = el?.type ?? KIND_LABEL[q.data.kind] ?? q.data.kind ?? "";
  const own = el ?? (q.data.kind === "spec_article" || q.data.kind === "detail" ? q.data.entity : null);
  const facts = own
    ? Object.entries(own).filter(([k, v]) => !["id", "global_id", "type", "p1", "p2", "bbox"].includes(k) && v !== "" && v != null && !(Array.isArray(v) && !v.length))
    : [];

  return (
    <div className="v2-page v2-element">
      <div className="v2-crumbs">
        <Link to="/v2">Move a column</Link> <span aria-hidden="true">/</span> Element registry
      </div>
      <h1 className="v2-title">
        <span className="mono">{eid}</span> <span className="muted v2-title-sub">{elType}</span>
        <InfoTip id="page.v2-element" />
      </h1>
      {facts.length > 0 && (
        <dl className="v2-facts">
          {facts.map(([k, v]) => (
            <div key={k}>
              <dt>{k.replace(/_/g, " ")}</dt>
              <dd className="mono">{Array.isArray(v) ? v.join(", ") : typeof v === "object" ? JSON.stringify(v) : String(v)}</dd>
            </div>
          ))}
        </dl>
      )}
      {recSelf && (
        <p className="v2-small">
          Calc record in {recSelf.calc} ({recSelf.calc_title}), UC {recSelf.uc ?? "-"}.{" "}
          <button type="button" className="btn sm" onClick={() => setView({ kind: "pdf", src: recordSource(recSelf)!, key: "self" })}>
            Open row in calc package
          </button>
        </p>
      )}
      <StatRow>
        {GROUPS.map((g) => (
          <StatPill key={g.id} label={g.label} value={g.id === "platforms" ? platformItems.length : grouped[g.id]?.length ?? 0} info={g.info} tone={g.id === "platforms" || g.id === "etabs" ? "neutral" : "accent"} />
        ))}
      </StatRow>

      <div className="v2-el-grid">
        <Panel title="Every occurrence" info="panel.reg-occurrences" className="v2-el-occ">
          {GROUPS.map((g) => {
            const items = g.id === "platforms" ? [] : grouped[g.id] ?? [];
            if (g.id === "platforms") {
              return (
                <section key={g.id} className="v2-occ-group">
                  <h3 className="v2-h3">
                    Construction platforms <span className="cg-tab-badge">{platformItems.length}</span> <PlatformSourceBadge />{" "}
                    <InfoTip id="panel.reg-platforms" />
                  </h3>
                  {cs.data && (
                    <p className="v2-small">
                      Stage: <b>{cs.data.stage}</b>
                      {cs.data.float_days != null ? `, float ${cs.data.float_days} d` : ""}
                    </p>
                  )}
                  {!platformItems.length && <p className="muted v2-small">No platform record names this element.</p>}
                  <ul className="v2-occ-list">
                    {platformItems.map((o, i) => (
                      <li key={`${o.platform}-${o.record_type}-${o.id}-${i}`}>
                        <span className="v2-chip">{(o.record_type ?? "").replace(/_/g, " ")}</span> <span className="mono">{o.number || o.record_ref}</span> {o.title}{" "}
                        <span className="v2-chip">{o.status}</span> <PlatformSourceBadge source={o.source} />{" "}
                        <MockLink url={o.link} onOpen={setMock} label={o.platform_label ? `${o.platform_label} record` : undefined} />
                      </li>
                    ))}
                  </ul>
                  <InboxHistory eid={eid} />
                </section>
              );
            }
            if (!items.length) return null;
            return (
              <section key={g.id} className="v2-occ-group">
                <h3 className="v2-h3">
                  {g.label} <span className="cg-tab-badge">{items.length}</span>
                  {g.id === "etabs" && <span className="v2-mock">mock</span>}
                </h3>
                <ul className="v2-occ-list">
                  {items.map((o, i) => {
                    const key = `${o.doc}-${i}`;
                    return (
                      <li key={key}>
                        <button type="button" className={`v2-occ${view?.key === key ? " on" : ""}`} onClick={() => openOcc(o, i)}>
                          <span className="v2-chip">{howLabel(o.how)}</span>
                          {o.sheet && !o.article && <span className="mono">{o.sheet}</span>}
                          {o.page && <span className="muted">p.{o.page}</span>}
                          {o.doc !== "etabs" && o.label && <span className="v2-chip" title="read from the document">{o.label}</span>}
                          {o.article && <span className="mono">{o.article.replace(/^SPEC:/, "")}</span>}
                          {o.via?.length ? <span className="muted">via {o.via.join(", ")}</span> : null}
                          {o.doc === "ifc" && <span className="mono muted">{o.global_id}</span>}
                          {o.doc === "etabs" && (
                            <span className="mono">
                              {o.object_type} {o.label}
                              {o.story ? `@${o.story}` : ""}
                            </span>
                          )}
                          {o.text && <span className="v2-occ-text">"{o.text.slice(0, 60)}"</span>}
                          {o.error && <span className="v2-error">{o.error}</span>}
                        </button>
                      </li>
                    );
                  })}
                </ul>
              </section>
            );
          })}
          {q.data.designed_by.length > 0 && (
            <section className="v2-occ-group">
              <h3 className="v2-h3">
                Designed by <InfoTip id="panel.reg-designed-by" />
              </h3>
              <ul className="v2-occ-list">
                {q.data.designed_by.map((r) => (
                  <li key={r.id}>
                    <button type="button" className={`v2-occ${view?.key === r.id ? " on" : ""}`} onClick={() => setView({ kind: "pdf", src: recordSource(r)!, key: r.id })} disabled={!r.page}>
                      <span className="mono">{r.id}</span> <span className="muted">{r.calc_title}</span> {r.uc != null && <span className="v2-chip">UC {r.uc}</span>}
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </Panel>

        <Panel title="Source" info="panel.reg-source" className="v2-el-src" scroll={false}>
          {!view && <p className="muted v2-pad">Pick an occurrence on the left, or a node in the graph below, to open its source here.</p>}
          {view?.kind === "pdf" && <PdfPage key={view.key} source={view.src} info="pdf.page" />}
          {view?.kind === "ifc" && (
            <Viewer3D
              ref={v3}
              url={urls.v2ModelIfc()}
              info="viewer3d.move-model"
              selected={view.gid}
              styleOf={(g) => (g === view.gid ? undefined : { color: "#c3cad3", opacity: 0.18 })}
              onLoaded={() => v3.current?.focus(view.gid)}
            />
          )}
          {view?.kind === "etabs" && (
            <div className="v2-pad">
              <p>
                <span className="v2-mock big">MOCK</span> ETABS {view.occ.object_type} <b className="mono">{view.occ.label}</b>
                {view.occ.story ? ` on ${view.occ.story}` : ""}
              </p>
              <p className="v2-small muted">
                How this element would appear in an ETABS model (object label and story). Built from our design, not read from ETABS.{" "}
                <Link to="/v2/etabs">Open the ETABS panel</Link>
              </p>
              <pre className="v2-pre">{JSON.stringify(view.occ, null, 2)}</pre>
            </div>
          )}
        </Panel>
      </div>

      <Panel title="Relations" info="graph.reg-relations" scroll={false}>
        <GraphView
          nodes={graph.nodes}
          edges={graph.edges}
          lanes={[
            { id: "in", label: "Points at this element", info: "graph.reg-lane-in" },
            { id: "self", label: "This element", info: "graph.reg-lane-self" },
            { id: "out", label: "This element points at", info: "graph.reg-lane-out" },
          ]}
          info="graph.reg-relations"
          selectedId={eid}
          onNodeClick={openNode}
          height={Math.max(320, Math.min(760, 70 + 56 * Math.max(...["in", "out"].map((l) => graph.nodes.filter((n) => n.lane === l).length), 1)))}
          footer={
            <Legend
              info="legend.reg-relations"
              items={[
                { label: "Element", color: "#2f6fed", info: "legend.reg-node-element" },
                { label: "Type / material", color: "#7c4dde", info: "legend.reg-node-type" },
                { label: "Spec article", color: "#b5650f", info: "legend.reg-node-spec" },
                { label: "Calc record", color: "#8a5cf0", info: "legend.reg-node-record" },
              ]}
            />
          }
        />
        <p className="v2-small muted">
          Relation kinds: {Object.keys(REL_COLOR).join(", ")}. Click a node to open its page (spec articles and details open in Source).
        </p>
      </Panel>
      {mock && <PlatformRecordDialog url={mock} onClose={() => setMock(null)} />}
    </div>
  );
}
