/**
 * Facts -> ModelInput: levels with elevations, one element per content id (every occurrence of it
 * merged in), drawing-derived geometry in metres, and the callout relations.
 */
import {
  MODEL_INPUT_VERSION, type BBox, type ElementInput, type GeometrySummary, type LevelInput, type ModelInput,
  type ParamValue, type RelationInput, type Vec3,
} from "@unloaded/element-graph/input";
import type { ColumnTierFact, ConnectionFact, Facts, LevelStatement, MemberFact, PointFact, ScheduleRow } from "./facts.ts";
import type { BuildingGrid } from "./grid.ts";
import { feetInches, FT, nominalSection, r2, slug } from "./text.ts";
import type { Occurrence, Sheet } from "./types.ts";

export const SOURCE_FORMAT = "drawing";
const IN = 0.0254;
const round6 = (v: number) => Math.round(v * 1e6) / 1e6;
const v3 = (x: number, y: number, z: number): Vec3 => [round6(x), round6(y), round6(z)];

export interface AssembleInput {
  facts: Facts;
  sheets: Sheet[];
  grid?: BuildingGrid;
  files: string[];
  /** Per sheet: how its scale was found and the residual, for the precision params. */
  calibration: Map<string, { source: string; ftPerPt: number; rmsResidualIn?: number }>;
}

export interface Level {
  name: string;
  id: string;
  ft: number;
  stated: boolean;
  /** Unstated levels: how the elevation was assumed. */
  assumed?: string;
}

/** Most frequent stated value (1/16 in buckets); conflicts become warnings. */
function vote(st: LevelStatement[], what: string, warnings: string[]): number | undefined {
  if (!st.length) return undefined;
  const n = new Map<number, number>();
  for (const s of st) {
    const k = Math.round(s.ft * 192) / 192;
    n.set(k, (n.get(k) ?? 0) + 1);
  }
  const ranked = [...n.entries()].sort((a, b) => b[1] - a[1] || a[0] - b[0]);
  if (ranked.length > 1) warnings.push(`${what}: conflicting elevations stated (${ranked.map(([v, c]) => `${r2(v)} ft x${c}`).join(", ")}); using the most frequent`);
  return ranked[0]![0];
}

/**
 * Bottom-up order of a level name (levelName's vocabulary): Foundation, Basement n (Basement 2 below
 * Basement 1), Level n (a lettered Level 2A just above Level 2), Mezzanine n (above Level n, below
 * Level n+1; no number = above Level 1), Penthouse, Roof, Penthouse Roof (the roof over the
 * penthouse, above the main roof). NaN for a name outside that vocabulary.
 */
export function levelOrder(name: string): number {
  let m = /^Level (\d+)([A-Z])?$/.exec(name);
  if (m) return Number(m[1]) + (m[2] ? (m[2].charCodeAt(0) - 64) / 100 : 0);
  if (name === "Foundation") return -1000;
  m = /^Basement(?: (\d+))?$/.exec(name);
  if (m) return -Number(m[1] ?? 1);
  m = /^Mezzanine(?: (\d+))?$/.exec(name);
  if (m) return Number(m[1] ?? 1) + 0.5;
  m = /^Penthouse(?: (\d+))?$/.exec(name);
  if (m) return 999 + Number(m[1] ?? 0) / 100;
  if (name === "Roof") return 1000;
  if (name === "Penthouse Roof") return 1001;
  return NaN;
}

/**
 * Does the name alone fix where the level sits among the others? Numbered levels, basements and
 * mezzanines, the foundation and the roofs do. An unnumbered Mezzanine or Penthouse (which storey it
 * is over is a guess) and a name outside the vocabulary do not: once such a level's elevation is
 * stated, the elevation places it, and it never brackets another level by name.
 */
export function nameFixesOrder(name: string): boolean {
  return !Number.isNaN(levelOrder(name)) && name !== "Mezzanine" && name !== "Penthouse";
}

/** Storey height assumed above / below the nearest level when nothing brackets an unstated one, ft. */
const ASSUMED_STOREY_FT = 12;

/**
 * Levels with elevations. Stated elevations place their levels (the order is by elevation, never by
 * name). An unstated level is placed between the stated levels its NAME puts it between - the
 * highest stated level named below it and the lowest stated level named above it, counting only
 * names that fix their order (`nameFixesOrder`) - evenly, with any other unstated levels in the same
 * gap in name order; with nothing stated above, 12 ft storeys up from the one below; with nothing
 * below, 12 ft storeys down. An unstated foundation is 3 ft below the lowest level by elevation.
 * Every assumption is warned and labelled on the level (`assumed`). The map iterates bottom-up.
 */
