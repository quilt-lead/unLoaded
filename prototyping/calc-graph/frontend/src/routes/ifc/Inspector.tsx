// Right-hand column of the IFC app: the impact box (when an impact check ran) and the inspector
// (mapping summary, a calc, or an element with its links and decisions).
import type { ReactNode } from "react";
import type { IfcElement, IfcImpact, IfcLink } from "../../api/types";
import { InfoTip } from "../../help/InfoTip";
import type { HelpId } from "../../help/registry";
import { Panel } from "../../components/Panel";
import { elLabel, linksFor, linksOfCalc, pageRange, shortTime, TIER, type IfcIndex, type Sel } from "./model";

type Decide = (gid: string, key: string, action: "confirm" | "reject" | "manual" | "undo") => void;

export interface InspectorProps {
  ix: IfcIndex | null;
  sel: Sel;
  impact: IfcImpact | null;
  impactLoading: boolean;
  onSelect: (s: Sel, focus?: boolean) => void;
  onImpact: (gid: string, mode: "change" | "remove") => void;
  onClearImpact: () => void;
  onDecide: Decide;
  onConfirmAll: (links: IfcLink[]) => void;
  onOpenPage: (page: number, rects?: number[][]) => void;
  busy: boolean;
}

function H3({ children, info }: { children: ReactNode; info?: HelpId }) {
  return (
    <h3 className="ifc-h3">
      {children}
      {info && <InfoTip id={info} />}
    </h3>
  );
}

function EList({ ix, arr, extra, onPick }: { ix: IfcIndex; arr: IfcElement[]; extra?: (e: IfcElement) => ReactNode; onPick: (gid: string) => void }) {
  return (
    <div className="ifc-elist">
      {arr.slice(0, 60).map((e) => (
        <button type="button" key={e.global_id} onClick={() => onPick(e.global_id)}>
          <span>{elLabel(e)}</span>
          <span className="muted">{extra ? extra(e) : `${e.cat} · ${e.storey}`}</span>
        </button>
      ))}
      {arr.length > 60 && <div className="muted">+{arr.length - 60} more</div>}
      {!arr.length && <div className="muted">None</div>}
      {ix.els.size === 0 && null}
    </div>
  );
}

function confChip(l: IfcLink) {
  const cls = l.status === "confirmed" || l.status === "manual" || l.conf >= 0.8 ? "good" : l.conf >= 0.5 ? "warn" : "bad";
  const txt = l.status === "confirmed" ? "confirmed" : l.status === "manual" ? "linked by hand" : `${Math.round(l.conf * 100)}%`;
  return <span className={`chip ${cls} ifc-conf`}>{txt}</span>;
}

export function ImpactBox({ ix, impact, onClear, onSelect }: { ix: IfcIndex; impact: IfcImpact; onClear: () => void; onSelect: InspectorProps["onSelect"] }) {
  const el = ix.els.get(impact.global_id);
  const hit = Object.entries(impact.hit).sort((a, b) => a[1] - b[1]);
  const stale = Object.entries(impact.stale);
  const nm = (g: string) => (ix.els.get(g) ? elLabel(ix.els.get(g)!) : g);
  return (
    <section className="ifc-impact" aria-label="Impact">
      <h3 className="ifc-impact-h">
        Impact · {impact.mode === "remove" ? "remove" : "change"} {el ? elLabel(el) : ""}
        <InfoTip id="panel.ifc-impact" />
      </h3>
      <dl className="ifc-kv">
        <dt>Removed / orphaned</dt>
        <dd>{impact.removed.length}</dd>
        <dt>Elements on the load path</dt>
        <dd>
          {hit.length} over {impact.waves} waves
        </dd>
        <dt>Calcs stale</dt>
        <dd>
          {stale.length} of {ix.calcs.size}
        </dd>
      </dl>
      <ul>
        {hit.slice(0, 12).map(([g, w]) => (
          <li key={g}>
            <button type="button" className="linkish" onClick={() => onSelect({ kind: "el", id: g }, true)}>
              <b>{nm(g)}</b>
            </button>{" "}
            <span className="why">
              wave {w}
              {impact.why[g] ? ` - ${impact.why[g]}` : " - load path from upstream"}
            </span>
          </li>
        ))}
        {hit.length > 12 && <li className="why">+{hit.length - 12} more</li>}
      </ul>
      <h3 className="ifc-impact-h">
        Re-run queue <InfoTip id="panel.ifc-rerun" />
      </h3>
      <ul>
        {stale.map(([k, why]) => {
          const c = ix.calcs.get(k);
          return (
            <li key={k}>
              <button type="button" className="linkish" onClick={() => onSelect({ kind: "calc", id: k })}>
                <b>{c?.title ?? k}</b>
              </button>
              {c?.software && <span className="chip warn">{c.software}</span>}
              <br />
              <span className="why">
                {why}
                {c?.software === "Hand calc" || c?.scanned ? " · hand calc: flag for engineer, do not auto-replace" : ""}
              </span>
            </li>
          );
        })}
        {!stale.length && <li className="why">none</li>}
      </ul>
      <div className="ifc-acts">
        <button type="button" className="btn sm" onClick={onClear}>
          Clear impact
        </button>
      </div>
    </section>
  );
}

