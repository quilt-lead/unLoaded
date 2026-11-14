// Synthetic IFC app: a BIM model (IFC) mapped to a calc package (PDF). Calc list on the left, 3D model
// or load-path graph in the middle, impact + inspector on the right, original calc pages in a dialog.
import { useCallback, useEffect, useMemo, useRef, useState, type ChangeEvent } from "react";
import { urls } from "../../api/client";
import { useDecide, useImpact, useLoadSample, useProjectState, useUpload } from "../../api/hooks";
import type { IfcLink } from "../../api/types";
import { Legend, type LegendItem } from "../../components/Legend";
import { Panel } from "../../components/Panel";
import { PdfPage } from "../../components/PdfPage";
import { StatPill, StatRow } from "../../components/StatPill";
import { Tabs } from "../../components/Tabs";
import { Viewer3D, type Viewer3DHandle } from "../../components/Viewer3D";
import { InfoTip } from "../../help/InfoTip";
import type { Viewer } from "../../viewer";
import { Inspector } from "./Inspector";
import { LoadPathGraph } from "./LoadPathGraph";
import {
  CAT_COLORS,
  GREY,
  IMPACTED,
  REMOVED,
  STATUS_COLORS,
  elLabel,
  indexState,
  linksFor,
  linksOfCalc,
  pageRange,
  paintOf,
  type ColorBy,
  type Sel,
} from "./model";
import Review from "../review/Review";
import "./ifc.css";

const PID = 1;

