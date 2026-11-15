/**
 * Element <-> calc mapping. Port of the reference run_mapping() (itself a faithful port of the
 * mockup's runMapping()); tiers, their confidences and their order unchanged:
 *
 *   exact    0.97  the element's mark appears as a token
 *   range    0.90  the mark falls inside a written range ("2B1 - 2B9", "C1 thru C12")
 *   loose    0.88  the mark matches ignoring punctuation ("SL2" for "SL-2")
 *   family   0.85  token names a mark family ("BR1" covers "BR1-1".."BR1-n")
 *   size     0.62  section size + element type (+ storey if the line names one), no mark
 *   partial  0.50  token is the tail of exactly one model mark ("CB1" -> "2CB1")
 *   xref     <=.45 any mark tier where the element type differs from the calc's type -
 *                  the calc mentions the element, it probably did not design it
 *   type     0.30  calc names no marks or sizes: covers unclaimed elements of its type
 * Scanned pages and front matter are never mapped. Every link keeps page, the exact text span it
 * matched, a snippet, word boxes for highlighting, and the rule. Calcs are read region by region
 * (a calc can start or end mid-page): a match counts only inside the calc's own regions.
 * Calc text and marks go through one fold (text.ts: upper case, Unicode dashes -> "-", offsets kept);
 * section sizes through one grammar (profile.ts `findSections`, the parser's patterns plus the
 * designations the model carries; a model mark is never a size); storeys through one whole-word test
 * (`storeysOn`), for the size rule and the evidence alike.
 *
 * On top of the tier (always evidence item 1, so tier metrics still compute) each link carries:
 * - more evidence on the matched line, summed into the confidence and clamped to [0, 1]:
 *   storey named and equal (+0.05) / different (-0.15); size named and equal to the model's
 *   (+0.05) / different on a mark line (-0.20);
 * - a role: "design" (the calc sizes the element) or "loads" (it only takes loads from / refers to
 *   it): xref links are loads; otherwise design when ANY hit sits on a line without a load cue
 *   (reaction(s), load(s), from, carried, end moment(s), punching, supporting, designed separately, see);
 * - a band (high >= 0.75, medium >= 0.5, low) and caveats.
 * A size on a line that names no mark ("typical beams W12X19") links the calc to the TYPICAL GROUP
 * (same size + storey + kind) once; members keep a per-element link marked `via_group`. A design-role line that NAMES the mark (exact / range
 * tier) and a different size than the model has is a size-mismatch finding.
 *
 * Every link, group link and finding carries provenance: producer calc-mapper/matcher, the rule id
 * (`matcher.tier.<tier>`, `matcher.typical-group`, `matcher.finding.size-mismatch`) and the two
 * documents it rests on - the element graph (`graphSha256`) and the PDF of the page it was read on.
 */
import { rectsForSpan } from "./pdf.ts";
import { findSections, normaliseProfile, profileFromText, type SectionHit } from "./profile.ts";
import { RULES, ruleProvenance } from "./provenance.ts";
import { CAT_WORDS, calcRegions } from "./segment.ts";
import { foldText } from "./text.ts";
import type {
  Calc, CalcPage, ConfidenceBand, ElementRow, Finding, GroupLink, Link, LinkEvidence, LinkRole, Rect, Snippet, Tier,
  TypicalGroup,
} from "./types.ts";

export const CONF = { exact: 0.97, range: 0.9, loose: 0.88, family: 0.85, size: 0.62, partial: 0.5, type: 0.3 } as const;
export const XREF_CAP = 0.45;
/** Evidence weights beyond the tier. */
export const WEIGHTS = { storeyMatch: 0.05, storeyConflict: -0.15, sizeMatch: 0.05, sizeMismatch: -0.2 } as const;
export const BANDS = { high: 0.75, medium: 0.5 } as const;

