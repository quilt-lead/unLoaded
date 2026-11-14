// As-of date control + cost / slip vs approval date (backend/calcgraph/as_of.py).
// The control is part of the move setup, so it goes through the page history (undo / redo).
import { useState } from "react";
import { InfoTip } from "../../help/InfoTip";
import type { Move } from "./api";
import { asOfLabel, useAsOfInfo, useImpactTimeline, type Timeline } from "./asOf";
import { fmtUsd } from "./util";
import "./asof-inbox.css";

export function AsOfControl({ value, onChange }: { value: string; onChange: (v: string, label: string) => void }) {
  const info = useAsOfInfo();
  const custom = !info.data?.presets.some((p) => p.key === value);
  const [draft, setDraft] = useState(custom ? value : "");
  return (
    <div className="ai-asof" role="group" aria-label="Approval date for the impact">
      <span className="ai-asof-label">
        Approved on <InfoTip id="panel.asof-control" />
      </span>
      <span className="v2-seg">
        {(info.data?.presets ?? [{ key: "today", label: "Today", date: "" }]).map((p) => (
          <button
            key={p.key}
            type="button"
            className={`btn sm${value === p.key ? " on" : ""}`}
            aria-pressed={value === p.key}
            title={p.date}
            data-testid={`asof-${p.key}`}
            onClick={() => onChange(p.key, asOfLabel(p.key, info.data))}
          >
            {p.label}
          </button>
        ))}
      </span>
      <label className="v2-field">
        custom
        <input
          type="date"
          value={custom ? value : draft}
          min={info.data?.today}
          onChange={(e) => {
            setDraft(e.target.value);
            if (e.target.value) onChange(e.target.value, e.target.value);
          }}
          aria-label="Custom approval date"
          data-testid="asof-custom"
        />
      </label>
      {value !== "today" && <span className="ai-asof-note">projected; the every-column heat view stays at today</span>}
    </div>
  );
}

export function AsOfTimeline({ move, asOf, onPick }: { move: Move | null; asOf: string; onPick: (date: string) => void }) {
  const tl = useImpactTimeline(move, asOf);
  if (!move || (!move.remove && move.dx === 0 && move.dy === 0)) return null;
  if (tl.isLoading) return <p className="muted v2-small">Projecting cost and slip over approval dates...</p>;
  if (tl.error) return <p className="v2-error v2-small">{String(tl.error)}</p>;
  if (!tl.data) return null;
  return (
    <div className="ai-tl" data-testid="asof-timeline">
      <h3 className="v2-h3">
        Cost and slip vs approval date <InfoTip id="panel.asof-timeline" />
      </h3>
      {tl.data.approve_by_line ? (
        <p className="ai-approve" data-testid="approve-by">
          {tl.data.approve_by_line}
        </p>
      ) : (
        <p className="v2-small muted">No stage boundary in the next {tl.data.horizon_days} days makes this change worse.</p>
      )}
      <StepChart tl={tl.data} onPick={onPick} />
      <table className="v2-table ai-tl-table">
        <thead>
          <tr>
            <th>Approved on</th>
            <th>Cost est.</th>
            <th>Slip (wd)</th>
            <th>Past contract (wd)</th>
            <th>Worst stage</th>
          </tr>
        </thead>
        <tbody>
          {tl.data.points.map((p) => (
            <tr key={p.date} className={p.date === tl.data!.selected ? "on" : undefined}>
              <td>
                <button type="button" className="v2-link-btn" onClick={() => onPick(p.date)} title="Use this approval date">
                  {p.date}
                </button>{" "}
                <span className="muted v2-small">{p.labels.join(", ")}</span>
              </td>
              <td className="mono">{p.total_cost == null ? "-" : fmtUsd(p.total_cost)}</td>
              <td className="mono">{p.forecast_slip ?? "-"}</td>
              <td className="mono">{p.finish_delay ?? "-"}</td>
              <td>{p.worst_stage ?? "-"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="v2-small muted">{tl.data.assumption}</p>
    </div>
  );
}

/** step chart: cost (bars) and forecast slip (line) at each evaluated approval date */
function StepChart({ tl, onPick }: { tl: Timeline; onPick: (d: string) => void }) {
  const pts = tl.points.filter((p) => p.total_cost != null);
  if (pts.length < 2) return null;
  const W = 360, H = 150, L = 56, R = 34, T = 24, B = 24;
  const t0 = Date.parse(pts[0].date), t1 = Date.parse(pts[pts.length - 1].date);
  const x = (d: string) => L + ((Date.parse(d) - t0) / Math.max(t1 - t0, 1)) * (W - L - R);
  const costs = pts.map((p) => p.total_cost ?? 0);
  const cMax = Math.max(...costs, 1);
  const cMin = Math.min(...costs) * 0.95; // axis starts near the lowest cost so the steps are visible (labelled)
  const sMax = Math.max(...pts.map((p) => p.forecast_slip ?? 0), 1);
  const yc = (v: number) => H - B - ((v - cMin) / Math.max(cMax - cMin, 1)) * (H - T - B);
  const ys = (v: number) => H - B - (v / sMax) * (H - T - B);
  const step = (f: (p: (typeof pts)[number]) => number, y: (v: number) => number) =>
    pts.map((p, i) => (i ? `H${x(p.date).toFixed(1)} V${y(f(p)).toFixed(1)}` : `M${x(p.date).toFixed(1)} ${y(f(p)).toFixed(1)}`)).join(" ") + ` H${W - R}`;
  return (
    <svg className="ai-chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Cost and slip against approval date">
      <line x1={L} x2={W - R} y1={H - B} y2={H - B} className="ai-axis" />
      <text x={L - 4} y={yc(cMax) + 4} className="ai-tick" textAnchor="end">
        {fmtUsd(cMax)}
      </text>
      <text x={L - 4} y={H - B} className="ai-tick" textAnchor="end">
        {fmtUsd(cMin)}
      </text>
      <text x={W - R + 4} y={H - B} className="ai-tick ai-slip-t">
        0 wd
      </text>
      <text x={W - R + 4} y={ys(sMax) + 4} className="ai-tick ai-slip-t">
        {sMax} wd
      </text>
      <path d={step((p) => p.total_cost ?? 0, yc)} className="ai-cost" />
      <path d={step((p) => p.forecast_slip ?? 0, ys)} className="ai-slip" />
      {pts.map((p) => (
        <g key={p.date} onClick={() => onPick(p.date)} className="ai-pt">
          <circle cx={x(p.date)} cy={yc(p.total_cost ?? 0)} r={p.date === tl.selected ? 4.5 : 3} className={p.date === tl.selected ? "ai-dot on" : "ai-dot"}>
            <title>{`${p.date}: ${fmtUsd(p.total_cost ?? 0)}, slip ${p.forecast_slip} wd`}</title>
          </circle>
        </g>
      ))}
      <text x={L} y={H - 6} className="ai-tick">
        {pts[0].date}
      </text>
      <text x={W - R} y={H - 6} className="ai-tick" textAnchor="end">
        {pts[pts.length - 1].date}
      </text>
      <text x={L} y={11} className="ai-tick ai-cost-t">
        cost est. (solid)
      </text>
      <text x={L + 92} y={11} className="ai-tick ai-slip-t">
        forecast slip (dashed)
      </text>
    </svg>
  );
}