export function Inspector(p: InspectorProps) {
  const { ix, sel } = p;
  const pick = (gid: string) => p.onSelect({ kind: "el", id: gid }, true);
  let title: ReactNode = "Inspector";
  let body: ReactNode;
  if (!ix || (!ix.st.elements.length && !ix.st.calcs.length)) {
    title = "Nothing loaded";
    body = <p className="muted">Upload an IFC model and a calc package PDF, or load the Harbor View documents.</p>;
  } else if (!sel) {
    const st = ix.st;
    const els = [...ix.els.values()];
    const review = els.filter((e) => e.status === "review");
    const un = els.filter((e) => e.status === "unmapped");
    const revs = st.revisions.slice().reverse();
    title = "Mapping summary";
    body = (
      <>
        <div className="ifc-kind">
          {st.model_rev?.source_name ?? "no model"} ⇄ {st.calc_rev?.source_name ?? "no calc package"}
          {st.run ? ` · ${st.run.engine_version}` : ""}
        </div>
        <div className="ifc-kind">Click an element in the model or a calc on the left.</div>
        <H3 info="insp.ifc-review">Needs review ({review.length})</H3>
        <EList ix={ix} arr={review} onPick={pick} />
        <H3 info="insp.ifc-unmapped">No calc found ({un.length})</H3>
        <EList ix={ix} arr={un} onPick={pick} />
        <H3 info="insp.ifc-no-mark">Elements without a mark</H3>
        <div className="ifc-kind">{els.filter((e) => !e.mark).length} elements have no Mark property, so they can only link by size or type.</div>
        <H3 info="insp.ifc-revisions">Revisions ({revs.length})</H3>
        <div className="ifc-revs">
          {revs.map((r) => (
            <div key={r.id}>
              <span>
                {r.kind === "model" ? "Model" : "Calcs"} rev {r.seq}
                {r.id === st.model_rev?.id || r.id === st.calc_rev?.id ? <b> (head)</b> : null} · {r.label ?? r.source_name}
              </span>
              <span className="muted">{shortTime(r.created_at)}</span>
            </div>
          ))}
        </div>
      </>
    );
  } else if (sel.kind === "calc") {
    const c = ix.calcs.get(sel.id);
    if (!c) body = <p className="muted">This calc is not in the current revision.</p>;
    else {
      const ls = linksOfCalc(ix, c.key);
      const groups = new Map<string, [IfcElement, IfcLink][]>();
      for (const l of ls) {
        const el = ix.els.get(l.global_id);
        if (el) (groups.get(l.tier) ?? groups.set(l.tier, []).get(l.tier)!).push([el, l]);
      }
      const deps = ix.st.calc_edges.filter((e) => e.dst === c.key);
      const feeds = ix.st.calc_edges.filter((e) => e.src === c.key);
      const toReview = ls.filter((l) => l.status === "auto" && l.conf < 0.8);
      title = c.title;
      body = (
        <>
          <div className="ifc-kind">
            Calculation · {pageRange(c)}
            {c.software ? ` · ${c.software}` : ""}
            {c.cat ? ` · ${c.cat}s` : ""}
          </div>
          <div className="ifc-acts">
            <button type="button" className="btn sm" onClick={() => p.onOpenPage(c.pages[0])}>
              Open calc pages
            </button>
            <button type="button" className="btn sm" onClick={() => p.onSelect(null)}>
              Back to summary
            </button>
          </div>
          {c.scanned && <div className="ifc-snip">These pages have no text layer (scanned or handwritten), so nothing could be read from them. An OCR or vision pass would be needed to link them.</div>}
          {c.front && <div className="ifc-snip">Front matter / contents page - never mapped.</div>}
          <H3 info="insp.ifc-calc-inputs">Takes input from ({deps.length})</H3>
          {deps.map((e, i) => (
            <div className="ifc-rule" key={i}>
              <button type="button" className="linkish" onClick={() => p.onSelect({ kind: "calc", id: e.src })}>
                {ix.calcs.get(e.src)?.title ?? e.src}
              </button>{" "}
              - {e.rules.join("; ")}
            </div>
          ))}
          {!deps.length && <div className="ifc-kind">None found</div>}
          <H3 info="insp.ifc-calc-feeds">Feeds ({feeds.length})</H3>
          {feeds.map((e, i) => (
            <div className="ifc-rule" key={i}>
              <button type="button" className="linkish" onClick={() => p.onSelect({ kind: "calc", id: e.dst })}>
                {ix.calcs.get(e.dst)?.title ?? e.dst}
              </button>{" "}
              - {e.rules.join("; ")}
            </div>
          ))}
          {!feeds.length && <div className="ifc-kind">None found</div>}
          {[...groups.entries()].map(([t, arr]) => (
            <div key={t}>
              <H3 info="insp.ifc-tier-group">
                {TIER[t] ?? t} ({arr.length})
              </H3>
              <EList
                ix={ix}
                arr={arr.map((x) => x[0])}
                onPick={pick}
                extra={(e) => {
                  const l = arr.find((x) => x[0] === e)![1];
                  return `${e.cat} · ${e.storey} · ${l.status === "confirmed" ? "confirmed" : Math.round(l.conf * 100) + "%"}`;
                }}
              />
            </div>
          ))}
          {!groups.size && !c.scanned && !c.front && (
            <>
              <H3>Elements</H3>
              <div className="ifc-kind">No model elements matched this calc.</div>
            </>
          )}
          {toReview.length > 0 && (
            <div className="ifc-acts" style={{ marginTop: 12 }}>
              <button type="button" className="btn sm" disabled={p.busy} onClick={() => p.onConfirmAll(toReview)}>
                Confirm all {toReview.length} to review
              </button>
              <InfoTip id="insp.ifc-confirm-all" />
            </div>
          )}
        </>
      );
    }
  } else {
    const el = ix.els.get(sel.id);
    if (!el) body = <p className="muted">This element is not in the current model revision.</p>;
    else {
      const g = el.global_id;
      const ls = linksFor(ix, g);
      const rejected = (ix.linksByEl.get(g) ?? []).filter((l) => l.status === "rejected");
      const up = ix.st.edges.filter((e) => e.dst === g);
      const down = ix.st.edges.filter((e) => e.src === g);
      const props = Object.entries(el.params).slice(0, 40);
      const candidates = [...ix.calcs.values()].filter((c) => !c.front && !ls.some((l) => l.calc_key === c.key));
      const nm = (x: string) => (ix.els.get(x) ? elLabel(ix.els.get(x)!) : x);
      title = elLabel(el);
      body = (
        <>
          <div className="ifc-kind">
            {el.cat} · {el.ifc_type}
            {el.storey ? ` · ${el.storey}` : ""}
          </div>
          <div className="ifc-acts">
            <button type="button" className="btn sm" disabled={p.impactLoading} onClick={() => p.onImpact(g, "change")}>
              Impact if changed
            </button>
            <button type="button" className="btn sm danger" disabled={p.impactLoading} onClick={() => p.onImpact(g, "remove")}>
              Impact if removed
            </button>
            <InfoTip id="insp.ifc-impact-buttons" />
          </div>
          <H3 info="insp.ifc-linked-calcs">Linked calcs ({ls.length})</H3>
          {ls.map((l) => {
            const c = ix.calcs.get(l.calc_key);
            if (!c) return null;
            return (
              <div className="ifc-link" key={l.calc_key}>
                <div className="ifc-link-top">
                  <span className="sw" style={{ background: c.color }} />
                  <button type="button" className="linkish t" onClick={() => p.onSelect({ kind: "calc", id: c.key })}>
                    {c.title}
                  </button>
                  {confChip(l)}
                </div>
                <div className="ifc-rule">
                  {l.rule}
                  {l.page ? ` · page ${l.page}` : ""}
                  {c.software ? ` · ${c.software}` : ""}
                  {l.decided_at ? ` · decided ${shortTime(l.decided_at)}` : ""}
                </div>
                {l.snippet && (
                  <div className="ifc-snip">
                    {l.snippet.before}
                    <mark>{l.snippet.match}</mark>
                    {l.snippet.after}
                  </div>
                )}
                <div className="ifc-acts">
                  {l.page != null && (
                    <button type="button" className="btn sm" onClick={() => p.onOpenPage(l.page!, l.rects)}>
                      Open page {l.page}
                    </button>
                  )}
                  {l.status === "auto" && (
                    <button type="button" className="btn sm" disabled={p.busy} onClick={() => p.onDecide(g, c.key, "confirm")}>
                      Confirm
                    </button>
                  )}
                  <button type="button" className="btn sm" disabled={p.busy} onClick={() => p.onDecide(g, c.key, "reject")}>
                    Reject
                  </button>
                </div>
              </div>
            );
          })}
          {!ls.length && (
            <div className="ifc-snip">
              No calc in the package names this element{el.mark ? ` ("${el.mark}")` : " (it has no Mark)"}, its size or its type.
            </div>
          )}
          <div className="ifc-acts" style={{ marginTop: 4 }}>
            <label className="sr-only" htmlFor="ifc-add-calc">
              Link to a calc by hand
            </label>
            <select
              id="ifc-add-calc"
              className="ifc-select"
              value=""
              disabled={p.busy}
              onChange={(e) => e.target.value && p.onDecide(g, e.target.value, "manual")}
            >
              <option value="">+ Link to a calc by hand…</option>
              {candidates.map((c) => (
                <option key={c.key} value={c.key}>
                  {c.title}
                </option>
              ))}
            </select>
            <InfoTip id="insp.ifc-manual-link" />
          </div>
          {rejected.length > 0 && (
            <>
              <H3 info="insp.ifc-rejected">Rejected</H3>
              {rejected.map((l) => (
                <div className="ifc-rule" key={l.calc_key}>
                  {ix.calcs.get(l.calc_key)?.title}{" "}
                  <button type="button" className="btn sm" disabled={p.busy} onClick={() => p.onDecide(g, l.calc_key, "undo")}>
                    undo
                  </button>
                </div>
              ))}
            </>
          )}
          <H3 info="insp.ifc-load-path">Load path</H3>
          <dl className="ifc-kv">
            <dt>Carries load from</dt>
            <dd>
              {up.length
                ? up.map((e, i) => (
                    <span key={i}>
                      {i > 0 && ", "}
                      <button type="button" className="linkish" title={e.rule} onClick={() => p.onSelect({ kind: "el", id: e.src }, true)}>
                        {nm(e.src)}
                      </button>
                    </span>
                  ))
                : "-"}
            </dd>
            <dt>Delivers load to</dt>
            <dd>
              {down.length
                ? down.map((e, i) => (
                    <span key={i}>
                      {i > 0 && ", "}
                      <button type="button" className="linkish" title={e.rule} onClick={() => p.onSelect({ kind: "el", id: e.dst }, true)}>
                        {nm(e.dst)}
                      </button>
                    </span>
                  ))
                : "-"}
            </dd>
          </dl>
          <H3 info="insp.ifc-element">Element</H3>
          <dl className="ifc-kv">
            <dt>Mark</dt>
            <dd>{el.mark || "-"}</dd>
            <dt>Name</dt>
            <dd>{el.name || "-"}</dd>
            <dt>Type</dt>
            <dd>{el.type_name || "-"}</dd>
            <dt>Size</dt>
            <dd>{el.profile || "-"}</dd>
            <dt>GlobalId</dt>
            <dd className="mono" style={{ fontSize: 11 }}>
              {el.global_id}
            </dd>
          </dl>
          {props.length > 0 && (
            <>
              <H3 info="insp.ifc-params">Parameters (open set)</H3>
              <dl className="ifc-kv">
                {props.map(([k, v]) => (
                  <div key={k} style={{ display: "contents" }}>
                    <dt>{k}</dt>
                    <dd>{v}</dd>
                  </div>
                ))}
              </dl>
            </>
          )}
          <div className="ifc-acts" style={{ marginTop: 14 }}>
            <button type="button" className="btn sm" onClick={() => p.onSelect(null)}>
              Back to summary
            </button>
          </div>
        </>
      );
    }
  }
  return (
    <div className="ifc-right">
      {ix && p.impact && <ImpactBox ix={ix} impact={p.impact} onClear={p.onClearImpact} onSelect={p.onSelect} />}
      <Panel title={title} info="panel.ifc-inspector" className="ifc-insp">
        {body}
      </Panel>
    </div>
  );
}
