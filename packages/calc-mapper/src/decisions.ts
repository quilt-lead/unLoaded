/**
 * The human decision log: append-only, keyed by (global_id, calc_key) - not by revision - so a
 * decision carries forward to every later revision while both keys exist. The latest decision
 * per pair wins; "undo" clears the pair. Port of the reference store + pipeline.effective_links.
 *
 * Every decision carries provenance with method "human": rule `decision.<action>`, the actor, the
 * time, and the documents it was made against when the caller knows them. A Decision is built only
 * by addDecision (a new one) or decisionFrom (one read back from storage or a file), so none lacks it.
 * A link a decision touched carries that decision's provenance as `review_provenance`; a hand link
 * ("manual") has it as its own provenance.
 */
import { RULES, humanProvenance } from "./provenance.ts";
import { DECISION_ACTIONS, type Decision, type DecisionFields, type DecisionIn, type Link } from "./types.ts";

/** Append a decision; returns a NEW log (the input is not mutated). Throws on an unknown action. */
export function addDecision(
  log: readonly Decision[], d: DecisionIn,
  ctx: { at?: string; model_rev?: string | number | null; calc_rev?: string | number | null; inputs?: readonly string[] } = {},
): Decision[] {
  const id = 1 + Math.max(0, ...log.map((x) => x.id));
  return [...log, decisionFrom({
    id, global_id: d.global_id, calc_key: d.calc_key, action: d.action, actor: d.actor ?? "reviewer",
    note: d.note ?? null, at: ctx.at ?? new Date().toISOString(), model_rev: ctx.model_rev ?? null,
    calc_rev: ctx.calc_rev ?? null,
  }, ctx.inputs)];
}

/**
 * A Decision from stored fields (a store record, a decision-log JSON file): the provenance it
 * carries, else the human provenance its own fields state (rule from the action, its actor and
 * time; `inputs` = the documents it was made against, when known). Throws on an unknown action.
 */
export function decisionFrom(d: DecisionFields, inputs: readonly string[] = []): Decision {
  if (!(DECISION_ACTIONS as readonly string[]).includes(d.action)) {
    throw new Error("action must be confirm | reject | manual | undo");
  }
  return { ...d, provenance: d.provenance ?? humanProvenance(RULES.decisions.action(d.action), d.actor, d.at, inputs) };
}

/** The latest decision per (global_id, calc_key), undone pairs dropped. Key: `${global_id}\0${calc_key}`. */
export function effectiveDecisions<D extends DecisionFields>(log: readonly D[]): Map<string, D> {
  const out = new Map<string, D>();
  for (const d of [...log].sort((p, q) => p.id - q.id)) out.set(`${d.global_id}\u0000${d.calc_key}`, d);
  for (const [k, d] of out) if (d.action === "undo") out.delete(k);
  return out;
}

/** Newest first (the backend's GET /decisions order). */
export function decisionLog(log: readonly Decision[]): Decision[] {
  return [...log].sort((p, q) => q.id - p.id);
}

/**
 * Auto links of a run with the decision log applied (copies; the run is not mutated). Decisions
 * whose element or calc no longer exists in `gids` / `calcKeys` are skipped (they stay in the log
 * and apply again if both keys come back).
 */
export function applyDecisions(links: readonly Link[], log: readonly DecisionFields[], gids: Set<string>, calcKeys: Set<string>): Link[] {
  const out = links.map((l): Link => {
    const copy: Link = { ...l, status: "auto" };
    delete copy.review_provenance;
    return copy;
  });
  const by = new Map(out.map((l) => [`${l.global_id}\u0000${l.calc_key}`, l]));
  for (const [k, raw] of effectiveDecisions(log)) {
    if (!gids.has(raw.global_id) || !calcKeys.has(raw.calc_key)) continue;
    const d = decisionFrom(raw); // keeps its provenance; derives it for a decision read from an older file
    let l = by.get(k);
    if (d.action === "confirm" && l) l.status = "confirmed";
    else if (d.action === "reject" && l) l.status = "rejected";
    else if (d.action === "manual") {
      if (l) l.status = "confirmed";
      else {
        l = {
          global_id: d.global_id, calc_key: d.calc_key, conf: 1.0, tier: "manual", rule: "Linked by hand", page: null,
          token: "", span: null, snippet: null, rects: [], status: "manual", role: "design", band: "high",
          evidence: [{ kind: "human", weight: 1, note: `linked by hand${d.actor ? " by " + d.actor : ""}${d.note ? ": " + d.note : ""}`, page: null, rects: [] }],
          caveats: [], provenance: d.provenance,
        };
        out.push(l);
        by.set(k, l);
      }
    }
    if (l && (d.action === "confirm" || d.action === "manual" || d.action === "reject")) {
      l.decided_at = d.at;
      l.decided_by = d.actor;
      l.review_provenance = d.provenance;
    }
  }
  return out;
}
