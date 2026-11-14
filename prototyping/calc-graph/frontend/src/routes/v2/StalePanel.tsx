import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { InfoTip } from "../../help/InfoTip";
import { StatPill, StatRow } from "../../components/StatPill";
import type { Impact, StaleItem } from "./api";
import { fmtUc, ucTone, type DesignIndex } from "./util";

export interface StalePanelProps {
  idx: DesignIndex;
  impact: Impact;
  openRecord: (rid: string) => void;
  activeRecord: string | null;
  onRerun: (records?: string[]) => void;
  rerunBusy: boolean;
}

const elHref = (id: string) => `/v2/element/${encodeURIComponent(id)}`;

/** Calc records to redo, grouped by calc, each with its reason chain; a row opens the record in the calc PDF. */
export function StalePanel({ idx, impact, openRecord, activeRecord, onRerun, rerunBusy }: StalePanelProps) {
  const [screenedOnly, setScreenedOnly] = useState(false);
  const [q, setQ] = useState("");
  const groups = useMemo(() => {
    const m = new Map<string, StaleItem[]>();
    for (const s of impact.stale) {
      if (screenedOnly && !s.screened) continue;
      if (q && !`${s.record} ${s.reasons.join(" ")} ${s.chain.join(" ")}`.toLowerCase().includes(q.toLowerCase())) continue;
      if (!m.has(s.calc)) m.set(s.calc, []);
      m.get(s.calc)!.push(s);
    }
    return [...m.entries()].sort((a, b) => a[0].localeCompare(b[0]));
  }, [impact, screenedOnly, q]);
  const screened = impact.stale.filter((s) => s.screened).length;
  const ests = Object.values(impact.estimates);
  const over = ests.filter((e) => (e.uc_new ?? 0) > 1).length;

  return (
    <div className="v2-stale">
      <StatRow>
        <StatPill label="To redo" value={impact.stale.length} info="stat.move-stale" tone="calc" />
        <StatPill
          label="Demand change > 5%"
          value={screened}
          info="stat.move-screened"
          tone="accent"
          onClick={() => setScreenedOnly((v) => !v)}
          active={screenedOnly}
          title="Show only records whose estimated demand changes by more than 5%"
        />
        <StatPill label="Over 1.0 (est.)" value={over} info="stat.move-over" tone={over ? "bad" : "good"} />
      </StatRow>
      <div className="v2-toolbar">
        <input className="v2-input" placeholder="Filter records, elements, reasons" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Filter calc records" />
        <button type="button" className="btn primary sm" disabled={rerunBusy} onClick={() => onRerun()} data-testid="rerun-all">
          {rerunBusy ? "Re-running..." : "Re-run all stale"}
        </button>
        <InfoTip id="panel.move-rerun-all" />
      </div>
      {impact.notes.length > 0 && (
        <ul className="v2-notes">
          {impact.notes.map((n, i) => (
            <li key={i}>{n}</li>
          ))}
        </ul>
      )}
      {groups.map(([calc, items]) => {
        const c = idx.calcTitle.get(calc);
        return (
          <section key={calc} className="v2-group">
            <h3 className="v2-group-head">
              <span className="mono">{calc}</span> {c?.title ?? ""} <span className="muted">{c?.software ? `- ${c.software}` : ""}</span>
              <span className="spacer" />
              <span className="cg-tab-badge">{items.length}</span>
            </h3>
            <ul className="v2-recs">
              {items.map((s) => {
                const r = idx.rec.get(s.record);
                const e = impact.estimates[r?.elements?.[0] ?? ""];
                return (
                  <li key={s.record} className={`v2-rec${activeRecord === s.record ? " on" : ""}`}>
                    <button type="button" className="v2-rec-main" onClick={() => openRecord(s.record)} title="Open this record's row in the calc package">
                      <span className="v2-rec-id mono">{s.record}</span>
                      <span className={`v2-chip ${s.screened ? "accent" : ""}`}>{s.screened ? "demand > 5%" : "topology"}</span>
                      {e?.uc_new != null && (
                        <span className={`v2-chip tone-${ucTone(e.uc_new)}`}>
                          UC {fmtUc(e.uc_old ?? r?.uc ?? null)} {"->"} {fmtUc(e.uc_new)} est.
                        </span>
                      )}
                      {e?.size_est && <span className="v2-chip tone-warn">{`${e.size} -> ${e.size_est}`}</span>}
                      {e?.next_typical && <span className="v2-chip tone-warn">{`next ${e.next_typical.replace("DETAIL:", "")}`}</span>}
                    </button>
                    <div className="v2-rec-why">{s.reasons.join("; ")}</div>
                    <div className="v2-chain" aria-label="Reason chain">
                      {s.chain.map((c, i) => (
                        <span key={i} className="v2-chain-step">
                          {i > 0 && <span className="v2-chain-arrow" aria-hidden="true">{"->"}</span>}
                          <Link to={elHref(c)} className="v2-chain-link mono">
                            {c}
                          </Link>
                        </span>
                      ))}
                      <span className="spacer" />
                      <button type="button" className="btn sm" disabled={rerunBusy} onClick={() => onRerun([s.record])}>
                        Re-run
                      </button>
                    </div>
                  </li>
                );
              })}
            </ul>
          </section>
        );
      })}
      {!groups.length && <p className="muted">No records match.</p>}
    </div>
  );
}
