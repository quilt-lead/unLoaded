import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { InfoTip } from "../../help/InfoTip";
import { StatPill, StatRow } from "../../components/StatPill";
import { Tabs } from "../../components/Tabs";
import type { AnsweredBy, EtabsJob, EtabsObject, EtabsRunSummary, Move } from "./api";
import { e2kUrl, useEtabsObjects, useEtabsPull, useEtabsRun, useEtabsRuns, useEtabsSend } from "./api";
import { fmtUc, ucTone } from "./util";

/** Which adapter answered, in words an engineer can trust: mock, our PyNite, or real ETABS (OAPI / BHoM). */
export function answeredLabel(a: AnsweredBy | undefined, source?: string): { text: string; kind: "mock" | "ours" | "real" } {
  if (source === "csi-oapi") return { text: "Real ETABS - read through CSI OAPI on the Windows bridge", kind: "real" };
  if (source === "etabs-via-bhom") return { text: "Real ETABS - read through BHoM ETABS_Toolkit on the Windows bridge", kind: "real" };
  if (source === "calcgraph-pynite") return { text: "Our PyNite re-run - ETABS did not run", kind: "ours" };
  if (!a) return { text: "Unknown adapter", kind: "mock" };
  if (a.adapter === "bhom_etabs" && source !== "mock")
    return { text: "ETABS via BHoM adapter (Windows bridge) - check each row's source", kind: "real" };
  return { text: "Mock ETABS - our design mapped to ETABS objects; ETABS did not run", kind: "mock" };
}

/** `source` = the ResultSource code every analysis response carries (mock included: AnalysisAdapter contract). */
export function AnsweredBadge({ a, source }: { a: AnsweredBy | undefined; source?: string }) {
  const l = answeredLabel(a, source);
  return (
    <span className={`v2-answered ${l.kind}`}>
      <b>Answered by:</b> {l.text}
      {a && <span className="mono muted"> (adapter {a.adapter})</span>}
      <InfoTip id="stat.etabs-answered" />
    </span>
  );
}

type Kind = "frame_design" | "story_drift" | "frame" | "point" | "section" | "combo" | "load_case" | "story";

const KINDS: { id: Kind; label: string; info: "tab.etabs-design" | "tab.etabs-drift" | "tab.etabs-frames" | "tab.etabs-points" | "tab.etabs-sections" | "tab.etabs-combos" | "tab.etabs-cases" | "tab.etabs-stories" }[] = [
  { id: "frame_design", label: "Design D/C", info: "tab.etabs-design" },
  { id: "story_drift", label: "Drifts", info: "tab.etabs-drift" },
  { id: "frame", label: "Frames", info: "tab.etabs-frames" },
  { id: "point", label: "Points", info: "tab.etabs-points" },
  { id: "section", label: "Sections", info: "tab.etabs-sections" },
  { id: "combo", label: "Combos", info: "tab.etabs-combos" },
  { id: "load_case", label: "Load cases", info: "tab.etabs-cases" },
  { id: "story", label: "Stories", info: "tab.etabs-stories" },
];

const short = (v: unknown) => (typeof v === "number" ? (Math.abs(v) < 10 ? v.toFixed(3) : v.toFixed(1)) : typeof v === "object" ? JSON.stringify(v) : String(v ?? ""));

