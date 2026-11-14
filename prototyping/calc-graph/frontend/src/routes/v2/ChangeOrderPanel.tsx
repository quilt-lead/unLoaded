import { useState, type ReactNode } from "react";
import { InfoTip } from "../../help/InfoTip";
import type { HelpId } from "../../help/registry";
import { StatPill, StatRow } from "../../components/StatPill";
import { urls } from "../../api/client";
import type { PdfSource } from "../../components/PdfPage";
import type { ChangeOrder, CoItem, Figure } from "./api";
import { usePlatforms } from "./api";
import { MockLink, PlatformSourceBadge } from "./PlatformRecord";
import { fmtUsd, type DesignIndex } from "./util";

export interface ChangeOrderPanelProps {
  idx: DesignIndex;
  co: ChangeOrder;
  openPdf: (s: PdfSource) => void;
  openMock: (url: string) => void;
  showCalcs: () => void;
}

function Basis({ f }: { f: Figure }) {
  return <span className="v2-basis">{f.estimate ? "Estimate. " : ""}Basis: {f.basis}</span>;
}

function Section({ title, info, count, children }: { title: string; info: HelpId; count?: number; children: ReactNode }) {
  return (
    <section className="v2-co-sec">
      <h3 className="v2-h3">
        {title} {count != null && <span className="cg-tab-badge">{count}</span>}
        <InfoTip id={info} />
      </h3>
      {children}
    </section>
  );
}

function Status({ s }: { s?: string | null }) {
  if (!s) return null;
  const tone = ["erected", "delivered", "fabricated"].includes(s) ? "bad" : ["approved", "open", "submitted"].includes(s) ? "warn" : "";
  return <span className={`v2-chip ${tone ? `tone-${tone}` : ""}`}>{s}</span>;
}

function ItemRow({ it, openMock }: { it: CoItem; openMock: (u: string) => void }) {
  return (
    <li className="v2-co-item">
      <div>
        <span className="mono">{it.number ?? it.ref}</span> {it.title} <Status s={it.status} />
      </div>
      {it.action && <div className="v2-small">Action: {it.action}</div>}
      <div className="v2-co-links">
        {(it.sources?.length ? it.sources.map((s) => s.url) : it.link ? [it.link] : []).map((u) => (
          <MockLink key={u} url={u} onOpen={openMock} />
        ))}
      </div>
    </li>
  );
}

