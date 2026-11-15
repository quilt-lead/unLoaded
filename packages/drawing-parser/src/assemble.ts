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
 * Level n+1; no number = above Level 1), Penthouse, Roof. NaN for a name outside that vocabulary.
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
  return NaN;
}

/** Storey height assumed above / below the nearest level when nothing brackets an unstated one, ft. */
const ASSUMED_STOREY_FT = 12;

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
  for (const n of names) if (Number.isNaN(levelOrder(n))) warnings.push(`level ${n}: name has no known storey order; placed after the numbered levels`);
  const out = new Map<string, Level>();
  const tof = vote(facts.datums.filter((d) => d.level === "top of footing"), "top of footing", warnings);
  for (const name of [...names].sort((a, b) => order(a) - order(b) || a.localeCompare(b))) {
    let ft = vote(facts.levels.filter((l) => l.level === name), name, warnings);
    if (ft === undefined && name === "Foundation") ft = tof;
    out.set(name, { name, id: slug(name), ft: ft ?? NaN, stated: ft !== undefined });
  }
  // unstated levels, walking up in storey order: evenly between the stated (or already assumed) level
  // below and the next stated level above; with nothing above, 12 ft storeys up from the one below;
  // with nothing below, 12 ft storeys down from the one above. Each consecutive unstated level gets
  // its own elevation (never the same as its neighbour). The foundation is placed last, 3 ft below
  // the lowest level. Every assumption is warned and labelled on the level (`assumed`).
  const list = [...out.values()].filter((l) => l.name !== "Foundation");
  for (let i = 0; i < list.length; i++) {
    if (list[i]!.stated) continue;
    let j = i;
    while (j + 1 < list.length && !list[j + 1]!.stated) j++;
    const lo = list[i - 1], hi = list[j + 1];
    const n = j - i + 1;
    for (let k = 0; k < n; k++) {
      const l = list[i + k]!;
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
    }
    i = j;
  }
  const fdn = out.get("Foundation");
  if (fdn && !fdn.stated) {
    fdn.ft = (list[0]?.ft ?? 0) - 3;
    fdn.assumed = `3 ft below ${list[0]?.name ?? "the lowest level"}`;
  }
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

  // ------------------------------------------------------------ columns (storeys merged)
  const tiersAt = new Map<string, ColumnTierFact[]>();
  for (const t of facts.tiers) tiersAt.set(t.at, [...(tiersAt.get(t.at) ?? []), t]);
  const pierAt = new Map<string, PointFact[]>();
  for (const p of facts.points) if (p.role === "pier") pierAt.set(p.at, [...(pierAt.get(p.at) ?? []), p]);
  for (const [at, ts] of tiersAt) {
    // one column per grid intersection: the id comes from its position only, never from its sizes, so
    // resizing a storey keeps the id (and every decision keyed on it). Storeys bottom-up; where sizes
    // differ by storey the element keeps every storey's size (Drawing.StoreySizes) and the lowest as
    // its profile - the drawing's text does not state where a column is spliced.
    const storeys = [...new Set(ts.map((t) => `${t.lo}..${t.hi}`))]
      .map((k) => ({ k, lo: k.split("..")[0]!, hi: k.split("..")[1]! }))
      .sort((a, b) => lvl(a.lo).ft - lvl(b.lo).ft || lvl(a.hi).ft - lvl(b.hi).ft);
    const sizeOf = (k: string) => {
      const sizes = [...new Set(ts.filter((t) => `${t.lo}..${t.hi}` === k && t.tag).map((t) => t.tag!.profile))];
      if (sizes.length > 1) warnings.push(`column ${at} ${k}: sizes ${sizes.join(", ")} disagree; kept ${sizes[0]}`);
      return sizes[0];
    };
    const sized = storeys.map((s) => ({ ...s, size: sizeOf(s.k) }));
    const id = `column:${at}`;
    for (const t of ts) {
      const d = draft(id, "column", t.occ);
      if (t.tag?.sfrs) d.params["Drawing.SFRS"] = true;
      d.params[`Drawing.Rule.${t.occ.how}`] = t.rule;
    }
    const d = drafts.get(id)!;
    const lo = sized[0]!.lo, hi = sized.reduce((a, b) => (lvl(b.hi).ft > lvl(a).ft ? b.hi : a), sized[0]!.hi);
    const profile = sized.find((s) => s.size)?.size;
    if (profile) d.profile = profile;
    const distinct = [...new Set(sized.map((s) => s.size).filter(Boolean))];
    if (distinct.length > 1) {
      d.params["Drawing.StoreySizes"] = sized.map((s) => `${s.lo} - ${s.hi}: ${s.size ?? "?"}`).join("; ");
      warnings.push(`column ${at}: size changes by storey (${distinct.join(", ")}); one element, profile ${profile} (lowest storey), every storey in Drawing.StoreySizes`);
    }
    d.levelId = lvl(lo).id;
    d.params["Drawing.Role"] = "column";
    d.params["Drawing.Grid"] = at;
    d.params["Drawing.Storeys"] = `${lo} - ${hi}`;
    if (grid) {
      const [xl, yl] = at.split("/") as [string, string];
      const x = grid.x.get(xl)! * FT, y = grid.y.get(yl)! * FT;
      const onPier = pierAt.has(at) && topOfPier !== undefined;
      const z0 = onPier ? topOfPier! * FT : z(lo);
      const z1 = z(hi);
      const sec = d.profile ? nominalSection(d.profile) : undefined;
      const w = sec ? Math.max(sec.depth, sec.width) : 0.3;
      d.geometry = {
        bbox: bboxOf([v3(x, y, z0), v3(x, y, z1)], [w / 2, w / 2, 0]),
        axis: { start: v3(x, y, z0), end: v3(x, y, z1) },
        ...(sec ? { section: { depth: round6(sec.depth), width: round6(sec.width) } } : {}),
      };
      d.params["Drawing.GeometryRule"] = `at grid intersection ${at}; from ${onPier ? "the top of pier (foundation note)" : `${lo}`} to ${hi}` +
        (sec ? `; section from the nominal designation${distinct.length > 1 ? " of the lowest storey" : ""}` : "; section unknown (0.3 m assumed)");
    }
  }

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
    d.params["Drawing.Role"] = c.member.startsWith("column:") && c.end === "base" ? "base_plate" : "connection";
    d.params["Drawing.Member"] = c.member;
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
      const at = member.slice("column:".length);
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
