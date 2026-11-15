// Load-path graph view (ported from the 2D concept): element lanes on the left,
// the calc graph on the right, dashed element -> calc mapping lines.
import type { Calc, CalcEdge, Edge, Element, Impact, Link } from "./api";

export interface GraphCtx {
  els: Map<string, Element>;
  edges: Edge[];
  linksFor: (gid: string) => Link[];
  calcs: Calc[];
  calcEdges: CalcEdge[];
  sel: { kind: "el" | "calc"; id: string } | null;
  impact: Impact | null;
  onSelect: (sel: { kind: "el" | "calc"; id: string }) => void;
}

const LANES: [string, string[]][] = [
  ["Slabs", ["Slab"]],
  ["Beams & braces", ["Beam", "Brace"]],
  ["Connections", ["Connection"]],
  ["Columns & walls", ["Column", "Wall"]],
  ["Foundations", ["Footing", "Pile"]],
  ["Other", ["Other"]],
];
const laneOf = (cat: string) =>
  Math.max(
    0,
    LANES.findIndex(([, cs]) => cs.includes(cat)),
  );
const NW = 96,
  NH = 34,
  PER_ROW = 6,
  MAX_PER_LANE = 18,
  ROW_H = 46,
  LANE_PAD = 26,
  EX0 = 24,
  EX1 = 610;
const KW = 160,
  KX0 = 650,
  KX1 = 985;