/** Potential change order: what a move would reopen on site and in the office, with cost and schedule estimates. */
export function ChangeOrderPanel({ idx, co, openPdf, openMock, showCalcs }: ChangeOrderPanelProps) {
  const [showRates, setShowRates] = useState(false);
  const ps = usePlatforms();
  const anyLive = !!ps.data?.some((p) => p.source === "live");
  const allLive = !!ps.data?.length && ps.data.every((p) => p.source === "live");
  if (co.error) return <p className="v2-error">Change order unavailable: {co.error}</p>;
  const s = co.summary;
  // the inserted work whose hold on an existing activity sets the new project finish
  const slipDrivers = (co.schedule?.activities ?? []).flatMap((a) =>
    (a.holds ?? []).filter((h) => h.drives_finish).map((h) => ({ via: a.ref, title: h.title, push: h.finish_push })),
  );
  const sheetPage = (n?: string) => idx.sheets.find((x) => x.sheet === n);
  return (
    <div className="v2-co">
      <p className="v2-mock-banner">
        <PlatformSourceBadge big />{" "}
        {allLive
          ? "Construction-platform records are read live from the platforms;"
          : anyLive
            ? "Some construction-platform records are live (hover the badge), the rest synthetic;"
            : "Construction-platform data (Procore, Autodesk Build) is synthetic;"}{" "}
        every cost and schedule figure is an estimate with its basis shown. <InfoTip id="panel.co-mock" />
      </p>
      {s && (
        <>
          <p className="v2-headline">{s.headline}</p>
          <StatRow>
            <StatPill label="Cost est." value={fmtUsd(s.total_cost.value)} info="stat.co-cost" tone="warn" />
            <StatPill label="Range" value={`${fmtUsd(s.cost_range.low.value)} to ${fmtUsd(s.cost_range.high.value)}`} info="stat.co-range" />
            <StatPill label="Forecast slip" value={`${s.forecast_slip.value} wd`} info="stat.co-slip" tone={s.forecast_slip.value ? "warn" : "good"} />
            <StatPill label="Past contract" value={`${s.finish_delay.value} wd`} info="stat.co-delay" tone={s.finish_delay.value ? "bad" : "good"} />
            <StatPill label="Float used" value={`${s.float_consumed.value} wd`} info="stat.co-float" />
          </StatRow>
          <ul className="v2-basis-list">
            <li>
              Cost: <Basis f={s.total_cost} />
            </li>
            <li>
              Range: <Basis f={s.cost_range.low} /> / <Basis f={s.cost_range.high} />
            </li>
            <li>
              Slip: <Basis f={s.forecast_slip} />
              {slipDrivers.length > 0 && (
                <>
                  {" "}
                  - driven by {slipDrivers.map((d) => `${d.via} holding '${d.title}' (+${d.push} wd)`).join("; ")}.
                </>
              )}
            </li>
            <li>
              Float: <Basis f={s.float_consumed} />
            </li>
          </ul>
        </>
      )}

      <Section title="Submittals to resubmit" info="panel.co-submittals" count={co.submittals?.length}>
        <ul className="v2-co-list">
          {co.submittals?.map((it) => (
            <ItemRow key={it.ref} it={it} openMock={openMock} />
          ))}
        </ul>
      </Section>

      <Section title="RFIs to reopen or answer" info="panel.co-rfis" count={co.rfis?.length}>
        <ul className="v2-co-list">
          {co.rfis?.map((it) => (
            <ItemRow key={it.ref} it={it} openMock={openMock} />
          ))}
        </ul>
      </Section>

      <Section title="Sheets to revise" info="panel.co-sheets" count={co.sheets?.length}>
        <ul className="v2-co-list">
          {co.sheets?.map((it) => {
            const sp = sheetPage(it.number);
            const rects = idx.occurrences
              .filter((o) => o.doc === "drawings" && o.sheet === it.number && o.bbox && it.element_ids?.includes(o.ref))
              .map((o) => o.bbox!);
            return (
              <li key={it.number} className="v2-co-item">
                <div>
                  <span className="mono">{it.number}</span> {it.title ?? sp?.title ?? ""}
                </div>
                <div className="v2-co-links">
                  {sp && (
                    <button
                      type="button"
                      className="btn sm"
                      onClick={() =>
                        openPdf({
                          url: urls.v2DocFile("drawings"),
                          page: sp.page,
                          rects,
                          focus: rects.length ? undefined : null,
                          label: `Sheet ${it.number} - ${sp.title}`,
                          sub: rects.length ? `${rects.length} affected tag(s) highlighted` : "Whole sheet",
                        })
                      }
                    >
                      Open sheet
                    </button>
                  )}
                  {(it.sources ?? []).map((src) => (
                    <MockLink key={src.url} url={src.url} onOpen={openMock} />
                  ))}
                </div>
              </li>
            );
          })}
        </ul>
      </Section>

      <Section title="Spec articles" info="panel.co-specs" count={co.spec_articles?.length}>
        <ul className="v2-co-list">
          {co.spec_articles?.map((a) => {
            const sa = idx.specArticles.get(a.article);
            return (
              <li key={a.article} className="v2-co-item">
                <div>
                  <span className="mono">{a.article.replace("SPEC:", "")}</span> {sa ? `${sa.section_title ?? ""} - ${sa.title}` : ""}
                </div>
                {sa && (
                  <div className="v2-co-links">
                    <button
                      type="button"
                      className="btn sm"
                      onClick={() =>
                        openPdf({ url: urls.v2DocFile("specs"), page: sa.page, rects: [sa.bbox], label: a.article.replace("SPEC:", ""), sub: sa.text.slice(0, 140) })
                      }
                    >
                      Open article
                    </button>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      </Section>

      <Section title="Calc records" info="panel.co-records" count={co.calc_records?.length}>
        <p className="v2-small">
          {co.calc_records?.length ?? 0} records whose estimated demand changes by more than 5% are priced as engineering redesign.{" "}
          <button type="button" className="btn sm" onClick={showCalcs}>
            See calcs to redo
          </button>
        </p>
      </Section>

      <Section title="Cost lines" info="panel.co-cost" count={co.cost?.lines.length}>
        <div className="v2-table-wrap">
          <table className="v2-table">
            <thead>
              <tr>
                <th>Category</th>
                <th>Item</th>
                <th className="num">Estimate</th>
                <th>
                  Basis <InfoTip id="table.co-basis" />
                </th>
              </tr>
            </thead>
            <tbody>
              {co.cost?.lines.map((l, i) => (
                <tr key={i}>
                  <td>{l.category.replace(/_/g, " ")}</td>
                  <td>
                    {l.description} {l.link && <MockLink url={l.link} onOpen={openMock} label="mock" />}
                  </td>
                  <td className="num mono">{fmtUsd(l.figure.value)}</td>
                  <td className="v2-basis">{l.figure.basis}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      <Section title="Schedule activities hit" info="panel.co-schedule" count={co.schedule?.activities.length}>
        <ul className="v2-co-list">
          {co.schedule?.activities.map((a) => (
            <li key={a.ref} className="v2-co-item">
              <div>
                <span className="mono">{a.ref}</span> {a.title} <span className="v2-chip tone-warn">+{a.added_days} d est.</span>
              </div>
              {a.inserted ? (
                <div className="v2-small">
                  Inserted work, {a.early_start} to {a.early_finish}
                  {a.holds && a.holds.length > 0 ? (
                    <>
                      ; must finish before{" "}
                      {a.holds.map((h, i) => (
                        <span key={h.ref}>
                          {i > 0 && ", "}
                          <span className="mono">{h.ref}</span> (finish {h.early_finish_before} {"->"} {h.early_finish_after}, float {h.float_before} {"->"} {h.float_after} d
                          {h.drives_finish ? <strong>, sets the project finish</strong> : null})
                        </span>
                      ))}
                    </>
                  ) : (
                    "; feeds the work after it"
                  )}
                </div>
              ) : (
                <div className="v2-small">
                  Finish {a.early_finish_before} {"->"} {a.early_finish_after}; {a.float_known === false ? "float not reported (assumed 0)" : <>float {a.float_before} {"->"} {a.float_after} d</>}
                </div>
              )}
              <details className="v2-small">
                <summary>{a.reasons.length} reasons</summary>
                <ul>
                  {a.reasons.map((r, i) => (
                    <li key={i}>{r}</li>
                  ))}
                </ul>
              </details>
              <div className="v2-co-links">
                <MockLink url={a.link} onOpen={openMock} />
              </div>
            </li>
          ))}
        </ul>
      </Section>

      {co.assumptions && (
        <Section title="Assumptions" info="panel.co-assumptions">
          <p className="v2-small">
            {co.assumptions.note} (as of {co.assumptions.as_of}){" "}
            <button type="button" className="btn sm" onClick={() => setShowRates((v) => !v)} aria-expanded={showRates}>
              {showRates ? "Hide" : "Show"} unit rates
            </button>
          </p>
          {showRates && <pre className="v2-pre">{JSON.stringify({ rates: co.assumptions.rates, schedule_rules: co.assumptions.schedule_rules }, null, 2)}</pre>}
        </Section>
      )}
    </div>
  );
}
