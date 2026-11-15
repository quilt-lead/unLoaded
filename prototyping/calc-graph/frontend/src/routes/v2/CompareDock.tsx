import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { InfoTip } from "../../help/InfoTip";
import { PdfPage, type PdfPageHandle, type PdfSource } from "../../components/PdfPage";
import { urls } from "../../api/client";
import type { CalcRevision, RerunResult } from "./api";
import { fmtUc, recordSource, ucTone, type DesignIndex } from "./util";
import "./compare-dock.css";

type PageStyle = "package" | "handcalcs";
type Layout = "side" | "stack";

interface Props {
  result: RerunResult;
  rev: CalcRevision;
  style: PageStyle;
  idx: DesignIndex;
}

interface Change {
  label: string;
  was: string;
  now: string;
  tone?: "good" | "warn" | "bad" | "neutral";
}

const round2 = (v: number | null | undefined) => (v == null ? "-" : String(Math.round(v * 100) / 100));
const withUnit = (v: string, unit: string | undefined) => (v === "-" || !unit ? v : `${v} ${unit}`);

/** The values that moved, old next to new: what to look for on the two pages. */
function changesOf(r: RerunResult): Change[] {
  const unit = r.new?.unit ?? r.old?.unit;
  return [
    { label: "Size", was: r.size_old ?? "-", now: r.size_new ?? "-" },
    { label: "Demand", was: withUnit(round2(r.old?.demand), unit), now: withUnit(round2(r.new?.demand), unit) },
    { label: "Capacity", was: withUnit(round2(r.old?.capacity), unit), now: withUnit(round2(r.new?.capacity), unit) },
    { label: "UC", was: fmtUc(r.old?.uc), now: fmtUc(r.new?.uc), tone: ucTone(r.new?.uc) },
    { label: "Governs", was: r.old?.check ?? "-", now: r.new?.check ?? "-" },
  ];
}

function newPage(result: RerunResult, rev: CalcRevision, style: PageStyle): { src: PdfSource | null; hand: boolean } {
  const np = result.new_page;
  if (!np) return { src: null, hand: false };
  const rs = np.rerun_sheet;
  if (style === "handcalcs" && rs && rs.page != null && rev.files?.rerun_sheets_pdf) {
    return {
      hand: true,
      src: {
        url: urls.v2RevisionPdf(rev.rev_id, "rerun_sheets"),
        page: rs.page,
        rects: [rs.bbox],
        label: `${result.record} - re-run sheet ${rs.sheet ?? ""}`,
        sub: `rerun_sheets.pdf p.${rs.page}${rs.recomputed ? ` - math recomputed, ${rs.asserts ?? 0} values asserted against the re-run` : ""}`,
      },
    };
  }
  return {
    hand: false,
    src: {
      url: urls.v2RevisionPdf(rev.rev_id, "calc_revision"),
      page: np.page,
      rects: [np.bbox],
      label: `${result.record} - revised sheet ${np.sheet ?? ""}`,
      sub: `calc_revision.pdf p.${np.page} (${rev.rev_id})`,
    },
  };
}

/** A record that is a row of a wide table reads best with the old page above the new one, each at
 * the full width (the two rows line up); a tall block (a Mathcad check, a re-run math sheet) reads
 * best side by side. Stacked only when both records are wide rows. */
function isRow(src: PdfSource | null): boolean {
  const b = src?.rects?.[0];
  if (!b) return true;
  const w = b[2] - b[0], h = b[3] - b[1];
  return h > 0 && w / h > 3;
}
const layoutFor = (a: PdfSource | null, b: PdfSource | null): Layout => (isRow(a) && isRow(b) ? "stack" : "side");

/** Old vs new calc page of one re-run record: the changed values in one line on top, then the two
 * pages at the full width of the dock, side by side or stacked (picked from the shape of the record,
 * switchable; always stacked when the dock is narrow), each zoomed to the record. Full view opens the
 * same comparison over the whole window. */
