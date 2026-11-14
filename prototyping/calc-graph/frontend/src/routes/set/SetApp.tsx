// Drawing-set view: elements read off the drawings, the calc package as pages and as calc records,
// connection details, findings, and the evidence links between them. Every node, edge, link and
// finding opens the ORIGINAL PDF page zoomed to the words that produced it.
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useSearchParams } from "react-router-dom";
import { urls } from "../../api/client";
import { useSetGraph, useSetIntegrated, useSets } from "../../api/hooks";
import type { CEdge, CInst, EEdge, Ev, Lnk, Note, REdge, RLink, SetFinding } from "../../api/types";
import { EvidenceCompare } from "../../components/EvidenceCompare";
import { GraphView } from "../../components/GraphView";
import { Legend } from "../../components/Legend";
import { PdfPage, PdfSplit, type PdfSource } from "../../components/PdfPage";
import { StatPill, StatRow } from "../../components/StatPill";
import { Tabs } from "../../components/Tabs";
import { InfoTip } from "../../help/InfoTip";
import { buildGraph, selNodeId, type Actions } from "./graphs";
import {
  buildIndex,
  calcEv,
  cinstEv,
  ctypeEv,
  docLabel,
  elEv,
  has,
  hashOf,
  mergeEv,
  noteEv,
  parseHash,
  recEv,
  rowsOnPage,
  tierCls,
  type Hash,
  type ListTab,
  type Sel,
  type SetIndex,
} from "./model";
import { Set3D } from "./Set3D";
import { SetInspector, type InspActions } from "./SetInspector";
import { SetList } from "./SetList";
import "./set.css";

/** what the evidence pane shows: one page, one page with a caption bar, two pages stacked, or a link compare */
type Evidence =
  | { mode: "none" }
  | { mode: "single"; a: Ev; focus?: readonly number[] | null; title?: ReactNode }
  | { mode: "split"; a: Ev; b: Ev; title: ReactNode }
  | { mode: "compare"; a: Ev; b: Ev; title: ReactNode; aTitle: string; bTitle: string; extra?: Ev };

const chip = (cls: string, t: ReactNode) => <span className={`chip ${cls}`}>{t}</span>;