export function buildLevels(facts: Facts, sheets: Sheet[], warnings: string[]): Map<string, Level> {
  const names = new Set<string>();
  for (const s of sheets) if (s.level) names.add(s.level);
  for (const l of facts.levels) names.add(l.level);
  for (const t of facts.tiers) names.add(t.lo).add(t.hi);
  for (const m of facts.members) {
    names.add(m.level);
    if (m.topLevel) names.add(m.topLevel);
  }
  const order = (n: string) => {
    const o = levelOrder(n);
    return Number.isNaN(o) ? 500 : o;
  };
  const byName = (a: string, b: string) => order(a) - order(b) || a.localeCompare(b);
  for (const n of names) if (Number.isNaN(levelOrder(n))) warnings.push(`level ${n}: name has no known storey order; placed by its stated elevation, else after the numbered levels`);
  const all: Level[] = [];
  const tof = vote(facts.datums.filter((d) => d.level === "top of footing"), "top of footing", warnings);
  for (const name of [...names].sort(byName)) {
    let ft = vote(facts.levels.filter((l) => l.level === name), name, warnings);
    if (ft === undefined && name === "Foundation") ft = tof;
    all.push({ name, id: slug(name), ft: ft ?? NaN, stated: ft !== undefined });
  }
  // brackets: stated levels other than the foundation whose name fixes their order
  const anchors = all.filter((l) => l.stated && l.name !== "Foundation" && nameFixesOrder(l.name));
  for (const a of anchors)
    for (const b of anchors)
      if (order(a.name) < order(b.name) && a.ft >= b.ft)
        warnings.push(`levels ${a.name} (${r2(a.ft)} ft) and ${b.name} (${r2(b.ft)} ft): stated elevations contradict the storey order of their names`);
  // unstated levels grouped by the gap they fall in, each gap filled in name order
  const gaps = new Map<string, { lo?: Level; hi?: Level; levels: Level[] }>();
  for (const l of all) {
    if (l.stated || l.name === "Foundation") continue;
    const below = anchors.filter((a) => order(a.name) < order(l.name)).sort((p, q) => q.ft - p.ft)[0];
    let above = anchors.filter((a) => order(a.name) > order(l.name)).sort((p, q) => p.ft - q.ft)[0];
    if (below && above && above.ft <= below.ft) above = undefined; // contradictory statements (warned): step up from below
    const key = `${below?.name ?? ""}|${above?.name ?? ""}`;
    const g = gaps.get(key) ?? gaps.set(key, { ...(below ? { lo: below } : {}), ...(above ? { hi: above } : {}), levels: [] }).get(key)!;
    g.levels.push(l);
  }
  for (const { lo, hi, levels: ls } of gaps.values()) {
    const n = ls.length;
    ls.forEach((l, k) => {
      if (lo && hi) {
        l.ft = lo.ft + ((hi.ft - lo.ft) * (k + 1)) / (n + 1);
        l.assumed = `evenly between ${lo.name} and ${hi.name}`;
      } else if (lo) {
        l.ft = lo.ft + ASSUMED_STOREY_FT * (k + 1);
        l.assumed = `${ASSUMED_STOREY_FT * (k + 1)} ft above ${lo.name} (${ASSUMED_STOREY_FT} ft storeys assumed)`;
      } else if (hi) {
        l.ft = hi.ft - ASSUMED_STOREY_FT * (n - k);
        l.assumed = `${ASSUMED_STOREY_FT * (n - k)} ft below ${hi.name} (${ASSUMED_STOREY_FT} ft storeys assumed)`;
      } else {
        l.ft = ASSUMED_STOREY_FT * k;
        l.assumed = k === 0 ? "no level elevation stated in the set: lowest level at 0 ft" : `${ASSUMED_STOREY_FT * k} ft above the lowest level (${ASSUMED_STOREY_FT} ft storeys assumed)`;
      }
    });
  }
  const fdn = all.find((l) => l.name === "Foundation");
  if (fdn && !fdn.stated) {
    const lowest = all.filter((l) => l !== fdn).sort((p, q) => p.ft - q.ft || byName(p.name, q.name))[0];
    fdn.ft = (lowest?.ft ?? 0) - 3;
    fdn.assumed = `3 ft below ${lowest?.name ?? "the lowest level"}`;
  }
  const out = new Map<string, Level>();
  for (const l of all.sort((p, q) => p.ft - q.ft || byName(p.name, q.name))) out.set(l.name, l);
  for (const l of out.values()) if (l.assumed) warnings.push(`level ${l.name}: no elevation stated in the set; assumed ${r2(l.ft)} ft (${l.assumed})`);
  return out;
}