export function CompareDock({ result, rev, style, idx }: Props) {
  const [expanded, setExpanded] = useState(false);
  const [chosen, setChosen] = useState<Layout | null>(null);
  const before = useRef<PdfPageHandle>(null);
  const after = useRef<PdfPageHandle>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const expandRef = useRef<HTMLButtonElement>(null);
  const left = recordSource(idx.rec.get(result.record), "original package");
  const { src: right, hand } = newPage(result, rev, style);
  const layout = chosen ?? layoutFor(left, right);
  const changes = changesOf(result);
  const moved = changes.filter((c) => c.was !== c.now).length;

  const collapse = () => {
    setExpanded(false);
    requestAnimationFrame(() => expandRef.current?.focus());
  };

  useEffect(() => {
    if (!expanded) return;
    closeRef.current?.focus();
    // the page behind the full view is out of reach (tab order, screen readers) while it is open
    const app = document.getElementById("root");
    app?.setAttribute("inert", "");
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") collapse();
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      app?.removeAttribute("inert");
    };
  }, [expanded]);
  const both = (fn: (h: PdfPageHandle) => void) => {
    if (before.current) fn(before.current);
    if (after.current) fn(after.current);
  };

  const body = (
    <div className={`v2-cd${expanded ? " expanded" : ""}`}>
      <div className="v2-cd-bar">
        <dl className="v2-cd-changes" aria-label={`${moved} of ${changes.length} values changed`}>
          {changes.map((c) => {
            const changed = c.was !== c.now;
            return (
              <div key={c.label} className={`v2-cd-change${changed ? " changed" : ""}`}>
                <dt>{c.label}</dt>
                <dd className="mono">
                  {changed ? (
                    <>
                      <del className="v2-cd-was" aria-label={`was ${c.was}`}>{c.was}</del>
                      <span className="v2-cd-arrow" aria-hidden="true">{"→"}</span>
                      <ins className={`v2-cd-now${c.tone ? ` tone-${c.tone}` : ""}`} aria-label={`now ${c.now}`}>{c.now}</ins>
                    </>
                  ) : (
                    <span className="v2-cd-same" title="Unchanged by the re-run">{c.now}</span>
                  )}
                </dd>
              </div>
            );
          })}
          {result.uc_current_size_new_layout != null && (
            <div className="v2-cd-change">
              <dt>UC at the old size, new layout</dt>
              <dd className={`mono tone-${ucTone(result.uc_current_size_new_layout)}`}>
                {fmtUc(result.uc_current_size_new_layout)}
                {result.ng_to_ok ? " - NG, OK after re-size" : ""}
              </dd>
            </div>
          )}
        </dl>
        <div className="v2-cd-tools" role="toolbar" aria-label="Both pages">
          <span className="v2-cd-seg" role="group" aria-label="Page layout">
            <button type="button" className={`btn sm${layout === "side" ? " on" : ""}`} aria-pressed={layout === "side"} onClick={() => setChosen("side")}>
              Side by side
            </button>
            <button type="button" className={`btn sm${layout === "stack" ? " on" : ""}`} aria-pressed={layout === "stack"} title="Old page above the new one, each at the full width" onClick={() => setChosen("stack")}>
              Stacked
            </button>
          </span>
          <button type="button" className="btn sm" title="Zoom both pages to the highlighted record" onClick={() => both((h) => h.zoomToHighlight())}>
            Both to record
          </button>
          <button type="button" className="btn sm" title="Show both whole pages" onClick={() => both((h) => h.fitPage())}>
            Both whole pages
          </button>
          {expanded ? (
            <button ref={closeRef} type="button" className="btn sm" onClick={collapse} title="Back to the docked view (Esc)">
              Close full view
            </button>
          ) : (
            <button ref={expandRef} type="button" className="btn sm" onClick={() => setExpanded(true)} title="Compare over the whole window">
              Full view
            </button>
          )}
        </div>
      </div>
      <div className={`v2-cd-pages ${layout}`}>
        <section className="v2-cd-page" aria-label="Before: original calc package">
          <header className="v2-cd-side">
            <span className="v2-cd-tag was">Before</span> original calc package
            <InfoTip id="evidence.rerun-compare" />
          </header>
          <PdfPage ref={before} source={left} info="pdf.page" emptyText="This record has no page in the original calc package." />
        </section>
        <section className="v2-cd-page" aria-label="After: our re-run">
          <header className="v2-cd-side">
            <span className="v2-cd-tag now">After</span> {hand ? "re-run sheet (rendered math)" : "revised sheet, new calc revision"}
          </header>
          <PdfPage ref={after} source={right} info="pdf.page" emptyText="The re-run wrote no page for this record." />
        </section>
      </div>
      <p className="v2-cd-note">Method: {result.method ?? rev.method ?? "calc-graph re-run"} - not ETABS</p>
    </div>
  );

  if (!expanded) return body;
  return createPortal(
    <div className="v2-cd-overlay" role="dialog" aria-modal="true" aria-label={`Re-run ${result.record}: old vs new calc page`}>
      <div className="v2-cd-overlay-head">
        <b>Re-run {result.record}: old vs new calc page</b>
        <span className="muted">{result.status}</span>
      </div>
      {body}
    </div>,
    document.body,
  );
}
