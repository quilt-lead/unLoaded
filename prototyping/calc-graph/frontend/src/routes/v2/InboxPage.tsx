// Inbound inbox: RFIs, change events and change order requests from the platform adapter. Read by the AI
// step, confirmed by the engineer, run through the move-a-column impact engine, answered with a drafted reply.
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { InfoTip } from "../../help/InfoTip";
import { Panel } from "../../components/Panel";
import { StatPill, StatRow } from "../../components/StatPill";
import { AsOfControl } from "./AsOfPanel";
import { useAsOfInfo } from "./asOf";
import { CHANGE_TYPES, useInbox, useInboxActions, type ChangeType, type InboxImpact, type InboxItem, type Reading } from "./inboxApi";
import { fmtUsd } from "./util";
import "./asof-inbox.css";

const KIND_LABEL: Record<InboxItem["kind"], string> = { rfi: "RFI", change_event: "Change event", change_order: "Change order request" };
const errMsg = (e: unknown) => (e instanceof Error ? e.message : e ? String(e) : null);

export default function InboxPage() {
  const [platform, setPlatform] = useState<string | null>(null);
  const q = useInbox(platform);
  const [sel, setSel] = useState<string | null>(null);
  const items = q.data?.items ?? [];
  const item = items.find((i) => i.key === sel) ?? null;
  useEffect(() => {
    if (!sel && items.length) setSel(items[0].key);
  }, [sel, items]);

  return (
    <div className="v2-page ai-inbox">
      <div className="v2-head">
        <h1 className="v2-title">
          Inbox <InfoTip id="page.v2-inbox" />
        </h1>
        <span className="v2-synth">RFIs, change events and change order requests waiting on the engineer</span>
        <span className="spacer" />
        <label className="v2-field">
          Platform
          <select value={platform ?? q.data?.platform ?? ""} onChange={(e) => { setPlatform(e.target.value); setSel(null); }} aria-label="Platform">
            {(q.data?.platforms ?? []).map((p) => (
              <option key={p.name} value={p.name}>
                {p.label} ({p.source})
              </option>
            ))}
          </select>
          <InfoTip id="panel.inbox-platform" />
        </label>
        <Link className="btn sm" to="/v2">
          Move a column
        </Link>
      </div>
      <StatRow>
        <StatPill label="Open items" value={items.length} info="stat.inbox-open" />
        <StatPill label="Read" value={items.filter((i) => i.reading).length} info="stat.inbox-read" tone="calc" />
        <StatPill label="Confirmed" value={items.filter((i) => i.state.confirmed).length} info="stat.inbox-confirmed" tone="good" />
        {q.data && (
          <span className="v2-small muted" data-testid="llm-status">
            AI step: {q.data.llm.provider} / {q.data.llm.model} - {q.data.llm.enabled ? `on (cap $${q.data.llm.run_cap_usd})` : "off: cached readings only"}; this server spent $
            {q.data.llm.run.cost_usd.toFixed(3)} in {q.data.llm.run.calls} calls, {q.data.llm.run.cache_hits} cache hits
          </span>
        )}
        {q.error && <span className="v2-error v2-small">{errMsg(q.error)}</span>}
      </StatRow>
      <div className="ai-inbox-work">
        <Panel title="Incoming" info="panel.inbox-list" className="ai-inbox-list">
          {q.isLoading && <p className="muted">Loading the platform's open items...</p>}
          <ul className="ai-items">
            {items.map((i) => (
              <li key={i.key}>
                <button type="button" className={`ai-item${i.key === sel ? " on" : ""}`} onClick={() => setSel(i.key)} data-testid={`item-${i.number}`}>
                  <span className="ai-item-top">
                    <span className="mono">{i.number}</span>
                    <span className="v2-chip">{KIND_LABEL[i.kind]}</span>
                    {i.state.confirmed ? <span className="v2-chip tone-good">confirmed</span> : i.reading ? <span className="v2-chip accent">read</span> : null}
                  </span>
                  <span className="ai-item-title">{i.title}</span>
                  <span className="v2-small muted">
                    received {i.received ?? "-"}
                    {i.required_by && <> - required by {i.required_by}</>}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </Panel>
        {item ? <ItemDetail key={item.key + item.content_hash} item={item} /> : <p className="muted">Pick an item.</p>}
      </div>
    </div>
  );
}

function ItemDetail({ item }: { item: InboxItem }) {
  const act = useInboxActions();
  const info = useAsOfInfo();
  const base = item.state.confirmed ?? item.reading;
  const [draft, setDraft] = useState<Reading | null>(base);
  useEffect(() => setDraft(item.state.confirmed ?? item.reading), [item.state.confirmed, item.reading]);
  const [asOf, setAsOf] = useState<string>(item.required_by ?? "today");
  const [reply, setReply] = useState<string>(item.state.reply ?? "");
  useEffect(() => setReply(item.state.reply ?? ""), [item.state.reply]);
  const [confirmPost, setConfirmPost] = useState(false);
  const impact: InboxImpact | null = act.impact.data ?? item.state.impact;
  const dirty = useMemo(() => JSON.stringify(draft) !== JSON.stringify(item.state.confirmed), [draft, item.state.confirmed]);

  return (
    <div className="ai-detail">
      <Panel title={item.kind === "rfi" ? item.number : `${KIND_LABEL[item.kind]} ${item.number}`} info="panel.inbox-item">
        <h2 className="ai-title">{item.title}</h2>
        <p className="ai-body" data-testid="item-body">
          {item.body}
        </p>
        <p className="v2-small muted">
          From {item.platform_label} ({item.source}) - received {item.received ?? "-"}
          {item.required_by && <> - required by {item.required_by}</>} - status {item.status}
          {item.link && (
            <>
              {" "}- <span className="mono">{item.link}</span>
            </>
          )}
          {item.linked_element_ids.length ? <> - linked on the platform to {item.linked_element_ids.join(", ")}</> : <> - not linked to any element on the platform</>}
        </p>
      </Panel>

      <Panel
        title="AI reading"
        info="panel.inbox-reading"
        actions={
          <button type="button" className="btn sm primary" disabled={act.read.isPending} onClick={() => act.read.mutate(item.key)} data-testid="read">
            {item.reading ? "Read again (cached)" : act.read.isPending ? "Reading..." : "Read with AI"}
          </button>
        }
      >
        {act.read.error && <p className="v2-error v2-small">{errMsg(act.read.error)}</p>}
        {act.read.data && (
          <p className="v2-small muted">
            {act.read.data.cached ? "Served from the content-hash cache (no spend)." : `New reading: $${(act.read.data.usage?.cost_usd ?? 0).toFixed(4)}.`}
          </p>
        )}
        {!draft ? (
          <p className="muted">Not read yet. The AI step reads which elements, what change, how confident, and what it could not resolve; you confirm or edit it before anything runs.</p>
        ) : (
          <ReadingEditor reading={draft} onChange={setDraft} aiConfidence={item.reading?.confidence} />
        )}
        {draft && (
          <div className="ai-row">
            <button
              type="button"
              className="btn sm primary"
              disabled={act.confirm.isPending || (!dirty && !!item.state.confirmed)}
              onClick={() => act.confirm.mutate({ key: item.key, reading: { ...draft, confidence: undefined, evidence_refs: undefined } })}
              data-testid="confirm"
            >
              {item.state.confirmed ? (dirty ? "Confirm edits" : "Confirmed") : "Confirm reading"}
            </button>
            <InfoTip id="panel.inbox-confirm" />
            {act.confirm.error && <span className="v2-error v2-small">{errMsg(act.confirm.error)}</span>}
          </div>
        )}
      </Panel>

      <Panel title="Impact" info="panel.inbox-impact">
        <AsOfControl value={asOf} onChange={(v) => setAsOf(v)} />
        <p className="v2-small muted">
          Default approval date = the item's required-by date ({item.required_by ?? "none, so today"}).
        </p>
        <div className="ai-row">
          <button type="button" className="btn sm primary" disabled={!item.state.confirmed || act.impact.isPending} onClick={() => act.impact.mutate({ key: item.key, as_of: asOf })} data-testid="run-impact">
            {act.impact.isPending ? "Running..." : "Run impact"}
          </button>
          {!item.state.confirmed && <span className="v2-small muted">Confirm the reading first.</span>}
          {act.impact.error && <span className="v2-error v2-small">{errMsg(act.impact.error)}</span>}
        </div>
        {impact && <ImpactView impact={impact} presets={info.data?.presets.length ?? 0} />}
      </Panel>

      <Panel
        title="Reply"
        info="panel.inbox-reply"
        actions={
          <button type="button" className="btn sm" disabled={!item.state.confirmed || act.reply.isPending} onClick={() => act.reply.mutate(item.key)} data-testid="draft-reply">
            {item.state.reply ? "Redraft" : "Draft reply"}
          </button>
        }
      >
        {act.reply.error && <p className="v2-error v2-small">{errMsg(act.reply.error)}</p>}
        <textarea className="ai-reply" value={reply} onChange={(e) => setReply(e.target.value)} placeholder="Confirm the reading, run the impact, then draft the reply." aria-label="Reply text" data-testid="reply-text" />
        <div className="ai-row">
          <button type="button" className="btn sm" disabled={!item.state.reply || reply === item.state.reply || act.saveReply.isPending} onClick={() => act.saveReply.mutate({ key: item.key, reply })}>
            Save edits
          </button>
          {item.state.reply_edited_at && <span className="v2-small muted">edited {item.state.reply_edited_at}</span>}
          <span className="spacer" />
          <PostButton item={item} confirmPost={confirmPost} setConfirmPost={setConfirmPost} onPost={() => act.post.mutate(item.key)} error={errMsg(act.post.error)} />
        </div>
      </Panel>
    </div>
  );
}

function PostButton({ item, confirmPost, setConfirmPost, onPost, error }: { item: InboxItem; confirmPost: boolean; setConfirmPost: (b: boolean) => void; onPost: () => void; error: string | null }) {
  const post = (item as InboxItem & { post?: { allowed: boolean; reason: string } }).post;
  const allowed = !!post?.allowed && !!item.state.reply;
  return (
    <span className="ai-post">
      {confirmPost && allowed ? (
        <>
          <span className="v2-small">Post this reply to {item.platform_label}?</span>
          <button type="button" className="btn sm primary" onClick={() => { setConfirmPost(false); onPost(); }}>
            Yes, post
          </button>
          <button type="button" className="btn sm" onClick={() => setConfirmPost(false)}>
            Cancel
          </button>
        </>
      ) : (
        <button type="button" className="btn sm" disabled={!allowed} onClick={() => setConfirmPost(true)} title={post?.reason} data-testid="post">
          Post to platform
        </button>
      )}
      <InfoTip id="panel.inbox-post" />
      {!allowed && post && (
        <span className="v2-small muted" data-testid="post-reason">
          {post.reason}
        </span>
      )}
      {error && <span className="v2-error v2-small">{error}</span>}
    </span>
  );
}

function ReadingEditor({ reading, onChange, aiConfidence }: { reading: Reading; onChange: (r: Reading) => void; aiConfidence?: number }) {
  const set = (patch: Partial<Reading>) => onChange({ ...reading, ...patch });
  const prim = reading.elements.filter((e) => e.role === "primary").map((e) => e.element_id).join(", ");
  const aff = reading.elements.filter((e) => e.role === "affected").map((e) => e.element_id).join(", ");
  const toRefs = (s: string, role: "primary" | "affected") =>
    s
      .split(/[\s,]+/)
      .map((x) => x.trim().toUpperCase())
      .filter(Boolean)
      .map((id) => reading.elements.find((e) => e.element_id === id && e.role === role) ?? { element_id: id, role, how_identified: "set by the engineer" });
  const isMove = reading.change_type === "move_column";
  const isSize = reading.change_type === "substitute_section" || reading.change_type === "resize_member";
  return (
    <div className="ai-reading" data-testid="reading">
      <p className="ai-summary">{reading.summary}</p>
      {aiConfidence != null && (
        <p className="v2-small">
          AI confidence <b className={aiConfidence >= 0.8 ? "tone-good" : aiConfidence >= 0.5 ? "tone-warn" : "tone-bad"}>{Math.round(aiConfidence * 100)}%</b>
        </p>
      )}
      <div className="ai-grid">
        <label className="v2-field">
          Change
          <select value={reading.change_type} onChange={(e) => set({ change_type: e.target.value as ChangeType })} aria-label="Change type">
            {CHANGE_TYPES.map((c) => (
              <option key={c} value={c}>
                {c.replace(/_/g, " ")}
              </option>
            ))}
          </select>
        </label>
        <label className="v2-field">
          Primary
          <input value={prim} onChange={(e) => set({ elements: [...toRefs(e.target.value, "primary"), ...reading.elements.filter((x) => x.role === "affected")] })} aria-label="Primary element id" />
        </label>
        {isMove && (
          <>
            <label className="v2-field">
              dx ft
              <input type="number" step={0.5} value={reading.move?.dx_ft ?? ""} onChange={(e) => set({ move: { dx_ft: Number(e.target.value), dy_ft: reading.move?.dy_ft ?? 0 } })} aria-label="Move east, ft" />
            </label>
            <label className="v2-field">
              dy ft
              <input type="number" step={0.5} value={reading.move?.dy_ft ?? ""} onChange={(e) => set({ move: { dx_ft: reading.move?.dx_ft ?? 0, dy_ft: Number(e.target.value) } })} aria-label="Move north, ft" />
            </label>
          </>
        )}
        {isSize && (
          <label className="v2-field">
            New section
            <input value={reading.new_section ?? ""} onChange={(e) => set({ new_section: e.target.value.toUpperCase() || null })} aria-label="New section" />
          </label>
        )}
      </div>
      <label className="v2-field ai-wide">
        Affected
        <input value={aff} onChange={(e) => set({ elements: [...reading.elements.filter((x) => x.role === "primary"), ...toRefs(e.target.value, "affected")] })} aria-label="Affected element ids" />
      </label>
      {reading.elements.length > 0 && (
        <ul className="v2-list ai-why">
          {reading.elements.slice(0, 8).map((e) => (
            <li key={e.role + e.element_id}>
              <Link to={`/v2/element/${encodeURIComponent(e.element_id)}`} className="mono">
                {e.element_id}
              </Link>{" "}
              <span className="v2-chip">{e.role}</span> <span className="v2-small muted">{e.how_identified}</span>
            </li>
          ))}
          {reading.elements.length > 8 && <li className="muted v2-small">+ {reading.elements.length - 8} more</li>}
        </ul>
      )}
      <div className="ai-unres">
        <b className="v2-small">Could not resolve</b> <InfoTip id="panel.inbox-unresolved" />
        {reading.unresolved.length ? (
          <ul className="v2-list">
            {reading.unresolved.map((u, i) => (
              <li key={i} className="v2-small">
                {u}{" "}
                <button type="button" className="v2-link-btn" onClick={() => set({ unresolved: reading.unresolved.filter((_, j) => j !== i) })} aria-label="Mark resolved">
                  resolved
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <span className="v2-small muted"> nothing</span>
        )}
      </div>
    </div>
  );
}

function ImpactView({ impact }: { impact: InboxImpact; presets: number }) {
  const p = impact.plan;
  const co = impact.change_order;
  return (
    <div className="ai-impact" data-testid="impact">
      <p className={`v2-small ${p.expressible === true ? "v2-ok" : p.expressible === "partial" ? "tone-warn" : "v2-error"}`}>
        {p.expressible === true ? "Engine: " : p.expressible === "partial" ? "Partly expressible: " : "Not expressible: "}
        {p.reason}
      </p>
      <p className="v2-small muted">
        Approved on {impact.as_of.as_of} {impact.as_of.projected ? `(projected: CPM data date ${impact.as_of.data_date})` : "(today's state)"} - run {impact.computed_at}
      </p>
      {impact.impact && (
        <StatRow>
          <StatPill label="Calcs to redo" value={impact.impact.stale} info="stat.move-stale" tone="calc" />
          <StatPill label="Design" value={String(impact.impact.health.band)} info="stat.move-health-design" />
          <StatPill label="With construction" value={String(impact.impact.health.band_construction ?? "-")} info="stat.move-health-construction" />
        </StatRow>
      )}
      {co && (
        <StatRow>
          <StatPill label="Cost est." value={fmtUsd(co.total_cost.value)} info="stat.co-cost" tone="warn" />
          <StatPill label="Forecast slip" value={`${co.forecast_slip.value} wd`} info="stat.inbox-slip" />
          <StatPill label="Past contract" value={`${co.finish_delay.value} wd`} info="stat.inbox-delay" />
        </StatRow>
      )}
      {impact.timeline?.approve_by_line && (
        <p className="ai-approve" data-testid="inbox-approve-by">
          {impact.timeline.approve_by_line}
        </p>
      )}
      {impact.records_to_redo && <p className="v2-small">Calc records to redo: {impact.records_to_redo.join(", ")}</p>}
      {impact.status && Object.keys(impact.status).length > 0 && (
        <ul className="v2-list">
          {Object.entries(impact.status).map(([eid, s]) => (
            <li key={eid} className="v2-small">
              <span className="mono">{eid}</span> {s.stage ? <>is <b>{s.stage}</b></> : s.error}
              {s.submittals?.length ? <> - submittals {s.submittals.join(", ")}</> : null}
            </li>
          ))}
        </ul>
      )}
      {impact.links?.move_page && (
        <Link className="btn sm" to={impact.links.move_page} data-testid="open-move">
          Open in Move a column
        </Link>
      )}
    </div>
  );
}
