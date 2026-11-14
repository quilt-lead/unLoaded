import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { InfoTip } from "../../help/InfoTip";
import { Panel } from "../../components/Panel";
import { StatPill, StatRow } from "../../components/StatPill";
import { Tabs } from "../../components/Tabs";
import { Legend } from "../../components/Legend";
import { PdfPage, type PdfSource } from "../../components/PdfPage";
import { EvidenceCompare } from "../../components/EvidenceCompare";
import type { MemberStyle } from "../../components/Viewer3D";
import { urls } from "../../api/client";
import {
  useApply,
  useCalcRevision,
  useConstructionStatus,
  useHealthHeat,
  useMoveImpact,
  useRerun,
  useScenarios,
  type ApplyResult,
  type Band,
  type CalcRevision,
  type Move,
  type RerunResult,
} from "./api";
import { HealthMeter } from "./HealthMeter";
import { MoveViewer } from "./MoveViewer";
import { PlanView, bandOf } from "./PlanView";
import { StalePanel } from "./StalePanel";
import { RerunPanel } from "./RerunPanel";
import { ChangeOrderPanel } from "./ChangeOrderPanel";
import { RevisionPanel } from "./RevisionPanel";
import { EtabsPanel } from "./EtabsPanel";
import { MockLink, PlatformRecordDialog } from "./PlatformRecord";
import { BAND_COLOR, BAND_LABEL, BAND_TONE, UC_COLOR, colShort, fmtUc, fmtUsd, recordSource, ucTone, useDesignIndex } from "./util";

type SideTab = "health" | "calcs" | "rerun" | "co" | "revision" | "etabs";
type Dock =
  | { kind: "pdf"; src: PdfSource; title: string }
  | { kind: "compare"; result: RerunResult; rev: CalcRevision }
  | null;

const FADED: MemberStyle = { color: UC_COLOR.faded, opacity: 0.22 };

const errMsg = (e: unknown) => (e instanceof Error ? e.message : e ? String(e) : null);

