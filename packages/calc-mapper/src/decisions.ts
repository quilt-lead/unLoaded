/**
 * The human decision log: append-only, keyed by (global_id, calc_key) - not by revision - so a
 * decision carries forward to every later revision while both keys exist. The latest decision
 * per pair wins; "undo" clears the pair. Port of the reference store + pipeline.effective_links.
 */
import type { Decision, DecisionIn, Link } from "./types.ts";

export const DECISION_ACTIONS = ["confirm", "reject", "manual", "undo"] as const;

/** Append a decision; returns a NEW log (the input is not mutated). Throws on an unknown action. */
export function addDecision(
  log: readonly Decision[], d: DecisionIn,
  ctx: { at?: string; model_rev?: string | number | null; calc_rev?: string | number | null } = {},
): Decision[] {
  if (!(DECISION_ACTIONS as readonly string[]).includes(d.action)) {
    throw new Error("action must be confirm | reject | manual | undo");
  }
  const id = 1 + Math.max(0, ...log.map((x) => x.id));
  return [...log, {
    id, global_id: d.global_id, calc_key: d.calc_key, action: d.action, actor: d.actor ?? "reviewer",
    note: d.note ?? null, at: ctx.at ?? new Date().toISOString(), model_rev: ctx.model_rev ?? null,
    calc_rev: ctx.calc_rev ?? null,
  }];
}

/** The latest decision per (global_id, calc_key), undone pairs dropped. Key: `${global_id}\0${calc_key}`. */
export function effectiveDecisions(log: readonly Decision[]): Map<string, Decision> {
  const out = new Map<string, Decision>();
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
export function applyDecisions(links: readonly Link[], log: readonly Decision[], gids: Set<string>, calcKeys: Set<string>): Link[] {
  const out = links.map((l) => ({ ...l, status: "auto" as Link["status"] }));
  const by = new Map(out.map((l) => [`${l.global_id}\u0000${l.calc_key}`, l]));
  for (const [k, d] of effectiveDecisions(log)) {
    if (!gids.has(d.global_id) || !calcKeys.has(d.calc_key)) continue;
    let l = by.get(k);
    if (d.action === "confirm" && l) l.status = "confirmed";
    else if (d.action === "reject" && l) l.status = "rejected";
    else if (d.action === "manual") {
      if (l) l.status = "confirmed";
      else {
        l = {
          global_id: d.global_id, calc_key: d.calc_key, conf: 1.0, tier: "manual", rule: "Linked by hand", page: null,
          token: "", span: null, snippet: null, rects: [], status: "manual",
        };
        out.push(l);
        by.set(k, l);
      }
    }
    if (l && (d.action === "confirm" || d.action === "manual" || d.action === "reject")) {
      l.decided_at = d.at;
      l.decided_by = d.actor;
    }
  }
  return out;
}