export default function IfcApp() {
  const liveState = useProjectState(PID);
  const [preview,setPreview] = useState<any|null>(null);
  const state = {...liveState, data: preview ?? liveState.data};
  const [reviewOpen,setReviewOpen] = useState(false);
  const reviewDialog = useRef<HTMLDialogElement>(null);
  const showReview = () => {setReviewOpen(true);reviewDialog.current?.showModal();};
  useEffect(()=>setPreview(null),[liveState.data?.model_rev?.id,liveState.data?.calc_rev?.id]);
  const decide = useDecide(PID);
  const sample = useLoadSample(PID);
  const upload = useUpload(PID);
  const ix = useMemo(() => (state.data ? indexState(state.data) : null), [state.data]);

  const [sel, setSel] = useState<Sel>(null);
  const [filter, setFilter] = useState<string | null>(null);
  const [colorBy, setColorBy] = useState<ColorBy>("calc");
  const [xray, setXray] = useState(false);
  const [level, setLevel] = useState("");
  const [tab, setTab] = useState<"3d" | "graph">("3d");
  const [impactReq, setImpactReq] = useState<{ gid: string; mode: "change" | "remove" } | null>(null);
  const impactQ = useImpact(PID, impactReq?.gid ?? null, impactReq?.mode ?? "change");
  const historical = preview && (preview.model_rev?.id !== liveState.data?.model_rev?.id || preview.calc_rev?.id !== liveState.data?.calc_rev?.id);
  const impact = !historical && impactReq && impactQ.data && impactQ.data.global_id === impactReq.gid ? impactQ.data : null;
  const [busyText, setBusyText] = useState("");
  const [err, setErr] = useState("");
  const [page, setPage] = useState<{ n: number; rects: number[][]; rectPage: number } | null>(null);
  const [tip, setTip] = useState<{ x: number; y: number; gid: string } | null>(null);
  const v3 = useRef<Viewer3DHandle>(null);
  const wrap = useRef<HTMLDivElement>(null);
  const dlg = useRef<HTMLDialogElement>(null);

  const showError = useCallback((e: unknown) => {
    setErr(e instanceof Error ? e.message : String(e));
    window.setTimeout(() => setErr(""), 8000);
  }, []);
  useEffect(() => {
    if (state.error) showError(state.error);
  }, [state.error, showError]);
  useEffect(() => {
    if (impactQ.error) showError(impactQ.error);
  }, [impactQ.error, showError]);

  // drop a selection that the new revision no longer has
  useEffect(() => {
    if (!ix || !sel) return;
    if ((sel.kind === "el" && !ix.els.has(sel.id)) || (sel.kind === "calc" && !ix.calcs.has(sel.id))) setSel(null);
  }, [ix, sel]);

  const select = useCallback((s: Sel, focus = false) => {
    setSel(s);
    if (s) setFilter(null);
    if (focus && s?.kind === "el") requestAnimationFrame(() => v3.current?.focus(s.id));
  }, []);

  const st = ix?.st;
  const levels = useMemo(() => [...new Set((st?.elements ?? []).map((e) => e.storey).filter(Boolean))], [st]);
  useEffect(() => setLevel(""), [st?.model_rev?.id]);

  const paintOpts = useMemo(() => ({ colorBy, sel, filter, impact, xray, level }), [colorBy, sel, filter, impact, xray, level]);
  const styleOf = useCallback(
    (gid: string) => {
      const el = ix?.els.get(gid);
      return el ? paintOf(ix!, el, paintOpts) : undefined;
    },
    [ix, paintOpts],
  );

  const run = useCallback(
    async (text: string, fn: () => Promise<unknown>) => {
      setBusyText(text);
      try {
        await fn();
        requestAnimationFrame(() => v3.current?.fit());
      } catch (e) {
        showError(e);
      } finally {
        setBusyText("");
      }
    },
    [showError],
  );
  const loadSample = () => run("Ingesting the synthetic building and calc package…", () => sample.mutateAsync(1));
  const loadRev2 = () => run("Ingesting model revision 2 (column C8 removed)…", () => sample.mutateAsync(2));
  const onFile = (kind: "model" | "calcs") => (e: ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    e.target.value = "";
    if (f) run(`Reading ${f.name}…`, () => upload.mutateAsync({ kind, file: f }));
  };
  const onDecide = (gid: string, key: string, action: "confirm" | "reject" | "manual" | "undo") =>
    decide.mutateAsync({ global_id: gid, calc_key: key, action }).catch(showError);
  const onConfirmAll = (ls: IfcLink[]) =>
    Promise.all(ls.map((l) => decide.mutateAsync({ global_id: l.global_id, calc_key: l.calc_key, action: "confirm" }))).catch(showError);

  // the page dialog (original calc page, evidence highlighted)
  const openPage = (n: number, rects: number[][] = []) => {
    setPage((p) => ({ n, rects: rects.length ? rects : p && p.rectPage === n ? p.rects : [], rectPage: rects.length ? n : (p?.rectPage ?? 0) }));
    if (dlg.current && !dlg.current.open) dlg.current.showModal();
  };
  const pageCount = st?.pages.length ?? 0;
  const pageCalc = page && ix ? [...ix.calcs.values()].find((c) => c.pages.includes(page.n)) : undefined;

  // 3D hover tip: attach once per Viewer instance
  const hooked = useRef(new WeakSet<Viewer>());
  const ixRef = useRef(ix);
  ixRef.current = ix;
  const onLoaded = useCallback((viewer: Viewer) => {
    requestAnimationFrame(() => viewer.fit());
    if (hooked.current.has(viewer)) return;
    hooked.current.add(viewer);
    const cv = viewer.renderer.domElement;
    cv.addEventListener("pointermove", (e) => {
      if (e.buttons || !ixRef.current) return setTip(null);
      const g = viewer.pick(e);
      if (!g || !ixRef.current.els.has(g)) return setTip(null);
      const r = wrap.current!.getBoundingClientRect();
      setTip({ x: Math.min(e.clientX - r.left + 14, r.width - 270), y: e.clientY - r.top + 14, gid: g });
    });
    cv.addEventListener("pointerleave", () => setTip(null));
  }, []);

  const hasData = !!st && (st.elements.length > 0 || st.pages.length > 0);
  const counts = st?.counts ?? {};
  const linkedCalcs = ix ? [...ix.calcs.values()].filter((c) => linksOfCalc(ix, c.key).length).length : 0;
  const pill = (k: string) => ({ active: filter === k, onClick: () => { setFilter(filter === k ? null : k); setSel(null); setImpactReq(null); } });

  const legendItems: LegendItem[] = !ix
    ? []
    : impact
      ? [
          { label: "Removed / orphaned", color: REMOVED, info: "legend.ifc-removed" },
          { label: "On the impacted load path", color: IMPACTED, info: "legend.ifc-impacted" },
        ]
      : colorBy === "status"
        ? [
            { label: "Linked (high confidence / confirmed)", color: STATUS_COLORS.confirmed, info: "legend.ifc-status-confirmed" },
            { label: "Needs review", color: STATUS_COLORS.review, info: "legend.ifc-status-review" },
            { label: "No calc found", color: STATUS_COLORS.unmapped, info: "legend.ifc-status-unmapped" },
          ]
        : colorBy === "cat"
          ? [...new Set([...ix.els.values()].map((e) => e.cat))].map((c) => ({ label: c, color: CAT_COLORS[c] ?? CAT_COLORS.Other, info: "legend.ifc-type-item" as const }))
          : [
              ...[...ix.calcs.values()].filter((c) => linksOfCalc(ix, c.key).length).map((c) => ({ label: c.title, color: c.color, info: "legend.ifc-calc-item" as const })),
              { label: "No calc found", color: GREY, info: "legend.ifc-no-calc" },
            ];

  const busy = !!busyText || decide.isPending;
  const stale = impact?.stale ?? {};
  const tipEl = tip && ix ? ix.els.get(tip.gid) : undefined;

  return (
    <div className="ifc-app">
      <div className="ifc-toolbar">
        <span className="ifc-tool ifc-title">
          <b>IFC workspace</b>
          <InfoTip id="page.ifc" />
        </span>
        <span className="ifc-tool">
          <label className="btn">
            ⬆ BIM model (.ifc)
            <input type="file" accept=".ifc" onChange={onFile("model")} disabled={busy} />
          </label>
          <InfoTip id="tool.ifc-upload-model" />
          <span className="ifc-src" title={st?.model_rev?.source_name}>
            {st?.model_rev ? `${st.model_rev.source_name} (rev ${st.model_rev.seq})` : "none"}
          </span>
        </span>
        <span className="ifc-tool">
          <label className="btn">
            ⬆ Calc package (.pdf)
            <input type="file" accept=".pdf,application/pdf" onChange={onFile("calcs")} disabled={busy} />
          </label>
          <InfoTip id="tool.ifc-upload-calcs" />
          <span className="ifc-src" title={st?.calc_rev?.source_name}>
            {st?.calc_rev ? `${st.calc_rev.source_name} (rev ${st.calc_rev.seq}, ${st.pages.length} pp)` : "none"}
          </span>
        </span>
        <span className="ifc-tool">
          <button type="button" className="btn primary" onClick={loadSample} disabled={busy}>
            Load sample
          </button>
          <InfoTip id="tool.ifc-sample" />
        </span>
        <span className="ifc-tool">
          <button type="button" className="btn" onClick={loadRev2} disabled={busy || !st?.model_rev} title="Ingest the synthetic model revision 2 (column C8 removed)">
            Ingest sample rev 2
          </button>
          <InfoTip id="tool.ifc-rev2" />
        </span>
        <button className="btn" onClick={showReview}>History &amp; beam checks</button>
        {historical && <button className="btn" onClick={()=>{setPreview(null);setReviewOpen(false);}}>Return to latest model</button>}
        <span className="spacer" />
        <span className="ifc-tool">
          <a className={`btn${st?.run ? "" : " disabled"}`} href={st?.run ? urls.exportProject(PID) : undefined} aria-disabled={!st?.run} download>
            Export mapping JSON
          </a>
          <InfoTip id="tool.ifc-export" />
        </span>
      </div>

      {hasData && st && (
        <div className="ifc-pills">
          <StatRow>
            <StatPill label="model elements" value={st.elements.length} info="stat.ifc-elements" />
            <StatPill label="load-path edges" value={st.edges.length} info="stat.ifc-edges" />
            <StatPill label={`calcs in ${st.pages.length} pp`} value={st.calcs.length} info="stat.ifc-calcs" />
            <StatPill label="calcs linked" value={linkedCalcs} info="stat.ifc-calcs-linked" />
            <StatPill label="calc dependencies" value={st.calc_edges.length} info="stat.ifc-calc-deps" />
            <StatPill label="elements linked" value={counts.confirmed ?? 0} tone="good" info="stat.ifc-linked" {...pill("confirmed")} />
            <StatPill label="need review" value={counts.review ?? 0} tone="warn" info="stat.ifc-review" {...pill("review")} />
            <StatPill label="no calc found" value={counts.unmapped ?? 0} tone="bad" info="stat.ifc-unmapped" {...pill("unmapped")} />
            {st.model_rev && (
              <StatPill label="model rev / calcs rev" value={`${st.model_rev.seq} / ${st.calc_rev?.seq ?? "-"}`} info="stat.ifc-revs" title="Every upload is a revision" />
            )}
          </StatRow>
        </div>
      )}

      <div className="ifc-main">
        <Panel
          title="Calc package"
          info="panel.ifc-calcs"
          className="ifc-left"
          actions={ix && ix.calcs.size ? `${ix.calcs.size} calcs` : undefined}
        >
          {!ix || !ix.calcs.size ? (
            <p className="muted">
              Upload a calc package PDF, or press <b>Load sample</b>.
            </p>
          ) : (
            <ul className="ifc-calcs">
              {[...ix.calcs.values()].map((c) => {
                const ls = linksOfCalc(ix, c.key);
                const n = new Set(ls.map((l) => l.global_id)).size;
                const rv = ls.filter((l) => l.conf < 0.8 && l.status === "auto").length;
                const on = sel?.kind === "calc" && sel.id === c.key;
                return (
                  <li key={c.key}>
                    <button type="button" className={`ifc-calc${on ? " sel" : ""}`} aria-pressed={on} onClick={() => select(on ? null : { kind: "calc", id: c.key })}>
                      <span className="sw" style={{ background: n ? c.color : "transparent", border: `1px solid ${n ? c.color : "var(--line)"}` }} />
                      <span className="ifc-calc-body">
                        <span className="t">{c.title}</span>
                        <span className="m">
                          {pageRange(c)}
                          {c.software ? ` · ${c.software}` : ""}
                        </span>
                        <span className="chips">
                          {stale[c.key] && (
                            <span className="chip warn" title={stale[c.key]}>
                              stale - re-run
                            </span>
                          )}
                          {c.front ? (
                            <span className="chip">front matter - not mapped</span>
                          ) : n ? (
                            <span className="chip good">
                              {n} element{n > 1 ? "s" : ""}
                            </span>
                          ) : (
                            <span className={`chip${c.scanned ? " bad" : ""}`}>{c.scanned ? "no text - needs OCR" : "no elements"}</span>
                          )}
                          {rv > 0 && <span className="chip warn">{rv} to review</span>}
                          {c.cat && <span className="chip">{c.cat}</span>}
                        </span>
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </Panel>

        <section className="ifc-center cg-panel">
          <div className="ifc-center-head">
            <Tabs
              label="Centre view"
              info="tabs.ifc-view"
              value={tab}
              onChange={(t) => {
                setTab(t);
                setTip(null);
              }}
              items={[
                { id: "3d", label: "3D model", info: "tab.ifc-3d" },
                { id: "graph", label: "Load-path graph", info: "tab.ifc-graph" },
              ]}
            />
          </div>
          <div className="ifc-view" ref={wrap} hidden={tab !== "3d"}>
            <Viewer3D
              ref={v3}
              url={st?.model_rev ? urls.revisionFile(st.model_rev.id) : null}
              rev={st?.model_rev?.id}
              info="viewer3d.model"
              styleOf={styleOf}
              selected={sel?.kind === "el" ? sel.id : null}
              onPick={(gid) => select(gid ? { kind: "el", id: gid } : null)}
              onLoaded={onLoaded}
              emptyText=" "
            >
              <div className="ifc-vtools">
                <span className="ifc-vtool">
                  <label className="sr-only" htmlFor="ifc-colour">
                    Colour elements by
                  </label>
                  <select id="ifc-colour" className="ifc-select" value={colorBy} onChange={(e) => setColorBy(e.target.value as ColorBy)}>
                    <option value="calc">Colour: by calc</option>
                    <option value="status">Colour: by match status</option>
                    <option value="cat">Colour: by element type</option>
                  </select>
                  <InfoTip id="tool.ifc-colour" />
                </span>
                <span className="ifc-vtool">
                  <label className="sr-only" htmlFor="ifc-level">
                    Level
                  </label>
                  <select
                    id="ifc-level"
                    className="ifc-select"
                    value={level}
                    onChange={(e) => {
                      setLevel(e.target.value);
                      requestAnimationFrame(() => requestAnimationFrame(() => v3.current?.fit()));
                    }}
                  >
                    <option value="">All levels</option>
                    {levels.map((l) => (
                      <option key={l}>{l}</option>
                    ))}
                  </select>
                  <InfoTip id="tool.ifc-level" />
                </span>
                <span className="ifc-vtool">
                  <button type="button" className={`btn${xray ? " on" : ""}`} aria-pressed={xray} onClick={() => setXray((x) => !x)}>
                    X-ray
                  </button>
                  <InfoTip id="tool.ifc-xray" />
                </span>
                <span className="ifc-vtool">
                  <button type="button" className="btn" onClick={() => v3.current?.fit()}>
                    Fit
                  </button>
                  <InfoTip id="tool.ifc-fit" />
                </span>
              </div>
              {ix && ix.els.size > 0 && (
                <div className="ifc-legend">
                  <Legend info="legend.ifc-colour" title="Colours" variant="overlay" items={legendItems} />
                </div>
              )}
              {tipEl && tip && ix && (
                <div className="ifc-tip" style={{ left: tip.x, top: tip.y }}>
                  <b>{elLabel(tipEl)}</b>{" "}
                  <span className="muted">
                    {tipEl.cat}
                    {tipEl.profile ? ` · ${tipEl.profile}` : ""}
                  </span>
                  <br />
                  {linksFor(ix, tipEl.global_id).length ? (
                    linksFor(ix, tipEl.global_id).map((l) => (
                      <div key={l.calc_key}>
                        {ix.calcs.get(l.calc_key)?.title} <span className="muted">{Math.round(l.conf * 100)}%</span>
                      </div>
                    ))
                  ) : (
                    <span style={{ color: "var(--bad)" }}>No calc found</span>
                  )}
                </div>
              )}
              {(busyText || (state.isSuccess && !(ix && ix.els.size))) && (
                <div className="ifc-overlay">
                  <div className="ifc-overlay-box">
                    <div className="ifc-overlay-h">Feed in a BIM model and a calc package</div>
                    <div className="muted">
                      The model becomes an element graph with load-path edges, the package is split into calcs, and every element is linked to the calcs that
                      cover it - with the evidence, a confidence you can confirm or reject, and the downstream calcs that go stale when something changes.
                    </div>
                    {!busyText && (
                      <div className="ifc-acts" style={{ justifyContent: "center", marginTop: 14 }}>
                        <button type="button" className="btn primary" onClick={loadSample}>
                          Load sample building
                        </button>
                      </div>
                    )}
                    {busyText && (
                      <div role="status" className="ifc-progress">
                        <div className="ifc-bar">
                          <i />
                        </div>
                        {busyText}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </Viewer3D>
          </div>
          {tab === "graph" && ix && (
            <div className="ifc-view graph">
              <LoadPathGraph ix={ix} sel={sel} impact={impact} onSelect={(s) => {setTab("3d");select(s,true);}} />
            </div>
          )}
        </section>

        <Inspector
          ix={ix}
          sel={sel}
          impact={impact}
          impactLoading={impactQ.isFetching}
          onSelect={select}
          onImpact={(gid, mode) => historical ? showError("Return to the latest model to run an impact check.") : setImpactReq({ gid, mode })}
          onClearImpact={() => setImpactReq(null)}
          onDecide={(...args)=>historical ? Promise.resolve(showError("Return to the latest model to edit links.")) : onDecide(...args)}
          onConfirmAll={ls=>historical ? Promise.resolve(showError("Return to the latest model to edit links.")) : onConfirmAll(ls)}
          onOpenPage={openPage}
          busy={busy}
        />
      </div>
      <p className="ifc-foot muted">
        Mapping is deterministic (marks, mark ranges, mark families, section sizes, element type) and every link shows the text it came from. Every upload is
        stored as a revision. Sample building and calc package are synthetic.
      </p>

      <dialog ref={reviewDialog} className="ifc-dlg ifc-review-dlg" aria-label="History and beam checks">
        <div className="ifc-dlg-head"><b>History &amp; beam checks</b><span className="spacer"/><button className="btn sm" onClick={()=>reviewDialog.current?.close()}>Back to model</button></div>
        <div className="ifc-dlg-body">{reviewOpen && <Review currentData={liveState.data} selected={sel} onPreview={setPreview} onSelect={s=>{select(s,true);reviewDialog.current?.close();}}/>}</div>
      </dialog>
      <dialog ref={dlg} className="ifc-dlg" onClose={() => setPage(null)} aria-label="Calc package page">
        <div className="ifc-dlg-head">
          <b>
            Page {page?.n} of {pageCount}
            {pageCalc ? ` · ${pageCalc.title}` : ""}
          </b>
          <span className="spacer" />
          <button type="button" className="btn sm" aria-label="Previous page" disabled={!page || page.n <= 1} onClick={() => page && openPage(page.n - 1)}>
            ‹
          </button>
          <button type="button" className="btn sm" aria-label="Next page" disabled={!page || page.n >= pageCount} onClick={() => page && openPage(page.n + 1)}>
            ›
          </button>
          <button type="button" className="btn sm" onClick={() => dlg.current?.close()}>
            Close
          </button>
        </div>
        <div className="ifc-dlg-body">
          {page && st?.calc_rev && (
            <PdfPage
              info="pdf.ifc-calc-page"
              source={{
                url: urls.revisionFile(st.calc_rev.id),
                page: page.n,
                rects: page.n === page.rectPage ? page.rects : [],
                label: pageCalc?.title ?? `Page ${page.n}`,
                sub: `Calc package ${st.calc_rev.source_name} (rev ${st.calc_rev.seq})${page.n === page.rectPage && page.rects.length ? " - the matched words are highlighted" : ""}`,
              }}
            />
          )}
        </div>
      </dialog>

      {err && (
        <div className="ifc-err" role="alert">
          {err}
        </div>
      )}
    </div>
  );
}