const esc = (s: unknown) =>
  String(s ?? "").replace(
    /[&<>"]/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]!,
  );
const natural = (a: string, b: string) =>
  a.localeCompare(b, undefined, { numeric: true });

function neighbourhood(ctx: GraphCtx): Set<string> {
  const out = new Set<string>();
  const down = new Map<string, string[]>(),
    up = new Map<string, string[]>();
  for (const e of ctx.edges) {
    (down.get(e.src) ?? down.set(e.src, []).get(e.src)!).push(e.dst);
    (up.get(e.dst) ?? up.set(e.dst, []).get(e.dst)!).push(e.src);
  }
  if (ctx.impact) {
    ctx.impact.removed.forEach((g) => out.add(g));
    Object.keys(ctx.impact.hit).forEach((g) => out.add(g));
    out.add(ctx.impact.global_id);
    return out;
  }
  if (!ctx.sel) return out;
  if (ctx.sel.kind === "calc") return out;
  const g = ctx.sel.id;
  out.add(g);
  const walk = (x: string, m: Map<string, string[]>, depth: number) => {
    if (depth <= 0) return;
    for (const n of m.get(x) ?? [])
      if (!out.has(n)) {
        out.add(n);
        walk(n, m, depth - 1);
      }
  };
  walk(g, down, 12);
  walk(g, up, 2);
  return out;
}

export function renderGraph(host: HTMLElement, ctx: GraphCtx) {
  const ids = neighbourhood(ctx);
  // ---- element lanes ----
  const byLane: string[][] = LANES.map(() => []);
  for (const g of ids) {
    const e = ctx.els.get(g);
    if (e) byLane[laneOf(e.cat)].push(g);
  }
  const pos = new Map<string, { x: number; y: number }>();
  let y = 48;
  const laneBoxes: { name: string; y: number; h: number; more: number }[] = [];
  byLane.forEach((list, li) => {
    if (!list.length && li === LANES.length - 1) return;
    list.sort((a, b) => {
      const sa = ctx.sel?.id === a ? -1 : 0,
        sb = ctx.sel?.id === b ? -1 : 0;
      return (
        sa - sb ||
        natural(ctx.els.get(a)!.storey, ctx.els.get(b)!.storey) ||
        natural(ctx.els.get(a)!.mark || a, ctx.els.get(b)!.mark || b)
      );
    });
    const shown = list.slice(0, MAX_PER_LANE),
      rows = Math.max(1, Math.ceil(shown.length / PER_ROW));
    const h = rows * ROW_H + LANE_PAD;
    shown.forEach((g, i) => {
      const r = Math.floor(i / PER_ROW),
        c = i % PER_ROW,
        n = Math.min(PER_ROW, shown.length - r * PER_ROW);
      const span = (EX1 - EX0) / n;
      pos.set(g, {
        x: EX0 + span * (c + 0.5),
        y: y + LANE_PAD + r * ROW_H + NH / 2,
      });
    });
    laneBoxes.push({
      name: LANES[li][0],
      y,
      h,
      more: list.length - shown.length,
    });
    y += h + 8;
  });
  const H = Math.max(y + 20, 560);
  // ---- calc graph: columns by dependency depth ----
  const calcs = ctx.calcs.filter((c) => !c.front);
  // longest-path depth in the calc graph (bounded relaxation, cycles cannot loop forever)
  const depth = new Map<string, number>(calcs.map((c) => [c.key, 0]));
  for (let it = 0; it < calcs.length; it++)
    for (const e of ctx.calcEdges)
      if (depth.has(e.src) && depth.has(e.dst) && depth.get(e.dst)! <= depth.get(e.src)!)
        depth.set(e.dst, Math.min(depth.get(e.src)! + 1, calcs.length));
  const kpos = new Map<string, { x: number; y: number }>();
  // simple, legible stacking: order by depth then title, alternate the two columns
  const ordered = [...calcs].sort(
    (a, b) => depth.get(a.key)! - depth.get(b.key)! || a.ord - b.ord,
  );
  const step = Math.max(
    44,
    Math.min(
      70,
      ((H - 90) / Math.max(1, Math.ceil(ordered.length / 2) * 2)) * 2,
    ),
  );
  ordered.forEach((c, i) =>
    kpos.set(c.key, {
      x: KX0 + (i % 2) * (KX1 - KX0 - KW) + KW / 2,
      y: 70 + (i * step) / 2,
    }),
  );
  const KH = Math.max(H, 70 + (ordered.length * step) / 2 + 40);
  const HH = Math.max(H, KH);

  const imp = ctx.impact;
  const stale = new Set(Object.keys(imp?.stale ?? {}));
  const removed = new Set(imp?.removed ?? []);
  const curve = (x1: number, y1: number, x2: number, y2: number) => {
    const my = (y1 + y2) / 2;
    return `M${x1},${y1} C${x1},${my} ${x2},${my} ${x2},${y2}`;
  };
  let svg = `<svg viewBox="0 0 1000 ${HH}" role="img" aria-label="Load-path graph mapped to the calc graph">
    <defs><marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="var(--calc)"/></marker></defs>
    <text class="g-head" x="${(EX0 + EX1) / 2}" y="22" text-anchor="middle">Element graph · load path from the BIM model</text>
    <text class="g-head" x="${(KX0 + KX1) / 2}" y="22" text-anchor="middle">Calc graph · from the calc package</text>
    <line x1="630" y1="34" x2="630" y2="${HH - 10}" stroke="var(--line)" stroke-dasharray="2 4"/>`;
  for (const lb of laneBoxes) {
    svg += `<rect class="g-lane" x="10" y="${lb.y}" width="610" height="${lb.h}" rx="8"/><text class="g-lanet" x="18" y="${lb.y + 14}">${lb.name}</text>`;
    if (lb.more > 0)
      svg += `<text class="g-more" x="612" y="${lb.y + 14}" text-anchor="end">+${lb.more} more not shown</text>`;
  }
  if (!ids.size) {
    svg += `<text class="g-empty" x="${(EX0 + EX1) / 2}" y="${HH / 2 - 10}" text-anchor="middle">Select an element (3D view or lists) to see its load path,</text>
      <text class="g-empty" x="${(EX0 + EX1) / 2}" y="${HH / 2 + 10}" text-anchor="middle">or run an impact check from the inspector.</text>`;
  }
  // mapping lines (top live link per visible element)
  for (const [g, p] of pos) {
    const top = ctx.linksFor(g)[0];
    if (!top) continue;
    const k = kpos.get(top.calc_key);
    if (!k) continue;
    const x2 = k.x - KW / 2,
      mx = (p.x + NW / 2 + x2) / 2;
    svg += `<path class="g-map${top.conf < 0.8 && top.status === "auto" ? " low" : ""}" d="M${p.x + NW / 2},${p.y} C${mx},${p.y} ${mx},${k.y} ${x2},${k.y}"/>`;
  }
  for (const e of ctx.edges) {
    const a = pos.get(e.src),
      b = pos.get(e.dst);
    if (!a || !b) continue;
    const cls =
      removed.has(e.src) || removed.has(e.dst)
        ? " gone"
        : imp && imp.hit[e.dst] !== undefined && imp.hit[e.src] !== undefined
          ? " imp"
          : "";
    svg += `<path class="g-edge${cls}" d="${curve(a.x, a.y + NH / 2, b.x, b.y - NH / 2)}"><title>${esc(e.rule)}</title></path>`;
  }
  for (const e of ctx.calcEdges) {
    const a = kpos.get(e.src),
      b = kpos.get(e.dst);
    if (!a || !b) continue;
    const cls = stale.has(e.src) && stale.has(e.dst) ? " imp" : "";
    const sx = a.x + (b.x > a.x ? KW / 2 : b.x < a.x ? -KW / 2 : 0),
      ex = b.x + (b.x > a.x ? -KW / 2 : b.x < a.x ? KW / 2 : 0);
    const d =
      a.x === b.x
        ? `M${a.x + KW / 2},${a.y} C${a.x + KW / 2 + 40},${a.y} ${b.x + KW / 2 + 40},${b.y} ${b.x + KW / 2},${b.y}`
        : `M${sx},${a.y} C${(sx + ex) / 2},${a.y} ${(sx + ex) / 2},${b.y} ${ex},${b.y}`;
    svg += `<path class="g-cedge${cls}" d="${d}" marker-end="url(#arr)"><title>${esc(e.src)} → ${esc(e.dst)}: ${esc(e.rules.join("; "))}</title></path>`;
  }
  for (const [g, p] of pos) {
    const e = ctx.els.get(g)!;
    const cls = [
      "g-node",
      e.cat === "Connection" ? "cx" : "",
      ctx.sel?.id === g ? "sel" : "",
      removed.has(g) ? "gone" : "",
      imp && imp.hit[g] !== undefined ? "imp" : "",
    ].join(" ");
    svg += `<g class="${cls}" data-el="${esc(g)}" transform="translate(${p.x - NW / 2},${p.y - NH / 2})"><rect width="${NW}" height="${NH}" rx="6"/>
      <text x="8" y="14">${esc((e.mark || e.name || e.ifc_type).slice(0, 13))}</text><text class="t2" x="8" y="27">${esc((e.profile || e.storey).slice(0, 15))}</text>
      <title>${esc(e.mark)} · ${esc(e.cat)} · ${esc(e.storey)}${imp?.why[g] ? "\n" + esc(imp.why[g]) : ""}</title></g>`;
  }
  for (const c of ordered) {
    const p = kpos.get(c.key)!;
    const cls = [
      "g-node calc",
      ctx.sel?.kind === "calc" && ctx.sel.id === c.key ? "sel" : "",
      stale.has(c.key) ? "stale" : "",
    ].join(" ");
    svg += `<g class="${cls}" data-calc="${esc(c.key)}" transform="translate(${p.x - KW / 2},${p.y - NH / 2})"><rect width="${KW}" height="${NH}" rx="8"/>
      <rect x="0" y="0" width="5" height="${NH}" rx="2" style="fill:${c.color};stroke:none"/>
      <text x="11" y="14">${esc(c.title.length > 22 ? c.title.slice(0, 21) + "…" : c.title)}</text><text class="t2" x="11" y="27">${esc((c.scanned ? "no text - needs OCR" : c.software || c.cat || "").slice(0, 22))}</text>
      <title>${esc(c.title)}${stale.has(c.key) ? "\nSTALE: " + esc(imp!.stale[c.key]) : ""}</title></g>`;
  }
  svg += "</svg>";
  host.innerHTML = svg;
  host
    .querySelectorAll<SVGGElement>("[data-el]")
    .forEach((n) =>
      n.addEventListener("click", () =>
        ctx.onSelect({ kind: "el", id: n.dataset.el! }),
      ),
    );
  host
    .querySelectorAll<SVGGElement>("[data-calc]")
    .forEach((n) =>
      n.addEventListener("click", () =>
        ctx.onSelect({ kind: "calc", id: n.dataset.calc! }),
      ),
    );
}