export default function SetApp() {
  const sets = useSets();
  const [params, setParams] = useSearchParams();
  const sid = params.get("set") || sets.data?.[0]?.id;
  const graphQ = useSetGraph(sid);
  const igQ = useSetIntegrated(sid);
  const igDone = igQ.isSuccess || igQ.isError;
  const x = useMemo<SetIndex | null>(() => (sid && graphQ.data && igDone ? buildIndex(sid, graphQ.data, igQ.data ?? null) : null), [sid, graphQ.data, igQ.data, igDone]);

  const [sel, setSel] = useState<Sel>(null);
  const [tab, setTab] = useState<ListTab>("el");
  const [q, setQ] = useState("");
  const [open, setOpen] = useState<Set<string>>(new Set());
  const [ev, setEv] = useState<Evidence>({ mode: "none" });
  const view3d = params.get("view") === "3d";
  const [seen3d, setSeen3d] = useState(view3d);
  useEffect(() => {
    if (view3d) setSeen3d(true);
  }, [view3d]);

  const writeHash = (h: Hash) => window.history.replaceState(window.history.state, "", `${window.location.pathname}${window.location.search}${h ? hashOf(h) : "#"}`);

  // ---- evidence openers (port of the legacy single / split / open* functions)
  const show = useCallback((a: Ev, focus?: readonly number[] | null, title?: ReactNode) => setEv({ mode: "single", a, focus, title }), []);
  const openEvs = useCallback(
    (evs: Ev[], title: ReactNode) => {
      const m = mergeEv(evs.filter((e) => e && e.rects));
      if (!m.length) return;
      if (m.length >= 2) setEv({ mode: "split", a: m[0], b: m[m.length - 1], title });
      else show(m[0], null, title);
    },
    [show],
  );
  const xr = useRef(x);
  xr.current = x;

  const actions = useMemo(() => {
    const X = () => xr.current!;
    const openLink = (l: Lnk) => {
      const e = X().els.get(l.el)!, c = X().calcs.get(l.calc)!;
      setEv({
        mode: "compare",
        a: l.evidence.el,
        b: l.evidence.calc,
        aTitle: `Drawing: ${e.text} (${e.sheet})`,
        bTitle: `Calc page: ${c.sheet_id} ${c.title}`,
        extra: l.evidence.el.extra?.[0],
        title: (
          <>
            <b>{e.text}</b> ({e.sheet}) ↔ <b>{c.sheet_id}</b> {c.title} {chip(tierCls(l.score), `${l.tier} ${Math.round(l.score * 100)}%`)} <span className="why">{l.rule}</span>
          </>
        ),
      });
      writeHash({ k: "link", el: l.el, calc: l.calc });
    };
    const openRLink = (l: RLink, rid: string) => {
      const x0 = X();
      const e = x0.els.get(l.el)!, c = x0.calcs.get(l.calc)!, r = x0.recs.get(rid)!;
      // a table record's row carries the size; a page record keeps the page link's own evidence beside the record's title
      const rows = rowsOnPage(r, c.doc, c.page);
      const tableRow = rows.length && r.ev.some((y) => y.doc === c.doc && y.page === c.page && y.table);
      const pl = (x0.linksByEl.get(l.el) ?? []).find((y) => y.calc === l.calc);
      const right = tableRow ? rows[0] : (mergeEv([...(pl ? [pl.evidence.calc] : []), ...rows])[0] ?? recEv(r));
      setEv({
        mode: "compare",
        a: elEv(e),
        b: right,
        aTitle: `Drawing: ${e.text} (${e.sheet})`,
        bTitle: `Calc record: ${r.title} on ${c.sheet_id}`,
        title: (
          <>
            <b>{e.text}</b> ({e.sheet}) ↔ <b>{r.title}</b> on {c.sheet_id} {chip(tierCls(l.score), `${l.tier} ${Math.round(l.score * 100)}%`)} <span className="why">{l.rule}</span>
          </>
        ),
      });
      writeHash({ k: "rlink", el: l.el, calc: l.calc, rec: rid });
    };
    const openEEdge = (e: EEdge) => {
      const a = X().els.get(e.src)!, b = X().els.get(e.dst)!;
      openEvs(e.evidence, (
        <>
          <b>{a.text}</b> ({a.sheet}) → <b>{b.text}</b> ({b.sheet}) {chip("", e.rule)}
        </>
      ));
    };
    const openCEdge = (e: CEdge) => {
      const a = X().calcs.get(e.src)!, b = X().calcs.get(e.dst)!;
      setEv({
        mode: "split",
        a: mergeEv(e.evidence.src)[0],
        b: mergeEv(e.evidence.dst)[0],
        title: (
          <>
            <b>{a.sheet_id}</b> {a.title} → <b>{b.sheet_id}</b> {b.title} {chip("", e.rule)}{" "}
            <span className="why">
              {e.labels.slice(0, 6).join(", ")}
              {e.labels.length > 6 ? "…" : ""}
            </span>
          </>
        ),
      });
    };
    const openREdge = (e: REdge) => {
      const a = X().recs.get(e.src), b = e.dst ? X().recs.get(e.dst) : null;
      const t = (
        <>
          <b>{a?.title ?? e.src}</b> → {b ? <b>{b.title}</b> : chip("bad", "no support found")} {chip(e.join === "exact" ? "good" : e.join === "inferred" ? "warn" : "bad", e.join)}{" "}
          <span className="why">
            {e.kind}: {e.rule}
          </span>
        </>
      );
      const src = mergeEv(e.evidence.src), dst = mergeEv(e.evidence.dst);
      if (src.length && dst.length) setEv({ mode: "split", a: src[0], b: dst[0], title: t });
      else openEvs([...src, ...dst], t);
    };
    const openInstEl = (i: CInst, elId: string) => {
      const e = X().els.get(elId)!;
      const at = i.attached.find((y) => y.id === elId);
      openEvs([cinstEv(i), elEv(e)], (
        <>
          <b>{i.type_id ?? i.ref}</b> {i.via} → <b>{e.text}</b> ({e.sheet}) {chip("", `${at?.role ?? "attached"} · ${at?.dist ?? "?"} pt`)} <span className="why">{i.attach_rule}</span>
        </>
      ));
    };
    const openFinding = (idx: number) => {
      const f: SetFinding | undefined = X().findings[idx];
      if (!f) return;
      const evs = mergeEv(f.evidence);
      const t = (
        <>
          {chip(f.severity === "high" ? "bad" : "", f.kind)} {f.text}
        </>
      );
      if (evs.length >= 2) setEv({ mode: "split", a: evs[0], b: evs[1], title: t });
      else if (evs.length) show(evs[0], null, t);
    };
    const openNote = (n: Note) => show(noteEv(n));
    return { openLink, openRLink, openEEdge, openCEdge, openREdge, openInstEl, openFinding, openNote };
  }, [openEvs, show]);

  /** select + open the selection's own evidence (legacy select(sel, open=true)) */
  const select = useCallback(
    (s: Sel, openEv = true) => {
      const x0 = xr.current;
      setSel(s);
      writeHash(s ? { k: s.kind, v: s.id } : null);
      if (!s || !x0 || !openEv || !has(x0, s)) return;
      if (s.kind === "el") show(elEv(x0.els.get(s.id)!));
      else if (s.kind === "calc") show(calcEv(x0.calcs.get(s.id)!));
      else if (s.kind === "rec") show(recEv(x0.recs.get(s.id)!));
      else if (s.kind === "ctype") {
        const t = x0.ctypes.get(s.id)!;
        show(ctypeEv(t), t.bbox);
      } else show(cinstEv(x0.cinst.get(s.id)!));
    },
    [show],
  );

  const onFinding = useCallback(
    (i: number) => {
      const x0 = xr.current;
      const f = x0?.findings[i];
      if (!x0 || !f) return;
      writeHash({ k: "find", i });
      if (f.el) setSel({ kind: "el", id: f.el });
      else if (f.calc) setSel({ kind: "calc", id: f.calc });
      else if (f.rec && x0.recs.has(f.rec)) setSel({ kind: "rec", id: f.rec });
      actions.openFinding(i);
    },
    [actions],
  );

  // deep links: apply the hash once data is in, and on every hashchange
  const fromHash = useCallback(() => {
    const x0 = xr.current;
    if (!x0) return;
    const h = parseHash(window.location.hash);
    if (!h) return;
    if (h.k === "link") {
      const l = (x0.linksByEl.get(h.el) ?? []).find((y) => y.calc === h.calc);
      if (l) {
        setSel({ kind: "el", id: h.el });
        actions.openLink(l);
      }
    } else if (h.k === "rlink") {
      const l = (x0.rlByEl.get(h.el) ?? []).find((y) => y.calc === h.calc && y.records.includes(h.rec));
      if (l) {
        setSel({ kind: "el", id: h.el });
        actions.openRLink(l, h.rec);
      }
    } else if (h.k === "find") {
      setTab("find");
      onFinding(h.i);
    } else if (has(x0, { kind: h.k, id: h.v })) select({ kind: h.k, id: h.v });
  }, [actions, onFinding, select]);
  useEffect(() => {
    if (x) fromHash();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [x]);
  useEffect(() => {
    window.addEventListener("hashchange", fromHash);
    return () => window.removeEventListener("hashchange", fromHash);
  }, [fromHash]);

  const graphActions: Actions = useMemo(
    () => ({
      select: (s) => select(s),
      openLink: actions.openLink,
      openEEdge: actions.openEEdge,
      openCEdge: actions.openCEdge,
      openREdge: actions.openREdge,
      openRLink: actions.openRLink,
      openInstEl: actions.openInstEl,
      openFindingKind: (kind) => {
        const i = xr.current?.findings.findIndex((f) => f.kind === kind) ?? -1;
        if (i >= 0) {
          setTab("find");
          onFinding(i);
        }
      },
      overviewEls: (key, first) => {
        setTab("el");
        setOpen((o) => new Set(o).add(key));
        select({ kind: "el", id: first });
      },
      overviewCalcs: (first) => {
        setTab("calc");
        select({ kind: "calc", id: first });
      },
    }),
    [actions, select, onFinding],
  );
  const built = useMemo(() => (x ? buildGraph(x, sel, graphActions) : null), [x, sel, graphActions]);

  const inspActions: InspActions = useMemo(
    () => ({ select: (s) => select(s), show: (a, f) => show(a, f), ...actions }),
    [actions, select, show],
  );

  const toggle = (k: string) =>
    setOpen((o) => {
      const n = new Set(o);
      if (n.has(k)) n.delete(k);
      else n.add(k);
      return n;
    });
  const filterFindings = (kind: string) => {
    setTab("find");
    setQ("");
    setOpen((o) => new Set(o).add(kind));
  };
  const set3d = (on: boolean) => {
    const p = new URLSearchParams(params);
    if (on) p.set("view", "3d");
    else p.delete("view");
    setParams(p, { replace: true });
    // keep the deep-link hash (setParams drops it)
    requestAnimationFrame(() => {
      if (sel) writeHash({ k: sel.kind, v: sel.id });
    });
  };
  const openDiff = (i: number) => {
    const d = x?.ig?.overlay.differences[i];
    if (!d) return;
    const c = mergeEv(d.calc), w = mergeEv(d.draw);
    const t = (
      <>
        {chip("bad", d.what)} {d.text}
      </>
    );
    if (c.length && w.length) setEv({ mode: "split", a: c[0], b: w[0], title: t });
    else openEvs([...c, ...w], t);
  };

  // ---- evidence -> PdfSource
  const src = (e: Ev | undefined, focus?: readonly number[] | null): PdfSource | null =>
    e && x
      ? {
          url: urls.setDocFile(x.sid, e.doc),
          page: e.page,
          rects: (e.rects ?? []).filter((r) => r && r.length === 4),
          focus: focus ?? null,
          label: docLabel(x, e),
          sub: (
            <>
              {e.text && <span className="mono">{e.text}</span>}
              {e.note ? ` - ${e.note}` : ""}
            </>
          ),
        }
      : null;
  const [compareLeftExtra, setCompareLeftExtra] = useState(false);
  useEffect(() => setCompareLeftExtra(false), [ev]);
  const two = ev.mode === "split" || ev.mode === "compare";

  if (sets.isSuccess && !sets.data.length)
    return (
      <div className="page">
        <h1>Drawing-set view</h1>
        <p className="page-lede">
          No drawing set ingested yet. Run <span className="mono">uv run calc-graph ingest-set --plans ... --calcs ...</span>
        </p>
      </div>
    );
  const loadErr = sets.error ?? graphQ.error;
  if (loadErr)
    return (
      <div className="page" role="alert">
        <h1>Drawing-set view</h1>
        <p className="page-lede">Could not load the drawing set: {loadErr instanceof Error ? loadErr.message : String(loadErr)}</p>
      </div>
    );
  if (!x) return <div className="page muted">Loading the drawing set...</div>;

  const c = x.g.coverage as Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any
  const ig = x.ig;
  const cv = (ig?.coverage ?? {}) as Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any
  const j = cv.record_edges_by_join ?? {};
  const nf = (k: string) => ig?.findings.filter((f) => f.kind === k).length ?? 0;
  const tabs = [
    { id: "el" as const, label: "Elements", info: "tab.set-elements" as const },
    { id: "rec" as const, label: "Calc records", info: "tab.set-records" as const },
    { id: "calc" as const, label: "Calc pages", info: "tab.set-pages" as const },
    { id: "conn" as const, label: "Connections", info: "tab.set-connections" as const },
    { id: "find" as const, label: "Findings", info: "tab.set-findings" as const },
  ];
  const graphLegend = (
    <Legend
      info="legend.set-graph"
      items={[
        { label: "load path (drawings)", color: "var(--ink)", shape: "line", info: "legend.set-load-path" },
        ...(built?.kind === "calc" || !ig ? [{ label: "calc feeds", color: "var(--calc)", shape: "line" as const, info: "legend.set-calc-feeds" as const }] : []),
        ...(ig
          ? [
              { label: "calc load path - exact", color: "var(--calc)", shape: "line" as const, info: "legend.edge-exact" as const },
              { label: "inferred", color: "var(--calc)", shape: "dashed" as const, info: "legend.edge-inferred" as const },
              { label: "absent", color: "var(--bad)", shape: "dotted" as const, info: "legend.edge-absent" as const },
              { label: "connection", color: "#e8590c", shape: "line" as const, info: "legend.set-connection" as const },
            ]
          : []),
        { label: "link ≥ 75%", color: "var(--good)", shape: "dashed", info: "legend.link-high" },
        { label: "55-74%", color: "var(--warn)", shape: "dashed", info: "legend.link-mid" },
        { label: "< 55%", color: "var(--bad)", shape: "dashed", info: "legend.link-low" },
      ]}
    />
  );

  return (
    <div className={`set-app${two ? " split" : ""}`}>
      <div className="set-head">
        <span className="set-crumb">Drawing set</span>
        <b className="set-name">{x.g.name}</b>
        <InfoTip id="page.set" />
        <span className="spacer" />
        <button
          type="button"
          className="btn sm"
          title="Back to the overview of all links"
          onClick={() => {
            select(null, false);
            setEv({ mode: "none" });
          }}
        >
          Overview
        </button>
        <InfoTip id="tool.set-overview" />
      </div>
      <div className="set-pills">
        <StatRow>
          <StatPill label={`elements from ${x.g.sheets.length} sheets`} value={c.elements} info="stat.set-elements" />
          <StatPill label="load-path edges" value={c.load_path_edges} info="stat.set-load-path" />
          <StatPill label="calc pages" value={c.calc_pages} info="stat.set-calc-pages" />
          <StatPill label="calc feed edges" value={c.calc_edges} info="stat.set-calc-feeds" />
          <StatPill label="elements linked" value={c.elements_linked} tone="good" info="stat.set-linked" />
          <StatPill label="no calc found" value={c.elements - c.elements_linked} tone="bad" info="stat.set-no-calc" onClick={() => filterFindings("no calc found")} />
          <StatPill label="calc pages linked to nothing" value={c.calc_pages_unlinked} tone="warn" info="stat.set-pages-unlinked" onClick={() => filterFindings("calc page linked to nothing")} />
          <StatPill
            label="links by rule"
            value={Object.entries(c.links_by_tier ?? {})
              .map(([k, v]) => `${k} ${v}`)
              .join(" · ")}
            info="stat.set-links-by-rule"
          />
          {ig && ig.stale.length > 0 && <StatPill label="stale record / connection data" value="rebuild" tone="bad" info="stat.set-stale" title={ig.stale.join("; ")} />}
          {ig && (
            <>
              <StatPill label="calc records" value={cv.records} info="stat.set-records" onClick={() => setTab("rec")} />
              <StatPill label="load path exact · inferred · absent" value={`${j.exact ?? 0} · ${j.inferred ?? 0} · ${j.absent ?? 0}`} info="stat.set-record-joins" onClick={() => setTab("rec")} />
              <StatPill
                label="connection details · placed · attached"
                value={`${cv.connection_types} · ${cv.connection_instances} · ${cv.connection_instances_attached}`}
                info="stat.set-connections"
                onClick={() => setTab("conn")}
              />
              <StatPill label="load-path gaps" value={nf("gravity load-path gap")} tone="bad" info="stat.set-gaps" onClick={() => filterFindings("gravity load-path gap")} />
              <StatPill label="unsupported member ends" value={nf("unsupported member end")} tone="bad" info="stat.set-unsupported" onClick={() => filterFindings("unsupported member end")} />
            </>
          )}
        </StatRow>
      </div>

      <div className="set-main">
        <section className="set-left cg-panel" aria-label="Lists">
          <div className="set-ltop">
            <Tabs label="List" info="tabs.set-list" size="sm" value={tab} onChange={setTab} items={tabs} />
            <span className="set-search">
              <input type="search" value={q} onChange={(e) => setQ(e.target.value.trim().toLowerCase())} placeholder="Search size, sheet, grid, calc id, title" aria-label="Search" autoComplete="off" />
              <InfoTip id="tool.set-search" />
            </span>
          </div>
          <SetList x={x} tab={tab} q={q} open={open} sel={sel} onToggle={toggle} onSelect={(s) => select(s)} onFinding={onFinding} />
        </section>

        <section className="set-center cg-panel">
          <div className="set-ctabs">
            <Tabs
              label="Centre view"
              info="tabs.set-center"
              size="sm"
              value={view3d ? "3d" : "graph"}
              onChange={(t) => set3d(t === "3d")}
              items={[
                { id: "graph", label: "Graph", info: "tab.set-graph" },
                { id: "3d", label: "3D model (from plans)", info: "tab.set-3d" },
              ]}
            />
          </div>
          {!view3d && built && (
            <div className="set-graph">
              {built.hint && <div className="set-hint">{built.hint}</div>}
              <GraphView
                nodes={built.nodes}
                edges={built.edges}
                lanes={built.lanes}
                info="graph.set"
                height={Math.max(380, Math.min(1500, Math.max(...built.lanes.map((l) => built.nodes.filter((n) => n.lane === l.id).length)) * 56 * 0.75 + 110))}
                fitMinZoom={0.6}
                compactLanes
                selectedId={selNodeId(sel)}
                onNodeClick={(n) => n.data?.run()}
                onEdgeClick={(e) => e.data?.run()}
                footer={
                  <>
                    {built.more.length > 0 && <div className="set-more muted">{built.more.join(" · ")}</div>}
                    {graphLegend}
                  </>
                }
              />
            </div>
          )}
          {seen3d && (
            <div className="set-3d-wrap" hidden={!view3d}>
              <Set3D x={x} sel={sel} onSelect={(s) => select(s)} onDiff={openDiff} />
            </div>
          )}
        </section>

        <section className="set-right cg-panel">
          <SetInspector x={x} sel={sel} a={inspActions} />
          <div className="set-evidence">
            {ev.mode === "none" && <PdfPage source={null} info="pdf.page" emptyText="Click any node, link or finding to open the original page here." />}
            {ev.mode === "single" && (
              <>
                {ev.title && (
                  <div className="cg-pdf-splitbar set-evbar">
                    <span className="set-evtitle">{ev.title}</span>
                    <InfoTip id="evidence.set-caption" />
                    <button type="button" className="btn sm" onClick={() => setEv({ ...ev, title: undefined })}>
                      Close
                    </button>
                  </div>
                )}
                <PdfPage source={src(ev.a, ev.focus)} info="pdf.page" />
              </>
            )}
            {ev.mode === "split" && (
              <PdfSplit
                primary={src(ev.a)}
                secondary={src(ev.b)}
                splitTitle={<span className="set-evtitle">{ev.title}</span>}
                info="pdf.split"
                pageInfo="pdf.page"
                onCloseSecondary={() => setEv({ mode: "single", a: ev.a })}
              />
            )}
            {ev.mode === "compare" && (
              <div className="set-compare">
                <div className="cg-pdf-splitbar set-evbar">
                  <span className="set-evtitle">{ev.title}</span>
                  {ev.extra && (
                    <button type="button" className="btn sm" onClick={() => setCompareLeftExtra((v) => !v)}>
                      {compareLeftExtra ? "Show the plan tag on the left" : "Show schedule row on the left"}
                    </button>
                  )}
                  <button type="button" className="btn sm" title="Back to a single page" onClick={() => setEv({ mode: "single", a: ev.a })}>
                    Close
                  </button>
                </div>
                <EvidenceCompare
                  left={src(compareLeftExtra && ev.extra ? { ...ev.extra, note: "foundation schedule row" } : ev.a)}
                  right={src(ev.b)}
                  leftTitle={compareLeftExtra ? "Drawing: foundation schedule row" : ev.aTitle}
                  rightTitle={ev.bTitle}
                  info="evidence.set-link-compare"
                  pageInfo="pdf.page"
                />
              </div>
            )}
          </div>
        </section>
      </div>
      <p className="set-foot muted">
        Elements are tags read off the structural sheets; calc records are the rows of the calc package tables, with pages kept as evidence; connections are the
        connection details and where they are called out. Every link and edge is a deterministic rule and keeps the words it came from on both documents.
      </p>
    </div>
  );
}