const occJson = (os: Occurrence[]) => JSON.stringify(os.map((o) => ({ file: o.file, sheet: o.sheet, page: o.page, rect: o.rect, how: o.how, text: o.text })));

function dedupeOcc(os: Occurrence[]): Occurrence[] {
  const seen = new Set<string>();
  const out: Occurrence[] = [];
  for (const o of os) {
    const k = `${o.file}|${o.page}|${o.rect.join(",")}|${o.how}`;
    if (seen.has(k)) continue;
    seen.add(k);
    out.push(o);
  }
  // plan / elevation tags first, then schedules, callouts, notes; then by sheet order
  const rank: Record<string, number> = { plan_tag: 0, elevation_tag: 1, schedule_row: 2, detail_callout: 3, note: 4 };
  return out.sort((a, b) => (rank[a.how]! - rank[b.how]!) || a.file.localeCompare(b.file) || a.page - b.page || a.rect[1] - b.rect[1] || a.rect[0] - b.rect[0]);
}

function bboxOf(points: Vec3[], pad: [number, number, number]): BBox {
  const min = [0, 1, 2].map((k) => Math.min(...points.map((p) => p[k]!)) - pad[k]!);
  const max = [0, 1, 2].map((k) => Math.max(...points.map((p) => p[k]!)) + pad[k]!);
  return { min: v3(min[0]!, min[1]!, min[2]!), max: v3(max[0]!, max[1]!, max[2]!) };
}

interface Draft {
  id: string;
  kind: string;
  mark?: string;
  name?: string;
  profile?: string;
  levelId?: string;
  params: Record<string, ParamValue>;
  geometry?: GeometrySummary;
  occ: Occurrence[];
}

