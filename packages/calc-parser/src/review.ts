/**
 * Human review on top of the automatic links, and the export report.
 * Ports of pipeline.effective_links / status_of / export and store.effective_decisions.
 *
 * Decisions are append-only and keyed by (GlobalId, calc key), not by link id, so
 * they carry forward to the next model or calc revision as long as both still exist.
 * Persisting them is the caller's job (the Python prototype used SQLite).
 */
import type { Calc, CalcEdge, CalcElement, CalcLink, Decision, LoadEdge } from './types.ts';

/** Calc colours, assigned by calc order. */
export const CALC_PALETTE = [
  '#4e79a7', '#f28e2b', '#59a14f', '#b07aa1', '#e15759', '#76b7b2', '#edc948', '#9c755f', '#ff9da7',
  '#2b8c8c', '#8f6ed5', '#d4a017', '#3d9970', '#c2185b', '#5f7d95',
] as const;

export const calcColor = (index: number): string => CALC_PALETTE[index % CALC_PALETTE.length]!;

const key = (gid: string, calcKey: string) => `${gid}\u0000${calcKey}`;

/** Latest decision per (GlobalId, calc key), in log order; an "undo" clears it. */
export function effectiveDecisions(log: readonly Decision[]): Map<string, Decision> {
  const out = new Map<string, Decision>();
  for (const d of log) out.set(key(d.global_id, d.calc_key), d);
  for (const [k, d] of out) if (d.action === 'undo') out.delete(k);
  return out;
}

/** Automatic links with the (carried-forward) human decisions applied. Returns new link objects. */
export function effectiveLinks(
  links: readonly CalcLink[],
  log: readonly Decision[],
  gids: ReadonlySet<string>,
  calcKeys: ReadonlySet<string>,
): CalcLink[] {
  const out = links.map((l) => ({ ...l, status: l.status ?? 'auto' }));
  const by = new Map(out.map((l) => [key(l.global_id, l.calc_key), l]));
  for (const d of effectiveDecisions(log).values()) {
    const { global_id: g, calc_key: k } = d;
    if (!gids.has(g) || !calcKeys.has(k)) continue; // element or calc no longer exists in the head revisions
    let l = by.get(key(g, k));
    if (d.action === 'confirm' && l) l.status = 'confirmed';
    else if (d.action === 'reject' && l) l.status = 'rejected';
    else if (d.action === 'manual') {
      if (l) l.status = 'confirmed';
      else {
        l = {
          global_id: g,
          calc_key: k,
          conf: 1.0,
          tier: 'manual',
          rule: 'Linked by hand',
          page: null,
          token: '',
          span: null,
          snippet: null,
          rects: [],
          status: 'manual',
        };
        out.push(l);
        by.set(key(g, k), l);
      }
    }
    if (l && (d.action === 'confirm' || d.action === 'manual' || d.action === 'reject')) {
      l.decided_at = d.at;
      l.decided_by = d.actor ?? null;
    }
  }
  return out;
}

export type MappingStatus = 'confirmed' | 'review' | 'unmapped';

/** An element's mapping status from its links: confirmed, needs review, or unmapped. */
export function statusOf(links: ReadonlyArray<Pick<CalcLink, 'status' | 'conf'>>): MappingStatus {
  const live = links.filter((l) => l.status !== 'rejected');
  if (!live.length) return 'unmapped';
  return live.some((l) => l.status === 'confirmed' || l.status === 'manual' || l.conf >= 0.8) ? 'confirmed' : 'review';
}

export function mappingStatuses(
  elements: readonly CalcElement[],
  links: readonly CalcLink[],
): { byElement: Map<string, MappingStatus>; counts: Record<MappingStatus, number> } {
  const perEl = new Map<string, CalcLink[]>();
  for (const l of links) (perEl.get(l.global_id) ?? perEl.set(l.global_id, []).get(l.global_id)!).push(l);
  const counts: Record<MappingStatus, number> = { confirmed: 0, review: 0, unmapped: 0 };
  const byElement = new Map<string, MappingStatus>();
  for (const e of elements) {
    const s = statusOf(perEl.get(e.global_id) ?? []);
    byElement.set(e.global_id, s);
    counts[s] += 1;
  }
  return { byElement, counts };
}

export interface ExportInput {
  model?: string | null;
  modelRevision?: string | number | null;
  calcPackage?: string | null;
  calcRevision?: string | number | null;
  engine: string;
  elements: ReadonlyArray<CalcElement & { ifc_type?: string }>;
  calcs: readonly Calc[];
  links: readonly CalcLink[];
  calcEdges: readonly CalcEdge[];
  loadPath?: ReadonlyArray<LoadEdge & { rule?: string }>;
}

/** The mapping report (same shape as the prototype's /export endpoint). */
export function exportMapping(s: ExportInput) {
  const cal = new Map(s.calcs.map((c) => [c.key, c]));
  const perEl = new Map<string, CalcLink[]>();
  for (const l of s.links) (perEl.get(l.global_id) ?? perEl.set(l.global_id, []).get(l.global_id)!).push(l);
  const { byElement } = mappingStatuses(s.elements, s.links);
  return {
    model: s.model ?? null,
    model_revision: s.modelRevision ?? null,
    calc_package: s.calcPackage ?? null,
    calc_revision: s.calcRevision ?? null,
    engine: s.engine,
    calcs: s.calcs.map((c) => ({
      key: c.key,
      title: c.title,
      software: c.software,
      element_type: c.cat,
      pages: c.pages,
      scanned: c.scanned,
      front_matter: c.front,
    })),
    calc_edges: s.calcEdges.map((e) => ({ src: e.src, dst: e.dst, rules: e.rules })),
    load_path: (s.loadPath ?? []).map((e) => ({ src: e.src, dst: e.dst, rule: e.rule ?? '' })),
    elements: s.elements.map((e) => ({
      global_id: e.global_id,
      ifc_type: e.ifc_type ?? '',
      mark: e.mark,
      storey: e.storey,
      size: e.profile,
      status: byElement.get(e.global_id)!,
      calcs: [...(perEl.get(e.global_id) ?? [])]
        .sort((a, b) => b.conf - a.conf)
        .map((l) => ({
          calc: l.calc_key,
          title: cal.get(l.calc_key)?.title ?? '',
          page: l.page,
          confidence: Math.round(l.conf * 100) / 100,
          tier: l.tier,
          rule: l.rule,
          matched_text: l.token,
          review: l.status ?? 'auto',
        })),
    })),
  };
}
