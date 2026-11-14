import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { InfoTip } from "../../help/InfoTip";
import { StatPill, StatRow } from "../../components/StatPill";
import { Tabs } from "../../components/Tabs";
import type { AnsweredBy, EtabsJob, EtabsObject, Move } from "./api";
import { e2kUrl, useEtabsObjects, useEtabsPull, useEtabsSend } from "./api";
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

export function AnsweredBadge({ a, source, method }: { a: AnsweredBy | undefined; source?: string; method?: string }) {
  const l = answeredLabel(a, source ?? (method?.includes("PyNite") ? "calcgraph-pynite" : undefined));
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
      <AnsweredBadge a={job.answered_by} source={job.source} method={job.method} />
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

/** ETABS panel: the model as ETABS would hold it, plus mock send / pull for the current move. Which adapter answered is always on screen. */
export function EtabsPanel({ move }: { move: Move | null }) {
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
      <AnsweredBadge a={objs.data?.answered_by} />
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
      {!hasMove && <p className="muted v2-small">Move or remove a column to send the change.</p>}
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