// calc text is read folded (text.ts: upper case, Unicode dashes -> "-"), so "-" is the only dash these rules need
const RANGE = /\b([A-Z]{0,3}\d{0,2}[A-Z]{1,3})(\d{1,4})\s*(?:-|TO|THRU|THROUGH)\s*(?:\1)?(\d{1,4})\b/g;
const TOK = /[A-Z0-9]+(?:[-./][A-Z0-9]+)*/g;
const LOAD_CUE = /\b(REACTIONS?|LOADS?|FROM|CARRIED|END MOMENTS?|PUNCHING|SUPPORTING|DESIGNED SEPARATELY|SEE)\b/;
const MARK_TIERS: ReadonlySet<Tier> = new Set(["exact", "range", "loose", "family", "partial"]);
/** Tiers that name the element's own mark (not a punctuation-insensitive or partial match): only these raise findings. */
const NAMED_TIERS: ReadonlySet<Tier> = new Set(["exact", "range"]);

/** Section designation as one comparable string (the parser's normaliser: profile.ts). */
export const normProfile = (s: string): string => (s ? normaliseProfile(s) : "");

/**
 * First section designation in the given strings, by the model side's own rule (profile.ts
 * `profileFromText`, the parser's grammar), on the folded text.
 */
export function profileFrom(...strs: (string | null | undefined)[]): string {
  return profileFromText(strs.map((s) => (s ? foldText(String(s)) : undefined))) ?? "";
}

/** A mark as one comparable string: the calc-text fold (text.ts) without whitespace. */
export const normMark = (s: string | null | undefined): string => foldText(String(s ?? "")).replace(/\s+/g, "");
export const dashless = (s: string | null | undefined): string => normMark(s).replace(/[-./]/g, "");

export const bandOf = (conf: number): ConfidenceBand => (conf >= BANDS.high ? "high" : conf >= BANDS.medium ? "medium" : "low");
const clamp01 = (v: number): number => Math.min(1, Math.max(0, Math.round(v * 1e6) / 1e6));

function snippet(text: string, idx: number, n: number): Snippet {
  const a = Math.max(0, idx - 70);
  const b = Math.min(text.length, idx + n + 70);
  return {
    before: (a > 0 ? "…" : "") + text.slice(a, idx), match: text.slice(idx, idx + n),
    after: text.slice(idx + n, b) + (b < text.length ? "…" : ""),
  };
}

const push = <K, V>(m: Map<K, V[]>, k: K, v: V): void => {
  const l = m.get(k);
  if (l) l.push(v);
  else m.set(k, [v]);
};
const cmp = (p: string, q: string): number => (p < q ? -1 : p > q ? 1 : 0);
/** Start of the line containing index i (Python's U.rfind("\n", 0, i) + 1). */
const lineStart = (U: string, i: number): number => (i > 0 ? U.lastIndexOf("\n", i - 1) + 1 : 0);
const escapeRe = (s: string): string => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

export const groupId = (cat: string, storey: string, profile: string): string => `group:${cat}:${storey}:${profile}`;

/** Typical groups: elements with a profile, by (kind, storey, profile). */
export function typicalGroups(elements: ElementRow[]): TypicalGroup[] {
  const by = new Map<string, ElementRow[]>();
  for (const e of elements) if (e.profile) push(by, groupId(e.cat, e.storey, normProfile(e.profile)), e);
  return [...by.entries()]
    .map(([id, ms]) => {
      const e = ms[0]!;
      const profile = normProfile(e.profile);
      const noun = e.cat.toLowerCase();
      return {
        id, cat: e.cat, storey: e.storey, profile, members: ms.map((m) => m.global_id).sort(cmp),
        title: `${e.storey ? e.storey + " " : ""}${noun}${ms.length > 1 ? "s" : ""} ${profile}${ms.length > 1 ? " (typ.)" : ""}`,
      };
    })
    .sort((p, q) => cmp(p.id, q.id));
}

export interface MappingResult {
  links: Link[];
  groups: TypicalGroup[];
  group_links: GroupLink[];
  findings: Finding[];
}

interface Hit {
  conf: number; // tier confidence (after the xref cap): decides which hit a link keeps, as the reference engine did
  link: Link;
}

/**
 * Map elements to calcs. `elements` = graphElements(graph); `calcs` + `pages` = the calc package;
 * `graphSha256` = sha256 of the graph the elements were read from (sha256Json(graph)).
 * Returns auto links (status "auto"), sorted by (calc_key, global_id), plus typical groups, group
 * links and size-mismatch findings.
 */
