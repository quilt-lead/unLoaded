import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { InfoTip } from "../../help/InfoTip";
import { StatPill, StatRow } from "../../components/StatPill";
import type { ApplyResult, ModelDiff, ModelRevision, Move, RestoreResult } from "./api";
import { useCompare, useRevisions } from "./api";
import { colShort } from "./util";

export interface RevisionPanelProps {
  move: Move | null;
  applying: boolean;
  applyError: string | null;
  /** the last write: an apply, or an undo / redo of one (a restoring revision) */
  applied: ApplyResult | RestoreResult | null;
  onApply: (label: string) => void;
  /** which model revision the 3D shows (null = the base design file) */
  viewRev: number | null;
  onViewRev: (rid: number | null) => void;
}

function DiffTable({ diff }: { diff: ModelDiff }) {
  const [hideGeom, setHideGeom] = useState(true);
  const rows = useMemo(
    () => diff.changed.filter((c) => !hideGeom || Object.keys(c.fields).some((k) => k !== "geometry")).sort((a, b) => (a.mark ?? "").localeCompare(b.mark ?? "")),
    [diff, hideGeom],
  );
  return (
    <>
      <StatRow>
        <StatPill label="Changed" value={diff.changed.length} info="stat.rev-changed" tone="warn" />
        <StatPill label="Added" value={diff.added.length} info="stat.rev-added" tone="good" />
        <StatPill label="Removed" value={diff.removed.length} info="stat.rev-removed" tone={diff.removed.length ? "bad" : "neutral"} />
        <StatPill label="Load-path edges" value={`+${diff.edges_added.length} / -${diff.edges_removed.length}`} info="stat.rev-edges" />
      </StatRow>
      <label className="v2-check">
        <input type="checkbox" checked={hideGeom} onChange={(e) => setHideGeom(e.target.checked)} /> Hide elements that only moved (geometry only) - showing{" "}
        {rows.length}
      </label>
      <div className="v2-table-wrap">
        <table className="v2-table">
          <thead>
            <tr>
              <th>Element</th>
              <th>
                Field <InfoTip id="table.rev-field" />
              </th>
              <th>Before</th>
              <th>After</th>
            </tr>
          </thead>
          <tbody>
            {rows.flatMap((c) =>
              Object.entries(c.fields).map(([k, [a, b]], i) => (
                <tr key={`${c.global_id}-${k}`}>
                  <td className="mono">{i === 0 ? c.mark ? <Link to={`/v2/element/${encodeURIComponent(c.mark)}`}>{c.mark}</Link> : c.global_id : ""}</td>
                  <td>{k.replace("Structural.", "")}</td>
                  <td className="mono">{a}</td>
                  <td className="mono">
                    <b>{b}</b>
                  </td>
                </tr>
              )),
            )}
            {diff.added.map((c) => (
              <tr key={`a${c.global_id}`}>
                <td className="mono">{c.mark ?? c.global_id}</td>
                <td colSpan={3} className="tone-good">
                  added
                </td>
              </tr>
            ))}
            {diff.removed.map((c) => (
              <tr key={`r${c.global_id}`}>
                <td className="mono">{c.mark ?? c.global_id}</td>
                <td colSpan={3} className="tone-bad">
                  removed
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

function RevTable({ revs, viewRev, onViewRev }: { revs: ModelRevision[]; viewRev: number | null; onViewRev: (rid: number | null) => void }) {
  if (!revs.length) return null;
  return (
    <div className="v2-table-wrap">
      <table className="v2-table">
        <thead>
          <tr>
            <th>Rev</th>
            <th>Label</th>
            <th>Created</th>
            <th>Show in 3D</th>
          </tr>
        </thead>
        <tbody>
          {revs.map((m) => (
            <tr key={m.id}>
              <td className="mono">
                {m.id}
                {m.parent_id != null && <span className="muted"> (from {m.parent_id})</span>}
              </td>
              <td>{m.label}</td>
              <td className="muted">{m.created_at.replace("T", " ").slice(0, 16)}</td>
              <td>
                <button type="button" className={`btn sm${viewRev === m.id ? " on" : ""}`} onClick={() => onViewRev(viewRev === m.id ? null : m.id)}>
                  {viewRev === m.id ? "Showing" : "Show"}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Apply the move as a new model revision (the store never overwrites) and diff any two revisions. */
export function RevisionPanel({ move, applying, applyError, applied, onApply, viewRev, onViewRev }: RevisionPanelProps) {
  const revs = useRevisions();
  // split and ordered at the source (GET /revisions): this design's history newest first, earlier designs apart
  const models = revs.data?.model_revisions ?? [];
  const earlier = revs.data?.earlier_model_revisions ?? [];
  const pickable = [...models, ...earlier];
  const [label, setLabel] = useState("");
  const [a, setA] = useState<number | null>(null);
  const [b, setB] = useState<number | null>(null);
  // the diff the write returned: apply = parent (base) -> revision; undo / redo = replaced head -> revision
  const from = applied ? ("verb" in applied ? applied.previous_head : applied.parent) : null;
  useEffect(() => {
    if (applied) {
      setA("verb" in applied ? applied.previous_head : applied.parent);
      setB(applied.revision);
    }
  }, [applied]);
  const own = !!applied && a === from && b === applied.revision;
  const cmp = useCompare(own ? null : a, b);
  const diff = own ? applied!.diff : cmp.data;
  const canApply = !!move && (move.remove || move.dx !== 0 || move.dy !== 0);
  const def = move ? (move.remove ? `Remove ${move.column}` : `Move ${move.column} (${move.dx >= 0 ? "+" : ""}${move.dx}, ${move.dy >= 0 ? "+" : ""}${move.dy}) ft`) : "";

  return (
    <div className="v2-revs">
      <div className="v2-apply">
        <input className="v2-input" value={label} placeholder={def || "Select and move a column first"} onChange={(e) => setLabel(e.target.value)} aria-label="Revision label" />
        <button type="button" className="btn primary" disabled={!canApply || applying} onClick={() => onApply(label)} data-testid="apply">
          {applying ? "Applying (re-design + IFC)..." : "Apply as model revision"}
        </button>
        <InfoTip id="panel.rev-apply" />
      </div>
      {move && canApply && (
        <p className="v2-small muted">
          Applying writes a new IFC for {move.remove ? `the building without ${colShort(move.column)}` : `${colShort(move.column)} at its new position`} with a
          minimum-change re-design (members keep their size unless they fail), ingests it as a new revision and diffs it against its parent.
        </p>
      )}
      {applyError && <p className="v2-error">Apply failed: {applyError}</p>}
      {applied &&
        ("verb" in applied ? (
          <p className="v2-ok">
            {applied.verb === "undo" ? "Undid" : "Redid"} revision R{applied.of}: restored R{applied.restored} as R{applied.revision}. Nothing was deleted; the diff
            below is R{applied.previous_head} {"->"} R{applied.revision}.
          </p>
        ) : (
          <p className="v2-ok">
            Revision {applied.revision} saved ({applied.label}). Parent R{applied.parent} = the base design every move is computed from, so the diff below is only this
            move; it replaced head R{applied.previous_head}.
          </p>
        ))}
      <h3 className="v2-h3">
        Model revisions <InfoTip id="panel.rev-list" />
      </h3>
      <RevTable revs={models} viewRev={viewRev} onViewRev={onViewRev} />
      {!models.length && <p className="muted v2-small">No revision of the current design yet. Apply a move to make one.</p>}
      {!!earlier.length && (
        <details className="v2-small" data-testid="earlier-revisions">
          <summary>Show {earlier.length} from earlier designs</summary>
          <RevTable revs={earlier} viewRev={viewRev} onViewRev={onViewRev} />
        </details>
      )}
      <h3 className="v2-h3">
        Before / after diff <InfoTip id="panel.rev-diff" />
      </h3>
      <div className="v2-toolbar">
        <label>
          Before{" "}
          <select value={a ?? ""} onChange={(e) => setA(e.target.value ? Number(e.target.value) : null)}>
            <option value="">-</option>
            {pickable.map((m) => (
              <option key={m.id} value={m.id}>
                {m.id} {m.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          After{" "}
          <select value={b ?? ""} onChange={(e) => setB(e.target.value ? Number(e.target.value) : null)}>
            <option value="">-</option>
            {pickable.map((m) => (
              <option key={m.id} value={m.id}>
                {m.id} {m.label}
              </option>
            ))}
          </select>
        </label>
      </div>
      {cmp.isLoading && <p className="muted">Comparing...</p>}
      {cmp.error && <p className="v2-error">{(cmp.error as Error).message}</p>}
      {diff ? <DiffTable diff={diff} /> : <p className="muted">Pick two revisions, or apply a move.</p>}
    </div>
  );
}