function ObjectTable({ objs, kind }: { objs: EtabsObject[]; kind: Kind }) {
  const rows = useMemo(() => {
    const o = objs.filter((x) => x.kind === kind);
    if (kind === "frame_design") return o.sort((a, b) => Number(b.props.ratio ?? b.props.Ratio ?? 0) - Number(a.props.ratio ?? a.props.Ratio ?? 0));
    return o;
  }, [objs, kind]);
  const keys = useMemo(() => {
    const ks = new Map<string, number>();
    for (const r of rows.slice(0, 40)) for (const k of Object.keys(r.props)) if (!k.startsWith("source")) ks.set(k, (ks.get(k) ?? 0) + 1);
    return [...ks.keys()].slice(0, 5);
  }, [rows]);
  return (
    <div className="v2-table-wrap tall">
      <table className="v2-table">
        <thead>
          <tr>
            <th>Label</th>
            <th>Story</th>
            <th>Element</th>
            {keys.map((k) => (
              <th key={k}>{k}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.slice(0, 300).map((r, i) => (
            <tr key={`${r.label}-${r.story}-${i}`}>
              <td className="mono">{r.label}</td>
              <td>{r.story ?? ""}</td>
              <td className="mono">{r.element_id ? <Link to={`/v2/element/${encodeURIComponent(r.element_id)}`}>{r.element_id}</Link> : ""}</td>
              {keys.map((k) => {
                const v = r.props[k];
                const isRatio = (k === "ratio" || k === "dc") && typeof v === "number";
                return (
                  <td key={k} className={isRatio ? `mono tone-${ucTone(v as number)}` : "mono"}>
                    {isRatio ? fmtUc(v as number) : short(v)}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length > 300 && <p className="muted v2-small">First 300 of {rows.length}.</p>}
    </div>
  );
}

function JobCard({ job }: { job: EtabsJob }) {
  return (
    <div className="v2-job">
      <div>
        <b className="mono">{job.job_id}</b> <span className="v2-chip">{job.status}</span>
      </div>
      <AnsweredBadge a={job.answered_by} source={job.source} />
      {job.note && <p className="v2-small v2-warnline">{job.note}</p>}
      {job.diff_summary && (
        <p className="v2-small">
          Change package:{" "}
          {Object.entries(job.diff_summary)
            .filter(([, v]) => v)
            .map(([k, v]) => `${v} ${k.replace(/_/g, " ")}`)
            .join(", ") || "no geometry change"}
        </p>
      )}
      {job.summary && (
        <>
          <StatRow>
            <StatPill label="Max D/C" value={fmtUc(job.summary.max_ratio)} info="stat.etabs-max-ratio" tone={ucTone(job.summary.max_ratio)} />
            <StatPill label="Frames over 1.0" value={job.summary.frames_over_1?.length ?? 0} info="stat.etabs-over" tone={job.summary.frames_over_1?.length ? "bad" : "good"} />
            <StatPill label="Sections changed" value={job.summary.sections_changed ?? 0} info="stat.etabs-sections" />
          </StatRow>
          {job.summary.max_drift_dc && (
            <p className="v2-small">
              Drift D/C by line:{" "}
              {Object.entries(job.summary.max_drift_dc)
                .map(([k, v]) => `${k} ${fmtUc(v)} (was ${fmtUc(job.summary?.base_max_drift_dc?.[k])})`)
                .join(", ")}
            </p>
          )}
          {!!job.summary.sections_changed_list?.length && (
            <details className="v2-small">
              <summary>Sections changed ({job.summary.sections_changed_list.length})</summary>
              <ul>
                {job.summary.sections_changed_list.map((s) => (
                  <li key={`${s.label}-${s.story}`}>
                    <span className="mono">
                      {s.label}@{s.story}
                    </span>{" "}
                    {s.element_id}: {s.from} {"->"} {s.to}
                  </li>
                ))}
              </ul>
            </details>
          )}
        </>
      )}
    </div>
  );
}

const pct = (v: number | null | undefined) => (v == null ? "-" : `${v.toFixed(1)}%`);

/** One saved REAL ETABS run (etabs_runs.py): label with version and date, what it found, modes, drift by line
 * vs the design, and the per-member agreement with PyNite. */
function RealRunCard({ s, note }: { s: EtabsRunSummary; note?: string }) {
  const run = useEtabsRun(s.run_id);
  const r = run.data;
  return (
    <div className="v2-job v2-real-run" data-testid="etabs-real-run">
      <div>
        <span className="v2-answered real">
          <b>{s.label}</b> <span className="mono muted">({s.etabs_source})</span>
          <InfoTip id="panel.etabs-real" />
        </span>
      </div>
      {note && <p className="v2-small muted">{note}</p>}
      <p className={s.finding.drift_ng.length || s.finding.mode1.shape === "torsional" ? "v2-error" : "v2-ok"} data-testid="etabs-finding">
        {s.finding.headline}
      </p>
      {run.isLoading && <p className="muted v2-small">Loading the run...</p>}
      {run.error && <p className="v2-error">{(run.error as Error).message}</p>}
      {r && (
        <>
          <StatRow>
            <StatPill label="Mode 1" value={`${r.modes[0].period_s.toFixed(3)} s ${s.finding.mode1.shape}`} info="stat.etabs-mode1" tone={s.finding.mode1.shape === "torsional" ? "bad" : "good"} />
            <StatPill label="Worst drift / limit" value={fmtUc(s.finding.worst_drift.etabs_ratio)} info="stat.etabs-drift-ratio" tone={ucTone(s.finding.worst_drift.etabs_ratio)} />
            <StatPill label="Rows over flag %" value={`${s.finding.flagged} / ${s.finding.compared}`} info="stat.etabs-flagged" tone={s.finding.flagged ? "warn" : "good"} />
          </StatRow>
          <details className="v2-small" open>
            <summary>Story drift by line: ETABS vs design (Cd x elastic / Ie, worse eccentricity)</summary>
            <div className="v2-table-wrap">
              <table className="v2-table">
                <thead>
                  <tr>
                    <th>Line</th>
                    <th>Level</th>
                    <th>ETABS in</th>
                    <th>Design in</th>
                    <th>Allow in</th>
                    <th>ETABS / limit</th>
                    <th>Design / limit</th>
                  </tr>
                </thead>
                <tbody>
                  {r.drift.map((d) => (
                    <tr key={`${d.line}-${d.level}`}>
                      <td>{d.line}</td>
                      <td>{d.level}</td>
                      <td className="mono">{d.etabs_in.toFixed(3)}</td>
                      <td className="mono">{d.design_in.toFixed(3)}</td>
                      <td className="mono">{d.allow_in.toFixed(2)}</td>
                      <td className={`mono tone-${ucTone(d.etabs_ratio)}`}>{fmtUc(d.etabs_ratio)}</td>
                      <td className={`mono tone-${ucTone(d.design_in / d.allow_in)}`}>{fmtUc(d.design_in / d.allow_in)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
          <details className="v2-small">
            <summary>Modes (code Ta X {r.code_ta_s.x.toFixed(3)} s, Y {r.code_ta_s.y.toFixed(3)} s)</summary>
            <table className="v2-table">
              <thead>
                <tr>
                  <th>Mode</th>
                  <th>T s</th>
                  <th>UX</th>
                  <th>UY</th>
                  <th>RZ</th>
                </tr>
              </thead>
              <tbody>
                {r.modes.map((m) => (
                  <tr key={m.mode}>
                    <td>{m.mode}</td>
                    <td className="mono">{m.period_s.toFixed(3)}</td>
                    <td className="mono">{m.ux.toFixed(3)}</td>
                    <td className="mono">{m.uy.toFixed(3)}</td>
                    <td className="mono">{m.rz.toFixed(3)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </details>
          <details className="v2-small" open>
            <summary>
              Agreement with PyNite (our 2D frames), governing design combo - within {r.members.flag_pct}% <InfoTip id="table.etabs-agreement" />
            </summary>
            <div className="v2-table-wrap">
              <table className="v2-table" data-testid="etabs-agreement">
                <thead>
                  <tr>
                    <th>Line</th>
                    <th>Members</th>
                    <th>Qty</th>
                    <th>Compared</th>
                    <th>Within {r.members.flag_pct}%</th>
                    <th>Median |%|</th>
                    <th>Max |%|</th>
                  </tr>
                </thead>
                <tbody>
                  {r.members.agreement.map((a) => (
                    <tr key={`${a.line}-${a.members}-${a.qty}`} className={a.n ? undefined : "muted"}>
                      <td className="v2-nowrap">{a.line}</td>
                      <td>{a.members}</td>
                      <td>{a.qty}</td>
                      <td className="mono">{a.n ? a.n : `0 of ${a.rows} (not like-for-like)`}</td>
                      <td className={`mono${a.n ? (a.within === a.n ? " tone-good" : a.within / a.n < 0.5 ? " tone-bad" : " tone-warn") : ""}`}>{a.n ? a.within : "-"}</td>
                      <td className="mono">{pct(a.median_abs_pct)}</td>
                      <td className="mono">{pct(a.max_abs_pct)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
          <p className="v2-small muted">Identity: {s.identity}</p>
        </>
      )}
    </div>
  );
}

/** Saved real ETABS runs of a design ("current" or a design scenario id); none is said out loud. */
export function RealEtabsRuns({ design, move }: { design: string; move?: Move | null }) {
  const q = useEtabsRuns(design);
  const moved = !!move && (move.remove || move.dx !== 0 || move.dy !== 0);
  if (q.isLoading) return <p className="muted v2-small">Looking for real ETABS runs...</p>;
  if (q.error) return <p className="v2-error">{(q.error as Error).message}</p>;
  if (!q.data) return null;
  return (
    <div className="v2-real-runs">
      {q.data.runs.map((s) => (
        <RealRunCard
          key={s.run_id}
          s={s}
          note={moved ? "This run is of the design WITHOUT the move: no real ETABS run exists for a moved column. The send / pull below is the mock." : undefined}
        />
      ))}
      {!q.data.runs.length && (
        <p className="v2-small muted" data-testid="etabs-no-real-run">
          No real ETABS run of {design === "current" ? "the current design" : design} (e2k sha1 {q.data.e2k_sha1?.slice(0, 10) ?? "not built"}). Everything below is the mock.
        </p>
      )}
      {q.data.stale.map((s) => (
        <p key={s.run_id} className="v2-small v2-warnline">
          {s.label} ({s.run_id}) is not shown: {s.stale_reason}.
        </p>
      ))}
    </div>
  );
}

/** ETABS panel: saved REAL runs of the design (labelled with version and date) above the model as ETABS would
 * hold it and the mock send / pull for the current move. Which adapter answered is always on screen. */
export function EtabsPanel({ move, design = "current" }: { move: Move | null; design?: string }) {
  const objs = useEtabsObjects();
  const send = useEtabsSend();
  const pull = useEtabsPull();
  const [kind, setKind] = useState<Kind>("frame_design");
  const counts = useMemo(() => {
    const c: Record<string, number> = {};
    for (const o of objs.data?.items ?? []) c[o.kind] = (c[o.kind] ?? 0) + 1;
    return c;
  }, [objs.data]);
  const hasMove = !!move && (move.remove || move.dx !== 0 || move.dy !== 0);

  return (
    <div className="v2-etabs">
      <h3 className="v2-h3">
        Real ETABS runs <InfoTip id="panel.etabs-real" />
      </h3>
      <RealEtabsRuns design={design} move={move} />
      <h3 className="v2-h3">
        {objs.data?.answered_by?.mock === false ? "Live ETABS link" : "Mock ETABS link"} <InfoTip id="panel.etabs" />
      </h3>
      <AnsweredBadge a={objs.data?.answered_by} source={objs.data?.items[0]?.props.source as string | undefined} />
      <div className="v2-toolbar">
        <a className="btn sm" href={e2kUrl()} download>
          Download .e2k (base)
        </a>
        {hasMove && (
          <a className="btn sm" href={e2kUrl(move)} download>
            Download .e2k (with this move)
          </a>
        )}
        <InfoTip id="panel.etabs-e2k" />
        <span className="spacer" />
        <button type="button" className="btn sm primary" disabled={!hasMove || send.isPending} onClick={() => move && send.mutate(move)}>
          {send.isPending ? "Sending..." : "Send to ETABS"}
        </button>
        <button type="button" className="btn sm" disabled={!send.data || pull.isPending} onClick={() => send.data && pull.mutate(send.data.job_id)}>
          {pull.isPending ? "Pulling (re-analysis)..." : "Pull ETABS results"}
        </button>
        <InfoTip id="panel.etabs-send" />
      </div>
      {!hasMove && (
        <p className="muted v2-small" data-testid="etabs-send-disabled">
          Send to ETABS is off: there is no move to send. {design === "current" ? "Move or remove a column first." : `${design} is a design scenario, not a move.`}
        </p>
      )}
      {send.error && <p className="v2-error">{(send.error as Error).message}</p>}
      {pull.error && <p className="v2-error">{(pull.error as Error).message}</p>}
      {pull.data ? <JobCard job={pull.data} /> : send.data && <JobCard job={send.data} />}
      <Tabs
        items={KINDS.map((k) => ({ ...k, badge: counts[k.id] ?? 0 }))}
        value={kind}
        onChange={setKind}
        info="tab.etabs-objects"
        label="ETABS object kinds"
        size="sm"
      />
      {objs.isLoading && <p className="muted">Loading ETABS objects...</p>}
      {objs.error && <p className="v2-error">{(objs.error as Error).message}</p>}
      {objs.data && <ObjectTable objs={objs.data.items} kind={kind} />}
    </div>
  );
}
