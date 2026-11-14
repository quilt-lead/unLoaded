import { useMemo, useState } from "react";
import { InfoTip } from "../../help/InfoTip";
import { StatPill, StatRow } from "../../components/StatPill";
import type { CalcRevision, RerunResult } from "./api";
import { useRevisions } from "./api";
import { fmtUc, ucTone } from "./util";

export interface RerunPanelProps {
  rev: CalcRevision | undefined;
  busy: boolean;
  error: string | null;
  selected: string | null;
  onSelect: (r: RerunResult) => void;
  onLoadRev: (revId: string) => void;
}

const changeLabel = (c: CalcRevision["change"]) =>
  !c.removed?.length && !Object.keys(c.moved ?? {}).length
    ? "original calc package (no re-run)"
    : c.removed?.length
    ? `remove ${c.removed.join(", ")}`
    : Object.entries(c.moved ?? {})
        .map(([k, [x, y]]) => `move ${k} (${x >= 0 ? "+" : ""}${x}, ${y >= 0 ? "+" : ""}${y}) ft`)
        .join(", ");

function Status({ r }: { r: RerunResult }) {
  if (r.ng_to_ok) return <span className="v2-chip tone-good">NG {"->"} OK</span>;
  if (r.ok_new === false) return <span className="v2-chip tone-bad">still NG</span>;
  if (r.size_new && r.size_old && r.size_new !== r.size_old) return <span className="v2-chip tone-warn">re-sized</span>;
  return <span className="v2-chip">{r.status === "unchanged" ? "unchanged" : "new values"}</span>;
}

/** Re-run results: old vs new per record in load-path order; picking one shows the two calc pages side by side. */
export function RerunPanel({ rev, busy, error, selected, onSelect, onLoadRev }: RerunPanelProps) {
  const revs = useRevisions();
  const [onlyChanged, setOnlyChanged] = useState(true);
  const results = useMemo(
    () => (rev?.results ?? []).filter((r) => !onlyChanged || r.ng_to_ok || r.ok_new === false || (r.size_new && r.size_new !== r.size_old)),
    [rev, onlyChanged],
  );
  return (
    <div className="v2-rerun">
      {busy && (
        <p className="v2-busy" role="status">
          Re-running the design for these records (load-path order; the lateral system as one job)... this takes about 10 to 20 seconds for all stale records.
        </p>
      )}
      {error && (
        <p className="v2-error" role="alert">
          Re-run failed: {error}
        </p>
      )}
      {rev ? (
        <>
          <div className="v2-rev-head">
            <b className="mono">{rev.rev_id}</b> <span className="muted">{rev.created_at}</span>
            <span className="muted">- {changeLabel(rev.change)}</span>
          </div>
          {rev.restore && (
            <p className="v2-small v2-ok">
              {rev.restore.verb === "undo" ? "Undo" : "Redo"} of re-run {rev.restore.of}: restored {rev.restore.restored ?? "the original calc package"} as {rev.rev_id}{" "}
              (superseding {rev.restore.parent}). Nothing was deleted.
            </p>
          )}
          {rev.restore && !rev.restore.restored && <p className="muted">The calcs are back to the original package: this revision re-runs nothing.</p>}
          <StatRow>
            <StatPill label="Records re-run" value={rev.summary.records} info="stat.rerun-records" />
            <StatPill label="Re-sized" value={rev.summary.resized} info="stat.rerun-resized" tone={rev.summary.resized ? "warn" : "good"} />
            <StatPill label="NG to OK" value={rev.summary.ng_to_ok} info="stat.rerun-ng-ok" tone="good" />
            <StatPill label="Still NG" value={rev.summary.still_ng} info="stat.rerun-still-ng" tone={rev.summary.still_ng ? "bad" : "good"} />
          </StatRow>
          {!(rev.restore && !rev.restore.restored) && (
          <p className="v2-method">
            <span className="v2-label-real">Our re-run</span> {rev.method ?? "calc-graph re-run"}. <span className="muted">{rev.order_rule}</span>
            <InfoTip id="panel.rerun-method" />
          </p>
          )}
          <label className="v2-check">
            <input type="checkbox" checked={onlyChanged} onChange={(e) => setOnlyChanged(e.target.checked)} /> Only re-sized or NG records ({results.length})
          </label>
          <div className="v2-table-wrap">
            <table className="v2-table">
              <thead>
                <tr>
                  <th>
                    Step <InfoTip id="table.rerun-step" />
                  </th>
                  <th>Record</th>
                  <th>
                    Job <InfoTip id="table.rerun-job" />
                  </th>
                  <th>
                    UC old {"->"} new <InfoTip id="table.rerun-uc" />
                  </th>
                  <th>Size</th>
                  <th>Result</th>
                </tr>
              </thead>
              <tbody>
                {results.map((r) => (
                  <tr key={r.record} className={selected === r.record ? "on" : undefined} onClick={() => onSelect(r)} tabIndex={0} onKeyDown={(e) => e.key === "Enter" && onSelect(r)}>
                    <td className="mono">{r.step}</td>
                    <td className="mono">{r.record}</td>
                    <td>{r.job}</td>
                    <td>
                      <span className={`tone-${ucTone(r.old?.uc)}`}>{fmtUc(r.old?.uc)}</span>
                      {r.uc_current_size_new_layout != null && r.size_new !== r.size_old && (
                        <span className={`tone-${ucTone(r.uc_current_size_new_layout)}`} title="current size, new layout">
                          {" "}
                          / {fmtUc(r.uc_current_size_new_layout)}
                        </span>
                      )}{" "}
                      {"->"} <b className={`tone-${ucTone(r.new?.uc)}`}>{fmtUc(r.new?.uc)}</b>
                    </td>
                    <td className="mono">{r.size_old && r.size_new && r.size_new !== r.size_old ? `${r.size_old} -> ${r.size_new}` : r.size_new ?? r.size_old ?? ""}</td>
                    <td>
                      <Status r={r} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : (
        !busy && <p className="muted">Nothing re-run yet. Use Re-run on a record in Calcs to redo, or Re-run all stale.</p>
      )}
      <h3 className="v2-h3">
        Earlier calc revisions <InfoTip id="panel.rerun-history" />
      </h3>
      <ul className="v2-list">
        {(revs.data?.calc_revisions ?? [])
          .slice()
          .reverse()
          .map((c) => (
            <li key={c.rev_id}>
              <button type="button" className={`btn sm${rev?.rev_id === c.rev_id ? " on" : ""}`} onClick={() => onLoadRev(c.rev_id)}>
                {c.rev_id}
              </button>{" "}
              <span className="muted">
                {c.created_at} - {c.restore ? `${c.restore.verb} of ${c.restore.of}, restores ${c.restore.restored ?? "the original package"} - ` : ""}
                {changeLabel(c.change)} - {c.summary.records} records, {c.summary.resized} re-sized
              </span>
            </li>
          ))}
      </ul>
    </div>
  );
}