export default function MovePage() {
  const { idx, isLoading, error } = useDesignIndex();
  const heat = useHealthHeat(2);
  const scenarios = useScenarios();
  const [mode, setMode] = useState<"heat" | "move">("move");
  const [bandMode, setBandMode] = useState<"design" | "construction">("design");
  const [view, setView] = useState<"3d" | "plan">("3d");
  const [selected, setSelected] = useState<string | null>(null);
  const [draft, setDraft] = useState({ dx: 0, dy: 0 });
  const [remove, setRemove] = useState(false);
  const [step, setStep] = useState(1);
  const [committed, setCommitted] = useState<Move | null>(null);
  const [tab, setTab] = useState<SideTab>("health");
  const [dock, setDock] = useState<Dock>(null);
  const [newStyle, setNewStyle] = useState<"package" | "handcalcs">("package");
  const [activeRecord, setActiveRecord] = useState<string | null>(null);
  const [rerunRev, setRerunRev] = useState<CalcRevision | undefined>(undefined);
  const [loadRev, setLoadRev] = useState<string | null>(null);
  const [applied, setApplied] = useState<ApplyResult | null>(null);
  const [viewRev, setViewRev] = useState<number | null>(null);
  const [mock, setMock] = useState<string | null>(null);

  const impactQ = useMoveImpact(committed);
  const impact = committed && impactQ.data && impactQ.data.column === committed.column ? impactQ.data : undefined;
  const rerun = useRerun();
  const apply = useApply();
  const loaded = useCalcRevision(loadRev);
  useEffect(() => {
    if (loaded.data) setRerunRev(loaded.data);
  }, [loaded.data]);
  const cstat = useConstructionStatus(selected);

  const pendingDraft = !!selected && (remove !== (committed?.remove ?? false) || draft.dx !== (committed?.dx ?? 0) || draft.dy !== (committed?.dy ?? 0) || committed?.column !== selected);

  const select = useCallback(
    (col: string | null) => {
      setSelected(col);
      setDraft({ dx: 0, dy: 0 });
      setRemove(false);
      setCommitted(col ? { column: col, dx: 0, dy: 0, remove: false } : null);
      setActiveRecord(null);
    },
    [],
  );
  const commit = useCallback(
    (dx: number, dy: number, rm = remove) => {
      if (!selected) return;
      setDraft({ dx, dy });
      setCommitted({ column: selected, dx, dy, remove: rm });
      if (rm || dx || dy) setTab((t) => (t === "health" || t === "revision" || t === "etabs" ? t : t));
    },
    [selected, remove],
  );

  // stale elements = elements of the stale records (coloured "to recheck" when no estimate)
  const staleEls = useMemo(() => {
    const s = new Set<string>();
    if (!impact || !idx) return s;
    for (const it of impact.stale) for (const e of idx.rec.get(it.record)?.elements ?? []) s.add(e);
    return s;
  }, [impact, idx]);

  const styleOf = useCallback(
    (gid: string): MemberStyle | undefined => {
      const e = idx?.byGid.get(gid);
      if (!e) return FADED;
      if (mode === "move" && impact) {
        if (e.id === impact.column) return { color: impact.remove ? UC_COLOR.over : UC_COLOR.moved, opacity: impact.remove ? 0.35 : 0.5 };
        const est = impact.estimates[e.id];
        if (est) return { color: fmtColor(est.uc_new), opacity: 1 };
        if (staleEls.has(e.id)) return { color: UC_COLOR.stale, opacity: 0.85 };
        return { color: UC_COLOR.faded, opacity: 0.14 };
      }
      if (e.type === "column") {
        const b = bandOf(heat.data?.[e.id], bandMode);
        return b ? { color: BAND_COLOR[b], opacity: 1 } : undefined;
      }
      return FADED;
    },
    [idx, mode, impact, staleEls, heat.data, bandMode],
  );

  const openRecord = useCallback(
    (rid: string) => {
      const r = idx?.rec.get(rid);
      setActiveRecord(rid);
      const src = recordSource(r, "highlighted row = the record to redo");
      if (src) setDock({ kind: "pdf", src, title: `Calc record ${rid}` });
    },
    [idx],
  );

  const doRerun = useCallback(
    (records?: string[]) => {
      if (!committed) return;
      setTab("rerun");
      rerun.mutate(
        { move: committed, records },
        {
          onSuccess: (rev) => {
            setRerunRev(rev);
            setLoadRev(null);
            const first = rev.results?.find((r) => r.ng_to_ok || (r.size_new && r.size_new !== r.size_old)) ?? rev.results?.[0];
            if (first) setDock({ kind: "compare", result: first, rev });
          },
        },
      );
    },
    [committed, rerun],
  );

  if (isLoading) return <div className="page muted">Loading the synthetic v2 design...</div>;
  if (error || !idx) return <div className="page v2-error">Could not load /api/v2/design: {errMsg(error)}. Run the v2 generator and the server.</div>;

  const h = impact?.health ?? (selected ? heat.data?.[selected] : undefined);
  const co = impact?.change_order;
  const selGid = selected ? idx.el.get(selected)?.global_id ?? null : null;
  const hasMove = !!committed && (committed.remove || committed.dx !== 0 || committed.dy !== 0);
  const ifcUrl = viewRev != null ? urls.revisionFile(viewRev) : urls.v2ModelIfc();

  const tabs = [
    { id: "health" as const, label: "Health", info: "tab.move-health" as const },
    { id: "calcs" as const, label: "Calcs to redo", info: "tab.move-calcs" as const, badge: impact ? impact.stale.length : undefined, disabled: !impact },
    { id: "rerun" as const, label: "Re-run", info: "tab.move-rerun" as const, badge: rerunRev?.summary.records },
    { id: "co" as const, label: "Change order", info: "tab.move-co" as const, disabled: !co },
    { id: "revision" as const, label: "Revisions", info: "tab.move-revision" as const },
    { id: "etabs" as const, label: "ETABS", info: "tab.move-etabs" as const },
  ];

  const heatLegend = [
    { label: BAND_LABEL.easy, color: BAND_COLOR.easy, info: "legend.band-easy" as const },
    { label: BAND_LABEL.moderate, color: BAND_COLOR.moderate, info: "legend.band-moderate" as const },
    { label: BAND_LABEL.hard, color: BAND_COLOR.hard, info: "legend.band-hard" as const },
    { label: BAND_LABEL["do-not-move"], color: BAND_COLOR["do-not-move"], info: "legend.band-dnm" as const },
  ];
  const ucLegend = [
    { label: "UC up to 0.90", color: UC_COLOR.ok, info: "legend.uc-ok" as const },
    { label: "0.90 to 1.00", color: UC_COLOR.near, info: "legend.uc-near" as const },
    { label: "Over 1.00", color: UC_COLOR.over, info: "legend.uc-over" as const },
    { label: "Recheck (no estimate)", color: UC_COLOR.stale, info: "legend.uc-stale" as const },
    { label: "Moved column / ghost", color: UC_COLOR.moved, info: "legend.uc-moved" as const },
  ];
  const showUc = mode === "move" && !!impact;

  return (
    <div className="v2-page v2-move">
      <div className="v2-head">
        <h1 className="v2-title">
          Move a column <InfoTip id="page.v2-move" />
        </h1>
        <span className="v2-synth">
          {idx.building.name} <InfoTip id="stat.v2-synthetic" />
        </span>
        <span className="spacer" />
        <Link className="btn sm" to="/v2/etabs">
          ETABS
        </Link>
        {selected && (
          <Link className="btn sm" to={`/v2/element/${encodeURIComponent(selected)}`}>
            {selected} in the registry
          </Link>
        )}
      </div>

      <div className="v2-controls" role="group" aria-label="Move controls">
        <span className="v2-seg" role="group" aria-label="Mode">
          <button type="button" className={`btn sm${mode === "heat" ? " on" : ""}`} onClick={() => setMode("heat")} aria-pressed={mode === "heat"}>
            Heat view
          </button>
          <button type="button" className={`btn sm${mode === "move" ? " on" : ""}`} onClick={() => setMode("move")} aria-pressed={mode === "move"}>
            Move mode
          </button>
          <InfoTip id="panel.move-mode" />
        </span>
        <span className="v2-seg" role="group" aria-label="Health basis">
          <button type="button" className={`btn sm${bandMode === "design" ? " on" : ""}`} onClick={() => setBandMode("design")} aria-pressed={bandMode === "design"}>
            Design
          </button>
          <button
            type="button"
            className={`btn sm${bandMode === "construction" ? " on" : ""}`}
            onClick={() => setBandMode("construction")}
            aria-pressed={bandMode === "construction"}
          >
            + construction status
          </button>
          <InfoTip id="panel.move-band-basis" />
        </span>
        <label className="v2-field">
          Column
          <select value={selected ?? ""} onChange={(e) => select(e.target.value || null)} aria-label="Column to move">
            <option value="">pick or click one</option>
            {idx.columns.map((c) => (
              <option key={c.id} value={c.id}>
                {c.id} {c.size} {c.sfrs ? "(lateral)" : ""}
              </option>
            ))}
          </select>
        </label>
        {mode === "move" && (
          <>
            <label className="v2-field">
              dx
              <input type="number" step={step} value={draft.dx} disabled={!selected || remove} onChange={(e) => setDraft((d) => ({ ...d, dx: Number(e.target.value) }))} aria-label="Offset in x, ft" />
            </label>
            <label className="v2-field">
              dy
              <input type="number" step={step} value={draft.dy} disabled={!selected || remove} onChange={(e) => setDraft((d) => ({ ...d, dy: Number(e.target.value) }))} aria-label="Offset in y, ft" />
            </label>
            <label className="v2-field">
              snap
              <select value={step} onChange={(e) => setStep(Number(e.target.value))} aria-label="Grid snap, ft">
                {[0.5, 1, 2, 2.5, 5].map((s) => (
                  <option key={s} value={s}>
                    {s} ft
                  </option>
                ))}
              </select>
            </label>
            <label className="v2-check">
              <input type="checkbox" checked={remove} disabled={!selected} onChange={(e) => setRemove(e.target.checked)} /> Remove
            </label>
            <button type="button" className="btn sm primary" disabled={!selected || !pendingDraft} onClick={() => commit(draft.dx, draft.dy, remove)} data-testid="check-impact">
              Check impact
            </button>
            <button type="button" className="btn sm" disabled={!selected} onClick={() => select(selected)}>
              Reset
            </button>
            <InfoTip id="panel.move-offsets" />
            {scenarios.data && (
              <label className="v2-field">
                Try
                <select
                  value=""
                  onChange={(e) => {
                    const s = scenarios.data!.find((x) => x.id === e.target.value);
                    if (!s) return;
                    const col = s.column.startsWith("COL-") ? s.column : `COL-${s.column}`;
                    setSelected(col);
                    const rm = s.kind === "remove";
                    setRemove(rm);
                    setDraft({ dx: s.dx, dy: s.dy });
                    setCommitted({ column: col, dx: s.dx, dy: s.dy, remove: rm });
                  }}
                  aria-label="Load a scenario from the answer key"
                >
                  <option value="">a scenario...</option>
                  {scenarios.data.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.label}
                    </option>
                  ))}
                </select>
                <InfoTip id="panel.move-scenarios" />
              </label>
            )}
          </>
        )}
      </div>

      <StatRow>
        {h && (
          <>
            <StatPill label="Design" value={BAND_LABEL[h.band]} info="stat.move-health-design" tone={BAND_TONE[h.band]} />
            {h.band_construction && (
              <StatPill label="With construction" value={BAND_LABEL[h.band_construction as Band]} info="stat.move-health-construction" tone={BAND_TONE[h.band_construction as Band]} />
            )}
          </>
        )}
        {impact && (
          <>
            <StatPill label="Calcs to redo" value={impact.stale.length} info="stat.move-stale" tone="calc" />
            <StatPill label="Worst UC (est.)" value={fmtUc(impact.health.worst_uc)} info="stat.move-worst-uc" tone={ucTone(impact.health.worst_uc)} />
            <StatPill label="Sheets" value={impact.health.sheets?.length ?? 0} info="stat.move-sheets" />
            {co?.summary && <StatPill label="Cost est." value={fmtUsd(co.summary.total_cost.value)} info="stat.co-cost" tone="warn" />}
          </>
        )}
        {impactQ.isFetching && <span className="muted v2-small">Estimating impact...</span>}
        {impactQ.error && <span className="v2-error v2-small">{errMsg(impactQ.error)}</span>}
        {!selected && <span className="muted v2-small">Click a column in the 3D model or the plan to start.</span>}
        {selected && mode === "move" && !hasMove && !pendingDraft && <span className="muted v2-small">Drag the blue ghost (3D) or the column (plan), or type offsets.</span>}
      </StatRow>

      <div className="v2-work">
        <div className="v2-stage">
          <div className="v2-stage-bar">
            <Tabs
              items={[
                { id: "3d", label: "3D", info: "tab.move-3d" },
                { id: "plan", label: "Plan", info: "tab.move-plan" },
              ]}
              value={view}
              onChange={(v) => setView(v as "3d" | "plan")}
              info="tab.move-views"
              label="Model views"
              size="sm"
            />
            {viewRev != null && (
              <span className="v2-chip accent">
                showing revision {viewRev}{" "}
                <button type="button" className="v2-x-btn" onClick={() => setViewRev(null)} aria-label="Back to the base design">
                  x
                </button>
              </span>
            )}
          </div>
          <div className="v2-stage-body">
            {view === "3d" ? (
              <MoveViewer
                idx={idx}
                url={ifcUrl}
                rev={viewRev ?? "base"}
                styleOf={styleOf}
                selectedGid={selGid}
                onPick={(gid) => {
                  const e = gid ? idx.byGid.get(gid) : null;
                  if (e?.type === "column") select(e.id);
                  else if (e && mode === "move" && impact) setActiveRecord(null);
                }}
                moveMode={mode === "move"}
                selected={selected}
                dx={draft.dx}
                dy={draft.dy}
                remove={remove}
                step={step}
                impact={impact}
                onDrag={(dx, dy) => setDraft({ dx, dy })}
                onDrop={(dx, dy) => commit(dx, dy)}
              >
                {showUc ? (
                  <Legend variant="overlay" title="Estimated UC" info="legend.move-uc" items={ucLegend} />
                ) : (
                  <Legend variant="overlay" title="How hard to move" info="legend.move-heat" items={heatLegend} />
                )}
              </MoveViewer>
            ) : (
              <div className="v2-plan-wrap">
                <PlanView
                  idx={idx}
                  heat={heat.data}
                  bandMode={bandMode}
                  selected={selected}
                  dx={draft.dx}
                  dy={draft.dy}
                  remove={remove}
                  step={step}
                  impact={mode === "move" ? impact : undefined}
                  moveMode={mode === "move"}
                  onSelect={(c) => (c !== selected ? select(c) : undefined)}
                  onDrag={(dx, dy) => setDraft({ dx, dy })}
                  onDrop={(dx, dy) => commit(dx, dy)}
                />
                {showUc ? <Legend title="Estimated UC" info="legend.move-uc" items={ucLegend} /> : <Legend title="How hard to move" info="legend.move-heat" items={heatLegend} />}
              </div>
            )}
            {dock && (
              <div className={`v2-dock${dock.kind === "compare" ? " tall" : ""}`} role="region" aria-label="Source document">
                <div className="v2-dock-head">
                  <b>{dock.kind === "pdf" ? dock.title : `Re-run ${dock.result.record}: old vs new calc page`}</b>
                  {dock.kind === "compare" && (
                    <span className="v2-seg">
                      <button type="button" className={`btn sm${newStyle === "package" ? " on" : ""}`} onClick={() => setNewStyle("package")}>
                        Package style
                      </button>
                      <button
                        type="button"
                        className={`btn sm${newStyle === "handcalcs" ? " on" : ""}`}
                        disabled={!dock.result.new_page?.rerun_sheet || !dock.rev.files?.rerun_sheets_pdf}
                        onClick={() => setNewStyle("handcalcs")}
                      >
                        Re-run sheet (math)
                      </button>
                      <InfoTip id="panel.rerun-page-style" />
                    </span>
                  )}
                  <span className="spacer" />
                  <button type="button" className="btn sm" onClick={() => setDock(null)}>
                    Close
                  </button>
                </div>
                <div className="v2-dock-body">
                  {dock.kind === "pdf" ? (
                    <PdfPage key={`${dock.src.url}-${dock.src.page}-${dock.title}`} source={dock.src} info="pdf.page" />
                  ) : (
                    <CompareDock result={dock.result} rev={dock.rev} style={newStyle} idx={idx} />
                  )}
                </div>
              </div>
            )}
          </div>
        </div>

        <Panel
          title="Impact"
          info="panel.move-side"
          className="v2-side"
          actions={
            <Tabs items={tabs} value={tab} onChange={(t) => setTab(t as SideTab)} info="tab.move-side" label="Impact views" size="sm" />
          }
        >
          {tab === "health" && (
            <div>
              {selected && h ? (
                <>
                  <HealthMeter health={h} title={`${selected}${impact ? ` - ${impact.remove ? "remove" : `move (${committed?.dx}, ${committed?.dy}) ft`}` : ` - probe move of +/- ${h.probe?.[0] ? Math.abs(h.probe[0]) : 2} ft`}`} />
                  {cstat.data && (
                    <div className="v2-cstat">
                      <h3 className="v2-h3">
                        Construction status <span className="v2-mock">mock</span> <InfoTip id="panel.move-construction" />
                      </h3>
                      <p className="v2-small">
                        Stage <b>{cstat.data.stage}</b>
                        {cstat.data.float_days != null && <> - float {cstat.data.float_days} working days</>}
                      </p>
                      <ul className="v2-list">
                        {cstat.data.submittals.map((s) => (
                          <li key={s.ref}>
                            <span className="mono">{s.number}</span> {s.title} <span className="v2-chip">{s.status}</span> <MockLink url={s.link} onOpen={setMock} />
                          </li>
                        ))}
                        {cstat.data.open_rfis.map((s) => (
                          <li key={s.ref}>
                            <span className="mono">{s.number}</span> {s.title} <span className="v2-chip tone-warn">{s.status}</span> <MockLink url={s.link} onOpen={setMock} />
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </>
              ) : (
                <p className="muted">Pick a column to see how hard it is to move and why. The list below is the heat view for every column.</p>
              )}
              <h3 className="v2-h3">
                Every column <InfoTip id="panel.move-heat-list" />
              </h3>
              <HeatList heat={heat.data} bandMode={bandMode} selected={selected} onSelect={select} />
            </div>
          )}
          {tab === "calcs" && impact && (
            <StalePanel idx={idx} impact={impact} openRecord={openRecord} activeRecord={activeRecord} onRerun={doRerun} rerunBusy={rerun.isPending} />
          )}
          {tab === "rerun" && (
            <RerunPanel
              rev={rerunRev}
              busy={rerun.isPending || loaded.isFetching}
              error={errMsg(rerun.error)}
              selected={dock?.kind === "compare" ? dock.result.record : null}
              onSelect={(r) => rerunRev && setDock({ kind: "compare", result: r, rev: rerunRev })}
              onLoadRev={setLoadRev}
            />
          )}
          {tab === "co" && co && (
            <ChangeOrderPanel idx={idx} co={co} openPdf={(src) => setDock({ kind: "pdf", src, title: String(src.label ?? "Document") })} openMock={setMock} showCalcs={() => setTab("calcs")} />
          )}
          {tab === "revision" && (
            <RevisionPanel
              move={committed}
              applying={apply.isPending}
              applyError={errMsg(apply.error)}
              applied={applied}
              onApply={(label) => committed && apply.mutate({ move: committed, label }, { onSuccess: setApplied })}
              viewRev={viewRev}
              onViewRev={setViewRev}
            />
          )}
          {tab === "etabs" && <EtabsPanel move={committed} />}
        </Panel>
      </div>
      {mock && <PlatformRecordDialog url={mock} onClose={() => setMock(null)} />}
    </div>
  );
}

const fmtColor = (uc: number | null | undefined) => (uc == null ? UC_COLOR.stale : uc > 1 ? UC_COLOR.over : uc > 0.9 ? UC_COLOR.near : UC_COLOR.ok);

function HeatList({
  heat,
  bandMode,
  selected,
  onSelect,
}: {
  heat: Record<string, import("./api").Health> | undefined;
  bandMode: "design" | "construction";
  selected: string | null;
  onSelect: (c: string) => void;
}) {
  if (!heat) return <p className="muted">Computing the heat view: a 2 ft probe move for every column. This takes a minute or two right after the server starts, then it is cached.</p>;
  const rows = Object.entries(heat).sort((a, b) => {
    const sa = bandMode === "construction" ? a[1].score_construction ?? a[1].score : a[1].score;
    const sb = bandMode === "construction" ? b[1].score_construction ?? b[1].score : b[1].score;
    return sb - sa || a[0].localeCompare(b[0]);
  });
  return (
    <ul className="v2-heat">
      {rows.map(([c, hh]) => {
        const band = bandOf(hh, bandMode)!;
        const top = hh.reasons.find((r) => (bandMode === "design" ? r.factor !== "construction status" : true));
        return (
          <li key={c}>
            <button type="button" className={`v2-heat-row${selected === c ? " on" : ""}`} onClick={() => onSelect(c)}>
              <i className="v2-dot" style={{ background: BAND_COLOR[band] }} />
              <span className="mono">{colShort(c)}</span>
              <span className="v2-heat-band" style={{ color: BAND_COLOR[band] }}>
                {BAND_LABEL[band]}
              </span>
              <span className="mono muted">{bandMode === "construction" ? hh.score_construction ?? hh.score : hh.score}</span>
              <span className="v2-heat-why">{top?.reason}</span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}

function CompareDock({ result, rev, style, idx }: { result: RerunResult; rev: CalcRevision; style: "package" | "handcalcs"; idx: NonNullable<ReturnType<typeof useDesignIndex>["idx"]> }) {
  const r = idx.rec.get(result.record);
  const left = recordSource(r, "original package");
  const np = result.new_page;
  const useHand = style === "handcalcs" && np?.rerun_sheet && rev.files?.rerun_sheets_pdf;
  const right: PdfSource | null = np
    ? useHand
      ? {
          url: urls.v2RevisionPdf(rev.rev_id, "rerun_sheets"),
          page: np.rerun_sheet!.page,
          rects: [np.rerun_sheet!.bbox],
          label: `${result.record} - re-run sheet ${np.rerun_sheet!.sheet ?? ""}`,
          sub: `rerun_sheets.pdf p.${np.rerun_sheet!.page}${np.rerun_sheet!.recomputed ? ` - math recomputed, ${np.rerun_sheet!.asserts ?? 0} values asserted against the re-run` : ""}`,
        }
      : {
          url: urls.v2RevisionPdf(rev.rev_id, "calc_revision"),
          page: np.page,
          rects: [np.bbox],
          label: `${result.record} - revised sheet ${np.sheet ?? ""}`,
          sub: `calc_revision.pdf p.${np.page} (${rev.rev_id})`,
        }
    : null;
  const rows: [string, string, string][] = [
    ["Size", result.size_old ?? "-", result.size_new ?? "-"],
    ["Demand", `${result.old?.demand ?? "-"} ${result.old?.unit ?? ""}`, `${result.new?.demand != null ? Math.round(result.new.demand * 100) / 100 : "-"} ${result.new?.unit ?? ""}`],
    ["Capacity", `${result.old?.capacity ?? "-"}`, `${result.new?.capacity != null ? Math.round(result.new.capacity * 100) / 100 : "-"}`],
    ["UC", fmtUc(result.old?.uc), fmtUc(result.new?.uc)],
    ["Governs", result.old?.check ?? "-", result.new?.check ?? "-"],
  ];
  return (
    <div className="v2-cmp">
      <table className="v2-table v2-cmp-table">
        <thead>
          <tr>
            <th />
            <th>Before</th>
            <th>After (our re-run)</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([k, a, b]) => (
            <tr key={k}>
              <td>{k}</td>
              <td className="mono">{a}</td>
              <td className="mono">
                <b>{b}</b>
              </td>
            </tr>
          ))}
          {result.uc_current_size_new_layout != null && (
            <tr>
              <td>UC at current size, new layout</td>
              <td colSpan={2} className={`mono tone-${ucTone(result.uc_current_size_new_layout)}`}>
                {fmtUc(result.uc_current_size_new_layout)} {result.ng_to_ok ? "(NG at the old size -> OK after re-size)" : ""}
              </td>
            </tr>
          )}
        </tbody>
      </table>
      <div className="v2-cmp-pages">
        <EvidenceCompare
          left={left}
          right={right}
          leftTitle="Before - original calc package"
          rightTitle={useHand ? "After - re-run sheet (rendered math)" : "After - revised sheet, new calc revision"}
          info="evidence.rerun-compare"
          pageInfo="pdf.page"
          note={`Method: ${result.method ?? rev.method ?? "calc-graph re-run"} - not ETABS`}
        />
      </div>
    </div>
  );
}