export function mapElements(elements: ElementRow[], calcs: Calc[], pages: CalcPage[], graphSha256: string): MappingResult {
  const groups = typicalGroups(elements);
  const empty = { links: [], groups, group_links: [], findings: [] };
  if (!elements.length || !calcs.length) return empty;
  const kept = new Map<string, Hit>();
  const designVotes = new Map<string, number>();
  const mismatch = new Map<string, Finding>();
  const groupLinks = new Map<string, GroupLink>();
  const els = [...elements].sort((p, q) => cmp(p.global_id, q.global_id));
  const pageByN = new Map(pages.map((p) => [p.n, p]));
  const exact = new Map<string, ElementRow[]>();
  const loose = new Map<string, ElementRow[]>();
  const families = new Map<string, ElementRow[]>();
  for (const el of els) {
    if (!el.mark) continue;
    const n = normMark(el.mark);
    push(exact, n, el);
    push(loose, dashless(el.mark), el);
    const fam = /^(.+?)-\d{1,3}[A-Z]?$/.exec(n);
    if (fam) push(families, fam[1]!, el);
  }
  const allMarks = [...exact.keys()];
  const byProfile = new Map<string, ElementRow[]>();
  for (const el of els) if (el.profile) push(byProfile, `${normProfile(el.profile)}|${el.cat}`, el);
  // longest first; equal lengths alphabetically (deterministic)
  const storeys = [...new Set(els.map((e) => e.storey).filter((s) => s && s.length > 2))]
    .sort((p, q) => q.length - p.length || cmp(p, q));
  const storeyRes = storeys.map((s) => [s, new RegExp(`(^|[^0-9A-Z])${escapeRe(foldText(s))}(?![0-9A-Z])`)] as const);
  /** The storeys a (folded) line names, longest first: whole words only ("LEVEL 10" does not name Level 1, "ROOFING" not Roof). */
  const storeysOn = (line: string): string[] => storeyRes.filter(([, rx]) => rx.test(line)).map(([s]) => s);
  // section designations: the parser's grammar plus the designations the model carries; a model mark is not a size
  const known = new Set(els.map((e) => normProfile(e.profile)).filter(Boolean));
  const markSet: ReadonlySet<string> = new Set(exact.keys());
  const sectionsIn = (text: string): SectionHit[] => findSections(text, { known, marks: markSet, markOf: normMark });
  const markHits = new Map<string, number>();
  /** Lines (page:lineStart) on which a mark tier matched: a size on such a line is not a "typical" (size-only) statement. */
  const markLines = new Set<string>();

  /** Storeys and sizes the line names. */
  const lineFacts = (line: string) => {
    const lineStoreys = storeysOn(line);
    const sizes = sectionsIn(line).map((h) => h.profile);
    return { lineStoreys, sizes };
  };

  const evidenceFor = (
    el: Pick<ElementRow, "storey" | "profile">, tier: Tier, tierConf: number, rule: string, pg: CalcPage, line: string,
    rects: Rect[], sizeRects: () => Rect[],
  ): { evidence: LinkEvidence[]; caveats: string[]; sizes: string[] } => {
    const evidence: LinkEvidence[] = [{ kind: "tier", weight: tierConf, note: `${tier}: ${rule}`, page: pg.n, rects }];
    const caveats: string[] = [];
    const { lineStoreys, sizes } = lineFacts(line);
    if (el.storey && lineStoreys.length) {
      if (lineStoreys.includes(el.storey)) {
        evidence.push({ kind: "storey-match", weight: WEIGHTS.storeyMatch, note: `line names ${el.storey}`, page: pg.n, rects: [] });
      } else {
        evidence.push({ kind: "storey-conflict", weight: WEIGHTS.storeyConflict,
          note: `line names ${lineStoreys.join(", ")}; element is on ${el.storey}`, page: pg.n, rects: [] });
        caveats.push(`The calc line names ${lineStoreys.join(", ")}, but the element is on ${el.storey}.`);
      }
    }
    const profile = normProfile(el.profile);
    if (profile && sizes.length) {
      if (sizes.includes(profile)) {
        evidence.push({ kind: "size-match", weight: WEIGHTS.sizeMatch, note: `line names ${profile}`, page: pg.n, rects: sizeRects() });
      } else if (MARK_TIERS.has(tier)) {
        evidence.push({ kind: "size-mismatch", weight: WEIGHTS.sizeMismatch,
          note: `line names ${sizes.join(", ")}; model has ${profile}`, page: pg.n, rects: sizeRects() });
        caveats.push(`The calc gives ${sizes.join(", ")} where the model has ${profile}.`);
      }
    }
    return { evidence, caveats, sizes };
  };

  const link = (el: ElementRow, c: Calc, conf0: number, tier0: Tier, rule0: string, pg: CalcPage, U: string, idx: number, n: number,
    viaGroup?: string) => {
    let conf = conf0, tier = tier0, rule = rule0;
    if (c.cat && el.cat !== c.cat && el.cat !== "Other" && tier !== "size" && tier !== "type") {
      conf = Math.min(conf, XREF_CAP);
      tier = "xref";
      rule = `${el.cat} "${el.mark}" is mentioned in a ${c.cat.toLowerCase()} calc - likely a cross-reference`;
    }
    const k = `${el.global_id}\u0000${c.key}`;
    const ls = lineStart(U, idx);
    const le = U.indexOf("\n", idx);
    if (MARK_TIERS.has(tier0)) markLines.add(`${pg.n}:${ls}`);
    const line = U.slice(ls, le >= 0 ? le : undefined);
    const loadsLine = LOAD_CUE.test(line);
    if (!loadsLine && tier !== "xref") designVotes.set(k, (designVotes.get(k) ?? 0) + 1);
    const rects = rectsForSpan(pg, idx, idx + n);
    const sizeRects = (): Rect[] => sectionsIn(line).flatMap((h) => rectsForSpan(pg, ls + h.index, ls + h.index + h.length));
    const ev = evidenceFor(el, tier, conf, rule, pg, line, rects, sizeRects);
    if (loadsLine) ev.evidence.push({ kind: "loads-context", weight: 0, note: "the line is about reactions / loads / a reference", page: pg.n, rects: [] });
    if (viaGroup) ev.evidence.push({ kind: "group", weight: 0, note: `linked through typical group ${viaGroup}`, page: pg.n, rects: [] });
    // a design-role mark line naming another size: the calc sized something else
    const inputs = [graphSha256, pg.doc_sha256];
    const mm = ev.evidence.find((e) => e.kind === "size-mismatch");
    if (mm && !loadsLine && NAMED_TIERS.has(tier) && !mismatch.has(k)) {
      mismatch.set(k, {
        kind: "size-mismatch", global_id: el.global_id, calc_key: c.key, model_size: normProfile(el.profile),
        calc_size: ev.sizes[0]!, page: pg.n, span: [idx, idx + n], rects: [...rects, ...mm.rects], snippet: snippet(pg.text, idx, n),
        note: `${c.title} gives ${ev.sizes.join(", ")} for ${el.mark || el.global_id}; the model has ${normProfile(el.profile)}`,
        provenance: ruleProvenance("matcher", RULES.matcher.sizeMismatch, inputs),
      });
    }
    const sum = clamp01(ev.evidence.reduce((s, e) => s + e.weight, 0));
    const rec: Link = {
      global_id: el.global_id, calc_key: c.key, conf: sum, tier, rule, page: pg.n, span: [idx, idx + n],
      token: pg.text.slice(idx, idx + n), snippet: snippet(pg.text, idx, n), rects, status: "auto",
      role: "loads", band: bandOf(sum), evidence: ev.evidence, caveats: ev.caveats, ...(viaGroup ? { via_group: viaGroup } : {}),
      provenance: ruleProvenance("matcher", RULES.matcher.tier(tier), inputs),
    };
    const ex = kept.get(k);
    if (!ex || conf > ex.conf) kept.set(k, { conf, link: rec });
  };
  const hit = (c: Calc) => markHits.set(c.key, (markHits.get(c.key) ?? 0) + 1);

  for (const c of calcs) {
    if (c.scanned || c.front) continue;
    markHits.set(c.key, 0);
    for (const r of calcRegions(c, pages)) {
      const pg = pageByN.get(r.page);
      if (!pg) continue;
      const U = foldText(pg.text);
      const inside = (m: { index: number; 0: string }) => m.index >= r.start && m.index + m[0].length <= r.end;
      // 1. ranges
      for (const m of U.matchAll(RANGE)) {
        if (!inside(m)) continue;
        const pre = m[1]!, a = Number(m[2]), b = Number(m[3]);
        if (!(b > a && b - a < 300)) continue;
        if (exact.has(normMark(m[0]))) continue;
        let any = false;
        for (let i = a; i <= b; i++) {
          for (const el of exact.get(`${pre}${i}`) ?? []) {
            link(el, c, CONF.range, "range", `In range ${pre}${a}–${pre}${b}`, pg, U, m.index, m[0].length);
            any = true;
          }
        }
        if (any) hit(c);
      }
      // 2. tokens
      for (const m of U.matchAll(TOK)) {
        if (!inside(m)) continue;
        const tok = m[0];
        if (!/[A-Z]/.test(tok) || !/\d/.test(tok) || tok.length < 2) continue;
        let h = exact.get(tok);
        if (h) {
          for (const el of h) link(el, c, CONF.exact, "exact", `Mark "${el.mark}" named in calc`, pg, U, m.index, tok.length);
          hit(c);
          continue;
        }
        h = loose.get(dashless(tok));
        if (h) {
          for (const el of h) {
            link(el, c, CONF.loose, "loose", `"${tok}" matches mark "${el.mark}" ignoring punctuation`, pg, U, m.index, tok.length);
          }
          hit(c);
          continue;
        }
        h = families.get(tok);
        if (h) {
          for (const el of h) link(el, c, CONF.family, "family", `"${tok}" covers mark family ${tok}-n`, pg, U, m.index, tok.length);
          hit(c);
          continue;
        }
        if (/^[A-Z]+\d+$/.test(tok) && !profileFrom(tok)) {
          const cands = allMarks.filter(
            (mk) => mk.length > tok.length && mk.endsWith(tok) && /^[0-9A-Z]/.test(mk[mk.length - tok.length - 1]!),
          );
          if (cands.length === 1) {
            for (const el of exact.get(cands[0]!)!) {
              link(el, c, CONF.partial, "partial", `"${tok}" is a partial mark - only "${el.mark}" ends with it`, pg, U, m.index, tok.length);
            }
            hit(c);
          }
        }
      }
      // 3. section size + element type (+ storey named on the line) -> the typical group(s)
      if (c.cat) {
        for (const h of sectionsIn(U)) {
          if (h.index < r.start || h.index + h.length > r.end) continue;
          const m = { index: h.index, 0: U.slice(h.index, h.index + h.length) };
          const p = h.profile;
          const ls = lineStart(U, m.index);
          const le = U.indexOf("\n", m.index);
          const line = U.slice(ls, le >= 0 ? le : undefined);
          const lineCat = CAT_WORDS.find(([, rx]) => rx.test(line))?.[0] || c.cat;
          const lineStorey = storeysOn(line)[0] ?? null;
          const rule = `Size ${p} + element type ${lineCat}${lineStorey ? " on " + lineStorey : ""} (no mark given)`;
          // a size on a line that names no mark is a typical (size-only) statement: it links the GROUP once;
          // a size beside a mark keeps the reference engine's plain per-element size links
          const typical = !markLines.has(`${pg.n}:${ls}`);
          const touched = new Set<string>();
          for (const el of byProfile.get(`${p}|${lineCat}`) ?? []) {
            if (lineStorey && el.storey !== lineStorey) continue;
            if (el.mark && kept.has(`${el.global_id}\u0000${c.key}`)) continue;
            const gid = groupId(el.cat, el.storey, normProfile(el.profile));
            if (typical) touched.add(gid);
            link(el, c, CONF.size, "size", rule, pg, U, m.index, m[0].length, typical ? gid : undefined);
          }
          for (const gid of touched) {
            const k = `${gid}\u0000${c.key}`;
            if (groupLinks.has(k)) continue;
            const g = groups.find((x) => x.id === gid)!;
            const rects = rectsForSpan(pg, m.index, m.index + m[0].length);
            const ev = evidenceFor({ storey: g.storey, profile: g.profile }, "size", CONF.size, rule, pg, line, rects, () => rects);
            const loadsLine = LOAD_CUE.test(line);
            if (loadsLine) ev.evidence.push({ kind: "loads-context", weight: 0, note: "the line is about reactions / loads / a reference", page: pg.n, rects: [] });
            const sum = clamp01(ev.evidence.reduce((s, e) => s + e.weight, 0));
            groupLinks.set(k, {
              group: gid, calc_key: c.key, conf: sum, band: bandOf(sum), tier: "size", role: loadsLine ? "loads" : "design", rule,
              page: pg.n, token: pg.text.slice(m.index, m.index + m[0].length), span: [m.index, m.index + m[0].length],
              snippet: snippet(pg.text, m.index, m[0].length), rects, evidence: ev.evidence,
              caveats: [...ev.caveats, `Size-only match: covers every ${g.title.toLowerCase()} - check the calc covers this group.`],
              provenance: ruleProvenance("matcher", RULES.matcher.typicalGroup, [graphSha256, pg.doc_sha256]),
            });
          }
        }
      }
    }
  }
  // 4. element type only
  const claimed = new Set([...kept.values()].map((h) => h.link.global_id));
  const linkedCalcs = new Set([...kept.values()].map((h) => h.link.calc_key));
  for (const c of calcs) {
    if (c.scanned || c.front || !c.cat || markHits.get(c.key) || linkedCalcs.has(c.key)) continue;
    const r = calcRegions(c, pages)[0];
    const pg = r && pageByN.get(r.page);
    if (!r || !pg) continue;
    const rx = CAT_WORDS.find(([k]) => k === c.cat)?.[1];
    if (!rx) continue;
    const mm = rx.exec(pg.text.slice(r.start, r.end));
    const [idx, n] = mm ? [r.start + mm.index, mm[0].length] : [r.start, 0];
    const U = foldText(pg.text);
    for (const el of els) {
      if (el.cat === c.cat && !claimed.has(el.global_id)) {
        link(el, c, CONF.type, "type", `Calc covers ${c.cat.toLowerCase()}s but names no marks or sizes`, pg, U, idx, n);
      }
    }
  }

  const links = [...kept.entries()].map(([k, h]): Link => {
    const role: LinkRole = h.link.tier !== "xref" && (designVotes.get(k) ?? 0) > 0 ? "design" : "loads";
    const caveats = [...h.link.caveats];
    if (role === "loads") caveats.push("Loads / reference only: the calc does not size this element.");
    if (h.link.tier === "type") caveats.push("Type-only match: the calc names no marks or sizes.");
    if (h.link.via_group) caveats.push(`Linked through its typical group (${h.link.via_group}), not by mark.`);
    return { ...h.link, role, caveats };
  }).sort((p, q) => cmp(p.calc_key, q.calc_key) || cmp(p.global_id, q.global_id));
  const roleOf = new Map(links.map((l) => [`${l.global_id}\u0000${l.calc_key}`, l.role]));
  const findings = [...mismatch.entries()]
    .filter(([k]) => roleOf.get(k) === "design")
    .map(([, f]) => f)
    .sort((p, q) => cmp(p.calc_key, q.calc_key) || cmp(p.global_id, q.global_id));
  return {
    links, groups, findings,
    group_links: [...groupLinks.values()].sort((p, q) => cmp(p.calc_key, q.calc_key) || cmp(p.group, q.group)),
  };
}

/** The auto links only (the reference engine's run_mapping signature). */
export function runMapping(elements: ElementRow[], calcs: Calc[], pages: CalcPage[], graphSha256: string): Link[] {
  return mapElements(elements, calcs, pages, graphSha256).links;
}