export function assemble(inp: AssembleInput): ModelInput {
  const { facts, sheets, grid } = inp;
  const warnings = [...facts.warnings];
  const levels = buildLevels(facts, sheets, warnings);
  const lvl = (name: string) => levels.get(name)!;
  const z = (name: string) => lvl(name).ft * FT;
  const drafts = new Map<string, Draft>();
  const relations: RelationInput[] = [];
  const rowsByMark = new Map<string, ScheduleRow[]>();
  for (const r of facts.rows) rowsByMark.set(r.mark, [...(rowsByMark.get(r.mark) ?? []), r]);
  const tof = vote(facts.datums.filter((d) => d.level === "top of footing"), "top of footing", []);
  const topOfPier = vote(facts.datums.filter((d) => d.level === "top of pier"), "top of pier", []);
  const foundationZ = (tof ?? (levels.has("Foundation") ? lvl("Foundation").ft : 0)) * FT;
  // scale provenance: the sheet the element was first read on, else the reference plan its grid came from
  const refSheet = grid ? sheets.find((s) => s.number === grid.reference) : undefined;
  const precision = (o: Occurrence) =>
    inp.calibration.get(`${o.file}|${o.page}`) ?? (refSheet ? inp.calibration.get(`${refSheet.file}|${refSheet.page}`) : undefined);

  const draft = (id: string, kind: string, o: Occurrence): Draft => {
    let d = drafts.get(id);
    if (!d) {
      d = { id, kind, params: {}, occ: [] };
      drafts.set(id, d);
    }
    d.occ.push(o);
    return d;
  };
  const setProfile = (d: Draft, profile: string | undefined, o: Occurrence) => {
    if (!profile) return;
    if (d.profile && d.profile !== profile) {
      warnings.push(`${d.id}: size ${profile} on ${o.sheet} differs from ${d.profile}; kept ${d.profile}`);
      d.params["Drawing.SizeConflict"] = `${d.profile} vs ${profile} (${o.sheet})`;
      return;
    }
    d.profile = profile;
  };

  // ------------------------------------------------------------ linear members
  for (const m of facts.members) {
    const d = draft(m.id, m.kind, m.occ);
    setProfile(d, m.tag?.profile, m.occ);
    if (m.mark) d.mark = m.mark;
    d.levelId = lvl(m.level).id;
    // a plan reading (girder / infill / grade beam) names the role better than an elevation's "frame_beam"
    const prevRole = d.params["Drawing.Role"];
    d.params["Drawing.Role"] = prevRole === undefined || prevRole === "frame_beam" ? m.role : prevRole;
    d.params["Drawing.Grid"] = m.grid;
    if (m.tag?.sfrs) d.params["Drawing.SFRS"] = true;
    if (m.tag?.studs !== undefined) d.params["Drawing.Studs"] = m.tag.studs;
    if (m.tag?.camberIn !== undefined) d.params["Drawing.CamberIn"] = m.tag.camberIn;
    const fr = facts.frames.get(m.id);
    if (fr) d.params["Drawing.FrameSystem"] = fr;
    d.params[`Drawing.Rule.${m.occ.how}`] = m.rule;
    d.params["Drawing.PlanErrorM"] = r2(Math.max(Number(d.params["Drawing.PlanErrorM"] ?? 0), m.planErrFt * FT) * 1000) / 1000;
    (d as Draft & { member?: MemberFact }).member ??= m;
  }

  // ------------------------------------------------------------ columns: one element per storey segment
  const tiersAt = new Map<string, ColumnTierFact[]>();
  for (const t of facts.tiers) tiersAt.set(t.at, [...(tiersAt.get(t.at) ?? []), t]);
  const pierAt = new Map<string, PointFact[]>();
  for (const p of facts.points) if (p.role === "pier") pierAt.set(p.at, [...(pierAt.get(p.at) ?? []), p]);
  // intersection -> its lowest segment: what "column:<intersection>" (a base plate, a base callout) means
  const stackBottom = new Map<string, string>();
  for (const [at, ts] of tiersAt) {
    // segments between every level this column's storeys start or end at, bottom-up. The id is position +
    // storey (`column:1/A:level-1..level-2`), never the size, so a resize keeps every id; each segment
    // carries its own storey's size and level, so a calc row for an upper storey matches its segment
    const bounds = [...new Set(ts.flatMap((t) => [t.lo, t.hi]))].sort((p, q) => lvl(p).ft - lvl(q).ft || p.localeCompare(q));
    const segs = bounds.slice(0, -1).map((lo, i) => ({ lo, hi: bounds[i + 1]! })).filter((g) => lvl(g.hi).ft > lvl(g.lo).ft);
    const covers = (t: ColumnTierFact, g: { lo: string; hi: string }) => {
      const [a0, a1] = [lvl(t.lo).ft, lvl(t.hi).ft].sort((p, q) => p - q) as [number, number];
      return a0 <= lvl(g.lo).ft + 1e-9 && lvl(g.hi).ft <= a1 + 1e-9;
    };
    for (const g of segs) {
      const mine = ts.filter((t) => covers(t, g));
      if (!mine.length) {
        warnings.push(`column ${at}: no storey stated between ${g.lo} and ${g.hi}; no element there`);
        continue;
      }
      const id = `column:${at}:${slug(g.lo)}..${slug(g.hi)}`;
      const bottom = !stackBottom.has(at);
      if (bottom) stackBottom.set(at, id);
      for (const t of mine) {
        const d = draft(id, "column", t.occ);
        setProfile(d, t.tag?.profile, t.occ);
        if (t.tag?.sfrs) d.params["Drawing.SFRS"] = true;
        d.params[`Drawing.Rule.${t.occ.how}`] = t.rule;
      }
      const d = drafts.get(id)!;
      d.levelId = lvl(g.lo).id;
      d.params["Drawing.Role"] = "column";
      d.params["Drawing.Grid"] = at;
      d.params["Drawing.Storeys"] = `${g.lo} - ${g.hi}`;
      if (grid) {
        const [xl, yl] = at.split("/") as [string, string];
        const x = grid.x.get(xl)! * FT, y = grid.y.get(yl)! * FT;
        const onPier = bottom && pierAt.has(at) && topOfPier !== undefined;
        const z0 = onPier ? topOfPier! * FT : z(g.lo);
        const z1 = z(g.hi);
        const sec = d.profile ? nominalSection(d.profile) : undefined;
        const w = sec ? Math.max(sec.depth, sec.width) : 0.3;
        d.geometry = {
          bbox: bboxOf([v3(x, y, z0), v3(x, y, z1)], [w / 2, w / 2, 0]),
          axis: { start: v3(x, y, z0), end: v3(x, y, z1) },
          ...(sec ? { section: { depth: round6(sec.depth), width: round6(sec.width) } } : {}),
        };
        d.params["Drawing.GeometryRule"] = `at grid intersection ${at}; from ${onPier ? "the top of pier (foundation note)" : g.lo} to ${g.hi}` +
          (sec ? "; section from the nominal designation" : "; section unknown (0.3 m assumed)");
      }
    }
  }
  /** A column reference by intersection ("column:1/A") is its lowest segment; any other id is itself. */
  const columnRef = (id: string): string => {
    const m = /^column:([^:]+)$/.exec(id);
    return (m && stackBottom.get(m[1]!)) ?? id;
  };

  // ------------------------------------------------------------ footings and piers
  for (const p of facts.points) {
    const d = draft(p.id, p.kind, p.occ);
    if (p.mark && !d.mark) d.mark = p.mark;
    else if (p.mark && d.mark !== p.mark) warnings.push(`${p.id}: mark ${p.mark} on ${p.occ.sheet} differs from ${d.mark}`);
    d.params["Drawing.Role"] = p.role;
    d.params["Drawing.Grid"] = p.at;
    d.params[`Drawing.Rule.${p.occ.how}`] = p.rule;
    if (levels.has("Foundation")) d.levelId = lvl("Foundation").id;
  }

  // ------------------------------------------------------------ connections
  const memberOf = new Map<string, ConnectionFact[]>();
  for (const c of facts.connections) {
    const d = draft(c.id, "connection", c.occ);
    const basePlate = c.member.startsWith("column:") && c.end === "base";
    d.params["Drawing.Role"] = basePlate ? "base_plate" : "connection";
    d.params["Drawing.Member"] = columnRef(c.member);
    if (basePlate) d.params["Drawing.Grid"] = c.member.slice("column:".length);
    d.params["Drawing.End"] = c.end;
    if (c.type) {
      d.mark ??= c.type;
      if (d.mark !== c.type) d.params["Drawing.TypeConflict"] = `${d.mark} vs ${c.type} (${c.occ.sheet})`;
    }
    if (c.detailRef) {
      const refs = new Set(String(d.params["Detail.Refs"] ?? "").split(" ").filter(Boolean));
      refs.add(c.detailRef);
      d.params["Detail.Refs"] = [...refs].sort().join(" ");
    }
    if (c.attribution) d.params["Drawing.CalloutAttribution"] = c.attribution;
    if (c.distPt !== undefined) d.params["Drawing.CalloutDistancePt"] = c.distPt;
    if (c.runnerUp) {
      d.params["Drawing.CalloutAmbiguous"] = true;
      d.params["Drawing.CalloutRunnerUp"] = `${c.runnerUp} (${c.runnerUpDistPt} pt)`;
    }
    d.params[`Drawing.Rule.${c.occ.how}`] = c.rule;
    memberOf.set(c.id, [...(memberOf.get(c.id) ?? []), c]);
  }
  // detail panels by type mark: base plates named by their schedule cell get their detail too
  const detailByType = new Map<string, { ref: string; title: string }>();
  for (const dp of facts.details.values()) if (dp.type && !detailByType.has(dp.type)) detailByType.set(dp.type, dp);
  for (const [id, cs] of memberOf) {
    const d = drafts.get(id)!;
    const det = cs.map((c) => (c.detailRef ? facts.details.get(c.detailRef) : undefined)).find(Boolean) ?? (d.mark ? detailByType.get(d.mark) : undefined);
    if (det) {
      d.params["Detail.Title"] = det.title;
      d.params["Detail.Ref"] = det.ref;
      d.name = det.title;
    }
  }

  // ------------------------------------------------------------ slabs
  for (const s of facts.slabs) {
    const d = draft(`slab:${slug(s.level)}`, "slab", s.occ);
    d.levelId = lvl(s.level).id;
    d.name = s.text.length > 120 ? `${s.text.slice(0, 117)}...` : s.text;
    d.params["Drawing.Role"] = "deck";
    if (s.thicknessIn) d.params["Drawing.ThicknessIn"] = s.thicknessIn;
    if (s.thicknessRule) d.params["Drawing.ThicknessRule"] = s.thicknessRule;
  }

  // ------------------------------------------------------------ schedules by mark
  for (const d of drafts.values()) {
    const rows = d.mark ? rowsByMark.get(d.mark) : undefined;
    if (!rows) continue;
    for (const r of rows) d.occ.push(r.occ);
    d.params["Schedule.Text"] = [...new Set(rows.map((r) => r.text))].join(" | ");
  }

  // ------------------------------------------------------------ geometry for members, foundations, connections, slabs
  if (grid) {
    const xsFt = [...grid.x.values()], ysFt = [...grid.y.values()];
    for (const d of drafts.values()) {
      const m = (d as Draft & { member?: MemberFact }).member;
      if (m) memberGeometry(d, m);
      else if (d.kind === "footing" || (d.kind === "column" && d.params["Drawing.Role"] === "pier")) pointGeometry(d);
      else if (d.kind === "slab") {
        const lv = [...levels.values()].find((l) => l.id === d.levelId)!;
        const t = Number(d.params["Drawing.ThicknessIn"] ?? 6) * IN;
        const zz = lv.ft * FT;
        d.geometry = { bbox: { min: v3(Math.min(...xsFt) * FT, Math.min(...ysFt) * FT, zz), max: v3(Math.max(...xsFt) * FT, Math.max(...ysFt) * FT, zz + t) } };
        d.params["Drawing.GeometryRule"] = "grid extents at the level (top of steel up); thickness from the deck note" + (d.params["Drawing.ThicknessIn"] ? "" : " (6 in assumed)");
      }
    }
    // connections after members (they sit at member ends)
    for (const d of drafts.values()) if (d.kind === "connection") connectionGeometry(d);
  }
  // the stated relations, with or without geometry: callout / schedule row -> the member it names
  for (const d of drafts.values()) {
    if (d.kind !== "connection") continue;
    const member = String(d.params["Drawing.Member"]);
    if (drafts.has(member)) relations.push(rel(d.id, member, d));
    else warnings.push(`${d.id}: ${member} is not an element (no size read for it); relation not emitted`);
  }

  function memberGeometry(d: Draft, m: MemberFact) {
    const role = d.params["Drawing.Role"];
    let section = d.profile ? nominalSection(d.profile) : undefined;
    let ruleSec = section ? "section from the nominal designation" : "section unknown (0.3 x 0.15 m assumed)";
    if (role === "grade_beam") {
      const dims = gradeBeamDims(d);
      section = dims ?? { depth: 0.6, width: 0.45 };
      ruleSec = dims ? "section from the grade beam schedule" : "section unknown (0.45 x 0.6 m assumed)";
    }
    const sec = section ?? { depth: 0.3, width: 0.15 };
    const [ax, ay] = m.a, [bx, by] = m.b;
    // physical extent (bbox); the axis stays the analytical line grid to grid, as the plan states it
    let qax = ax, qay = ay, qbx = bx, qby = by;
    let trimmed = "";
    if (role === "grade_beam") {
      // a grade beam frames into the footings at its ends: its body runs between the footing faces, so
      // it does not pass under the pier (the pier then bears on its footing, not on the grade beam)
      const L = Math.hypot(bx - ax, by - ay) || 1;
      const ux = (bx - ax) / L, uy = (by - ay) / L;
      const halfFooting = (end: string) => {
        const at = Math.abs(ux) > Math.abs(uy)
          ? `${end}/${m.grid.split("/")[0]}` : `${m.grid.split("/")[0]}/${end}`;
        const f = drafts.get(`footing:${at}`);
        const ft = f ? feetInches(String(f.params["Schedule.Text"] ?? "")) : [];
        return ft.length >= 3 ? ft[0]! / 2 : 0;
      };
      const ta = halfFooting(m.ends[0]), tb = halfFooting(m.ends[1]);
      if (ta || tb) {
        qax = ax + ux * ta;
        qay = ay + uy * ta;
        qbx = bx - ux * tb;
        qby = by - uy * tb;
        trimmed = "; axis grid line to grid line, body (bbox) between the footing faces (footing schedule sizes)";
      }
    }
    let za: number, zb: number;
    if (m.kind === "brace") {
      za = z(m.level);
      zb = z(m.topLevel ?? m.level);
    } else {
      za = zb = role === "grade_beam" ? foundationZ : z(m.level);
    }
    const start = v3(ax * FT, ay * FT, m.kind === "brace" ? za : za - sec.depth / 2);
    const end = v3(bx * FT, by * FT, m.kind === "brace" ? zb : zb - sec.depth / 2);
    const alongX = Math.abs(bx - ax) >= Math.abs(by - ay);
    const half = sec.width / 2;
    d.geometry = {
      bbox: m.kind === "brace"
        ? bboxOf([start, end], [alongX ? 0 : half, alongX ? half : 0, half])
        : bboxOf([v3(qax * FT, qay * FT, za), v3(qbx * FT, qby * FT, za - sec.depth)], [alongX ? 0 : half, alongX ? half : 0, 0]),
      axis: { start, end },
      section: { depth: round6(sec.depth), width: round6(sec.width) },
    };
    d.params["Drawing.GeometryRule"] = (m.kind === "brace"
      ? `between ${m.level} and ${m.topLevel}`
      : role === "grade_beam" ? `top at the top of footing${trimmed}` : `top of steel at ${m.level}`) + `; ${ruleSec}`;
  }

  function gradeBeamDims(d: Draft): { depth: number; width: number } | undefined {
    const t = String(d.params["Schedule.Text"] ?? "");
    const m = /^\S+\s+(\d+)"\s*(?:x\s*)?(\d+)"/.exec(t);
    return m ? { width: Number(m[1]) * IN, depth: Number(m[2]) * IN } : undefined;
  }

  function pointGeometry(d: Draft) {
    const at = String(d.params["Drawing.Grid"]);
    const [xl, yl] = at.split("/") as [string, string];
    if (!grid!.x.has(xl) || !grid!.y.has(yl)) return;
    const x = grid!.x.get(xl)! * FT, y = grid!.y.get(yl)! * FT;
    const sched = String(d.params["Schedule.Text"] ?? "");
    if (d.kind === "footing") {
      const ft = feetInches(sched);
      const [L, W, T] = ft.length >= 3 ? ft : [5, 5, 1.5];
      d.geometry = { bbox: { min: v3(x - (L! * FT) / 2, y - (W! * FT) / 2, foundationZ - T! * FT), max: v3(x + (L! * FT) / 2, y + (W! * FT) / 2, foundationZ) } };
      d.params["Drawing.GeometryRule"] = `centred on grid intersection ${at}; top at the top of footing` + (ft.length >= 3 ? "; L x W x T from the footing schedule" : "; size unknown (5 x 5 x 1.5 ft assumed)");
    } else {
      const m = /^\S+\s+(\d+)"\s*x\s*(\d+)"/.exec(sched);
      const b = m ? Number(m[1]) * IN : 0.6;
      const top = (topOfPier ?? lvl([...levels.values()].sort((p, q) => p.ft - q.ft).find((l) => l.name !== "Foundation")?.name ?? "Foundation").ft) * FT;
      d.geometry = {
        bbox: { min: v3(x - b / 2, y - b / 2, foundationZ), max: v3(x + b / 2, y + b / 2, top) },
        axis: { start: v3(x, y, foundationZ), end: v3(x, y, top) },
        section: { depth: round6(b), width: round6(b) },
      };
      d.params["Drawing.GeometryRule"] = `centred on grid intersection ${at}; from the top of footing to the top of pier` + (m ? "; size from the pier schedule" : "; size unknown (0.6 m assumed)");
    }
  }

  function connectionGeometry(d: Draft) {
    const member = String(d.params["Drawing.Member"]);
    const end = String(d.params["Drawing.End"]);
    if (d.params["Drawing.Role"] === "base_plate") {
      const col = drafts.get(member);
      const at = String(d.params["Drawing.Grid"]);
      const [xl, yl] = at.split("/") as [string, string];
      if (!grid!.x.has(xl) || !grid!.y.has(yl)) return;
      const x = grid!.x.get(xl)! * FT, y = grid!.y.get(yl)! * FT;
      const zb = col?.geometry?.axis?.start[2] ?? (topOfPier !== undefined ? topOfPier * FT : foundationZ);
      d.geometry = { bbox: { min: v3(x - 0.25, y - 0.25, zb - 0.04), max: v3(x + 0.25, y + 0.25, zb + 0.04) } };
      d.params["Drawing.GeometryRule"] = `plate at the base of column ${at} (0.5 m square, nominal)`;
      if (!d.levelId && col?.levelId) d.levelId = col.levelId;
      return;
    }
    const m = drafts.get(member);
    const g = m?.geometry;
    if (!m || !g?.axis) return;
    const mf = (m as Draft & { member?: MemberFact }).member;
    const atStart = mf ? (end === mf.ends[0] || end === "bottom") : true;
    const p = atStart ? g.axis.start : g.axis.end;
    // inside the depth of the member it lands on and at least 30 mm below the top of steel (more than the
    // graph's 25 mm contact): a slab bears on the beam, never on the plate, so the plate must not touch it
    const brace = m.kind === "brace";
    const top = brace ? p[2] : p[2] + (g.section?.depth ?? 0.3) / 2;
    const h = Math.max(0.1, (g.section?.depth ?? 0.3) * 0.4);
    // a brace gusset is a thin band just under the brace end: it reaches the member the brace lands on but
    // neither the slab above nor, at the base, the pier below the column
    const [z0, z1]: [number, number] = brace ? [p[2] - 0.1, p[2] - 0.03] : [p[2] - h, Math.min(p[2] + h, top - 0.03)];
    d.geometry = { bbox: { min: v3(p[0] - 0.15, p[1] - 0.15, z0), max: v3(p[0] + 0.15, p[1] + 0.15, z1) } };
    d.params["Drawing.GeometryRule"] = `0.3 m box at the ${end} end of ${member} (nominal)`;
    if (!d.levelId && m.levelId) d.levelId = m.levelId;
  }

  function rel(conn: string, member: string, d: Draft): RelationInput {
    const callouts = d.occ.filter((o) => o.how === "detail_callout");
    const detail: Record<string, ParamValue> = callouts.length
      ? { callouts: callouts.map((o) => `${o.text}@${o.sheet}`).join(" "), attribution: String(d.params["Drawing.CalloutAttribution"] ?? "") }
      : { sheets: [...new Set(d.occ.map((o) => o.sheet))].join(" ") };
    const [a, b]: [string, string] = conn < member ? [conn, member] : [member, conn];
    return { a, b, kind: "connects", evidence: { rule: callouts.length ? "drawing detail callout" : "column schedule base plate", source: "explicit", detail } };
  }

  // ------------------------------------------------------------ finish: occurrences, precision, source
  const elements: ElementInput[] = [];
  for (const d of [...drafts.values()].sort((a, b) => (a.id < b.id ? -1 : a.id > b.id ? 1 : 0))) {
    const os = dedupeOcc(d.occ);
    const first = os[0]!;
    const p = precision(first);
    const onLevel = d.levelId ? [...levels.values()].find((l) => l.id === d.levelId) : undefined;
    const params: Record<string, ParamValue> = {
      ...d.params,
      ...(onLevel?.assumed ? { "Drawing.LevelElevationAssumed": `${r2(onLevel.ft)} ft: ${onLevel.assumed}` } : {}),
      "Drawing.Sheet": first.sheet,
      "Drawing.Page": first.page,
      "Drawing.Rect": first.rect.join(","),
      "Drawing.Occurrences": occJson(os),
      "Drawing.OccurrenceCount": os.length,
      "Drawing.Tag": first.text,
    };
    if (d.geometry) {
      params["Drawing.GeometrySource"] = "drawing-derived";
      if (p) {
        params["Drawing.ScaleSource"] = p.source;
        params["Drawing.ScaleFtPerPt"] = Math.round(p.ftPerPt * 1e6) / 1e6;
        if (p.rmsResidualIn !== undefined) params["Drawing.ScaleResidualIn"] = p.rmsResidualIn;
      }
    }
    const el: ElementInput = {
      id: d.id, kind: d.kind, params,
      source: { format: SOURCE_FORMAT, file: first.file, nativeId: `${first.sheet}:p${first.page}:[${first.rect.join(",")}]`, nativeType: first.how },
    };
    if (d.mark) el.mark = d.mark;
    el.name = d.name ?? first.text;
    if (d.profile) el.profile = d.profile;
    if (d.levelId) el.levelId = d.levelId;
    if (d.geometry) el.geometry = d.geometry;
    elements.push(el);
  }
  if (!grid) warnings.push("no plan sheet with a readable grid: elements have no geometry");
  const levelList: LevelInput[] = [...levels.values()]
    .map((l) => ({ id: l.id, name: l.name, elevation: round6(l.ft * FT) }))
    .sort((a, b) => a.elevation - b.elevation || a.id.localeCompare(b.id));
  relations.sort((p, q) => p.kind.localeCompare(q.kind) || p.a.localeCompare(q.a) || p.b.localeCompare(q.b) || p.evidence.rule.localeCompare(q.evidence.rule));
  const seen = new Set<string>();
  const rels = relations.filter((r) => {
    const k = `${r.kind}|${r.a}|${r.b}`;
    if (seen.has(k)) return false;
    seen.add(k);
    return true;
  });
  return {
    meta: {
      version: MODEL_INPUT_VERSION, schema: "drawing-set", units: "m",
      source: { format: SOURCE_FORMAT, ...(inp.files.length === 1 ? { file: inp.files[0]! } : { file: inp.files.join(", ") }) },
    },
    levels: levelList,
    elements,
    relations: rels,
    warnings,
  };
}
