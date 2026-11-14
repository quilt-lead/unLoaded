// Graph builders for the drawing-set view, one per selection kind (port of the legacy SVG graphs:
// overview, element, calc page, calc record and connection), laid out by the shared GraphView.
// Every node and edge carries the action it runs on click.
import type {
  CEdge,
  CInst,
  CType,
  EEdge,
  El,
  Lnk,
  REdge,
  Rec,
  RLink,
  SetCalc,
} from "../../api/types";
import type {
  GraphEdge,
  GraphLane,
  GraphNode,
} from "../../components/GraphView";
import {
  CAT_COL,
  CONN_COL,
  PARAPET_DETAIL,
  PARAPET_REC,
  SEC_COL,
  SEC_ORDER,
  TONE_COL,
  calcSec,
  nat,
  recColor,
  recEdgesOut,
  secName,
  tierCls,
  type Sel,
  type SetIndex,
} from "./model";

export interface Act {
  run: () => void;
}
export type GN = GraphNode<Act>;
export type GE = GraphEdge<Act>;
export interface Built {
  nodes: GN[];
  edges: GE[];
  lanes: GraphLane[];
  hint?: string;
  more: string[];
  kind: "overview" | "el" | "calc" | "rec" | "conn";
}

export interface Actions {
  select: (s: Sel) => void;
  openLink: (l: Lnk) => void;
  openEEdge: (e: EEdge) => void;
  openCEdge: (e: CEdge) => void;
  openREdge: (e: REdge) => void;
  openRLink: (l: RLink, rid: string) => void;
  openInstEl: (i: CInst, elId: string) => void;
  openFindingKind: (kind: string) => void;
  overviewEls: (key: string, firstId: string) => void;
  overviewCalcs: (firstId: string) => void;
}

const JOIN_TXT: Record<string, string> = {
  exact: "exact join (shared label)",
  inferred: "inferred join (coordinates)",
  absent: "absent - no support found",
};
const k = (kind: string, id: string) => `${kind}:${id}`;

function recNode(r: Rec, a: Actions, sel = false): GN {
  return {
    id: k("rec", r.id),
    label: r.title,
    sub: `${r.table}${r.level && !r.table.includes(r.level) ? " · " + r.level : ""}`,
    color: recColor(r),
    tone: sel ? "accent" : undefined,
    data: { run: () => a.select({ kind: "rec", id: r.id }) },
  };
}
function elNode(e: El, a: Actions): GN {
  return {
    id: k("el", e.id),
    label: e.text,
    sub: `${e.sheet} · ${e.grid || e.type}`,
    color: CAT_COL[e.cat] ?? CAT_COL.Other,
    data: { run: () => a.select({ kind: "el", id: e.id }) },
  };
}
function calcNode(c: SetCalc, a: Actions, sub?: string): GN {
  return {
    id: k("calc", c.id),
    label: `${c.sheet_id} ${c.title}`,
    sub: sub ?? `page · ${c.software}`,
    color: SEC_COL[calcSec(c)] ?? "#888",
    data: { run: () => a.select({ kind: "calc", id: c.id }) },
  };
}
function instNode(i: CInst, a: Actions): GN {
  return {
    id: k("cinst", i.id),
    label: i.type_id ?? i.symbol_name ?? i.ref,
    sub: `${i.via}${i.symbol ? " " + i.symbol : ""} · ${i.sheet} ${i.grid || ""}`,
    color: CONN_COL,
    data: { run: () => a.select({ kind: "cinst", id: i.id }) },
  };
}
function typeNode(t: CType, a: Actions): GN {
  return {
    id: k("ctype", t.id),
    label: `${t.id} ${t.title}`,
    sub: `detail · ${t.category}`,
    color: CONN_COL,
    data: { run: () => a.select({ kind: "ctype", id: t.id }) },
  };
}
const recEdge = (e: REdge, a: Actions, target?: string): GE => ({
  id: `re:${e.src}>${target ?? e.dst}:${e.kind}`,
  source: k("rec", e.src),
  target: target ?? k("rec", e.dst!),
  style:
    e.join === "exact"
      ? "exact"
      : e.join === "inferred"
        ? "inferred"
        : "absent",
  color: "var(--calc)",
  title: `${e.kind} - ${JOIN_TXT[e.join]}: ${e.rule} - click for both rows`,
  data: { run: () => a.openREdge(e) },
});
const linkEdge = (
  id: string,
  src: string,
  dst: string,
  score: number,
  title: string,
  run: () => void,
): GE => ({
  id,
  source: src,
  target: dst,
  style: "inferred",
  color: TONE_COL[tierCls(score)],
  title,
  data: { run },
});
function lanesOf(defs: [GraphLane, GN[]][]): {
  lanes: GraphLane[];
  nodes: GN[];
} {
  const lanes: GraphLane[] = [];
  const nodes: GN[] = [];
  const seen = new Set<string>();
  for (const [lane, ns] of defs) {
    const fresh = ns.filter((n) => !seen.has(n.id));
    if (!fresh.length) continue;
    lanes.push(lane);
    for (const n of fresh) {
      seen.add(n.id);
      nodes.push({ ...n, lane: lane.id });
    }
  }
  return { lanes, nodes };
}
/** drop edges whose ends are not drawn, and duplicates */
function keep(edges: GE[], nodes: GN[]): GE[] {
  const ids = new Set(nodes.map((n) => n.id));
  const seen = new Set<string>();
  return edges.filter((e) => {
    if (!ids.has(e.source) || !ids.has(e.target) || seen.has(e.id))
      return false;
    seen.add(e.id);
    return true;
  });
}

// ---------------------------------------------------------------- overview: every link bundled
export function overviewGraph(x: SetIndex, a: Actions): Built {
  const ecl = new Map<string, El[]>();
  for (const e of x.g.elements)
    (
      ecl.get(`${e.sheet}|${e.type}`) ??
      ecl.set(`${e.sheet}|${e.type}`, []).get(`${e.sheet}|${e.type}`)!
    ).push(e);
  const ccl = new Map<string, SetCalc[]>();
  for (const c of x.g.calcs)
    (ccl.get(calcSec(c)) ?? ccl.set(calcSec(c), []).get(calcSec(c))!).push(c);
  const ekeys = [...ecl.keys()]
    .sort(nat)
    .filter(
      (key) =>
        ecl.get(key)!.length >= 2 || x.linksByEl.has(ecl.get(key)![0].id),
    );
  const ckeys = [...ccl.keys()].sort(
    (p, q) => SEC_ORDER.indexOf(p) - SEC_ORDER.indexOf(q),
  );
  const bundle = new Map<string, number>();
  for (const l of x.g.links) {
    const e = x.els.get(l.el),
      c = x.calcs.get(l.calc);
    if (!e || !c) continue;
    const key = `${e.sheet}|${e.type}#${calcSec(c)}`;
    bundle.set(key, (bundle.get(key) ?? 0) + 1);
  }
  const enodes: GN[] = ekeys.map((key) => {
    const es = ecl.get(key)!;
    const nl = es.filter((e) => x.linksByEl.has(e.id)).length;
    const [sh, ty] = key.split("|");
    const first = es.find((e) => x.linksByEl.has(e.id)) ?? es[0];
    return {
      id: `ecl:${key}`,
      label: `${sh} ${ty}`,
      sub: `${nl}/${es.length} linked`,
      color: nl ? "var(--good)" : "var(--muted)",
      tone: nl === es.length ? "good" : undefined,
      title: `${nl} of ${es.length} linked - click to list them`,
      data: { run: () => a.overviewEls(key, first.id) },
    };
  });
  const cnodes: GN[] = ckeys.map((key) => {
    const cs = ccl.get(key)!;
    const nl = cs.filter((c) => x.linksByCalc.has(c.id)).length;
    const first = cs.find((c) => x.linksByCalc.has(c.id)) ?? cs[0];
    return {
      id: `ccl:${key}`,
      label: secName(key),
      sub: `${cs.length} pages · ${nl} linked to elements`,
      color: SEC_COL[key] ?? "#888",
      data: { run: () => a.overviewCalcs(first.id) },
    };
  });
  const edges: GE[] = [...bundle.entries()].map(([key, n]) => {
    const [ek, ck] = key.split("#");
    return {
      id: `b:${key}`,
      source: `ecl:${ek}`,
      target: `ccl:${ck}`,
      style: "plain",
      color: "color-mix(in srgb, var(--accent) 40%, transparent)",
      width: Math.min(14, 1 + Math.sqrt(n)),
      title: `${n} links ${ek.replace("|", " ")} -> ${secName(ck)}`,
      data: {
        run: () =>
          a.overviewEls(
            ek,
            (ecl.get(ek)!.find((e) => x.linksByEl.has(e.id)) ?? ecl.get(ek)![0])
              .id,
          ),
      },
    };
  });
  const { lanes, nodes } = lanesOf([
    [
      {
        id: "els",
        label: "Elements by sheet and type",
        info: "graph.set-lane-el-groups",
      },
      enodes,
    ],
    [
      {
        id: "secs",
        label: "Calc package sections",
        info: "graph.set-lane-calc-sections",
      },
      cnodes,
    ],
  ]);
  return {
    kind: "overview",
    nodes,
    edges: keep(edges, nodes),
    lanes,
    more: [],
    hint: "Overview - every link bundled by element group and calc section. Pick an element or calc page (left, or click a group) to see its load path, its calc pages and the calc feeds, each opening the original page.",
  };
}

// ---------------------------------------------------------------- element
function loadPathAround(x: SetIndex, id: string) {
  const carried = (x.up.get(id) ?? []).map((e) => e.src).slice(0, 6);
  const chain: string[] = [];
  const seen = new Set([id]);
  let frontier = [id];
  for (let d = 0; d < 5 && frontier.length; d++) {
    const next: string[] = [];
    for (const f of frontier)
      for (const e of x.down.get(f) ?? [])
        if (!seen.has(e.dst)) {
          seen.add(e.dst);
          chain.push(e.dst);
          next.push(e.dst);
        }
    frontier = next.slice(0, 4);
  }
  return { carried, chain: chain.slice(0, 8) };
}
function lpEdges(x: SetIndex, a: Actions): GE[] {
  return x.g.element_edges.map((e, i) => ({
    id: `lp${i}`,
    source: k("el", e.src),
    target: k("el", e.dst),
    style: "exact" as const,
    color: "var(--ink)",
    title: `${e.rule} - click for evidence`,
    data: { run: () => a.openEEdge(e) },
  }));
}

export function elGraph(x: SetIndex, id: string, a: Actions): Built {
  const e0 = x.els.get(id)!;
  const more: string[] = [];
  const { carried, chain } = loadPathAround(x, id);
  const col0 = [
    ...carried.map((y) => elNode(x.els.get(y)!, a)),
    { ...elNode(e0, a), tone: "accent" as const },
    ...chain.map((y) => elNode(x.els.get(y)!, a)),
  ];
  const edges: GE[] = lpEdges(x, a);
  const insts = (x.instByEl.get(id) ?? []).slice(0, 10);
  const col1 = insts.map((i) => instNode(i, a));
  for (const i of insts)
    edges.push({
      id: `cn:${i.id}>${id}`,
      source: k("cinst", i.id),
      target: k("el", id),
      style: "exact",
      color: CONN_COL,
      title: `${i.via}: ${i.attach_rule} - click for evidence`,
      data: { run: () => a.openInstEl(i, id) },
    });
  const LIM = 14;
  const col2: GN[] = [];
  const col3: GN[] = [];
  if (x.ig) {
    const rls = x.rlByEl.get(id) ?? [];
    const retargeted = new Set(rls.map((l) => l.calc));
    const recIds: string[] = [];
    for (const l of rls)
      for (const rid of l.records) {
        if (!recIds.includes(rid)) recIds.push(rid);
        if (recIds.indexOf(rid) < LIM)
          edges.push(
            linkEdge(
              `rl:${l.calc}:${rid}`,
              k("el", id),
              k("rec", rid),
              l.score,
              `${l.tier} - ${l.rule} - click to compare evidence`,
              () => a.openRLink(l, rid),
            ),
          );
      }
    recIds
      .slice(0, LIM)
      .forEach(
        (rid) => x.recs.has(rid) && col2.push(recNode(x.recs.get(rid)!, a)),
      );
    if (recIds.length > LIM)
      more.push(
        `+${recIds.length - LIM} more linked calc records in the inspector`,
      );
    for (const l of (x.linksByEl.get(id) ?? [])
      .filter((y) => !retargeted.has(y.calc))
      .slice(0, 6)) {
      col2.push(calcNode(x.calcs.get(l.calc)!, a));
      edges.push(
        linkEdge(
          `pl:${l.calc}`,
          k("el", id),
          k("calc", l.calc),
          l.score,
          `${l.tier} - page link (no record on the page matched) - ${l.rule}`,
          () => a.openLink(l),
        ),
      );
    }
    const seen3 = new Set(recIds.slice(0, LIM));
    for (const rid of recIds.slice(0, 6))
      for (const e of recEdgesOut(x, rid).slice(0, 3)) {
        if (!e.dst) continue;
        edges.push(recEdge(e, a));
        if (seen3.has(e.dst) || col3.length >= 10) continue;
        seen3.add(e.dst);
        const s = x.recs.get(e.dst);
        if (s) col3.push(recNode(s, a));
      }
  } else {
    // no integrated layer: calc pages and one hop of calc feeds around them
    const ls = x.linksByEl.get(id) ?? [];
    for (const l of ls.slice(0, LIM)) {
      col2.push(
        calcNode(x.calcs.get(l.calc)!, a, `${x.calcs.get(l.calc)!.software}`),
      );
      edges.push(
        linkEdge(
          `pl:${l.calc}`,
          k("el", id),
          k("calc", l.calc),
          l.score,
          `${l.tier} ${Math.round(l.score * 100)}% - ${l.rule} - click to compare evidence`,
          () => a.openLink(l),
        ),
      );
    }
    if (ls.length > LIM)
      more.push(`+${ls.length - LIM} more linked calc pages in the inspector`);
    const feeds = new Set<string>();
    for (const l of ls.slice(0, 6))
      for (const e of [
        ...(x.cin.get(l.calc) ?? []),
        ...(x.cout.get(l.calc) ?? []),
      ].slice(0, 3))
        feeds.add(e.src === l.calc ? e.dst : e.src);
    for (const f of [...feeds].slice(0, 12))
      col3.push(calcNode(x.calcs.get(f)!, a));
    edges.push(...calcFeedEdges(x, a));
  }
  const { lanes, nodes } = lanesOf([
    [
      {
        id: "els",
        label: "Elements (drawings)",
        info: "graph.set-lane-elements",
      },
      col0,
    ],
    [
      { id: "conn", label: "Connections", info: "graph.set-lane-connections" },
      col1,
    ],
    [
      {
        id: "recs",
        label: x.ig ? "Calc records" : "Calc pages",
        info: "graph.set-lane-records",
      },
      col2,
    ],
    [
      {
        id: "lp",
        label: x.ig ? "Calc load path" : "Calc feeds",
        info: "graph.set-lane-calc-load-path",
      },
      col3,
    ],
  ]);
  return { kind: "el", nodes, edges: keep(edges, nodes), lanes, more };
}

function calcFeedEdges(x: SetIndex, a: Actions): GE[] {
  return x.g.calc_edges.map((e, i) => ({
    id: `ce${i}`,
    source: k("calc", e.src),
    target: k("calc", e.dst),
    style: "plain" as const,
    color: "var(--calc)",
    title: `${e.rule}: ${e.labels.slice(0, 5).join(", ")} - click for evidence`,
    data: { run: () => a.openCEdge(e) },
  }));
}

// ---------------------------------------------------------------- calc page
export function calcGraph(x: SetIndex, id: string, a: Actions): Built {
  const more: string[] = [];
  const ls = x.linksByCalc.get(id) ?? [];
  const els = [...new Set(ls.map((l) => l.el))];
  if (els.length > 18)
    more.push(`+${els.length - 18} more linked elements in the inspector`);
  const ins = (x.cin.get(id) ?? []).map((e) => e.src);
  const outs = (x.cout.get(id) ?? []).map((e) => e.dst);
  const insS = ins.slice(0, 8);
  const outsS = outs.filter((o) => !insS.includes(o)).slice(0, 10);
  if (ins.length > 8 || outs.length > 10)
    more.push(`${ins.length} pages feed this page, it feeds ${outs.length}`);
  const edges: GE[] = [...lpEdges(x, a), ...calcFeedEdges(x, a)];
  for (const l of ls)
    edges.push(
      linkEdge(
        `pl:${l.el}`,
        k("el", l.el),
        k("calc", l.calc),
        l.score,
        `${l.tier} ${Math.round(l.score * 100)}% - ${l.rule} - click to compare evidence`,
        () => a.openLink(l),
      ),
    );
  const c = x.calcs.get(id)!;
  const { lanes, nodes } = lanesOf([
    [
      {
        id: "els",
        label: "Elements (drawings)",
        info: "graph.set-lane-elements",
      },
      els.slice(0, 18).map((e) => elNode(x.els.get(e)!, a)),
    ],
    [
      { id: "in", label: "Pages feeding it", info: "graph.set-lane-pages-in" },
      insS.map((p) =>
        calcNode(x.calcs.get(p)!, a, `${x.calcs.get(p)!.software}`),
      ),
    ],
    [
      { id: "page", label: "Calc page", info: "graph.set-lane-calc-page" },
      [
        {
          ...calcNode(c, a, `${c.software}${c.level ? " · " + c.level : ""}`),
          tone: "accent" as const,
        },
      ],
    ],
    [
      { id: "out", label: "Pages it feeds", info: "graph.set-lane-pages-out" },
      outsS.map((p) =>
        calcNode(x.calcs.get(p)!, a, `${x.calcs.get(p)!.software}`),
      ),
    ],
  ]);
  return { kind: "calc", nodes, edges: keep(edges, nodes), lanes, more };
}

// ---------------------------------------------------------------- calc record: its calc load path
export function recGraph(x: SetIndex, id: string, a: Actions): Built | null {
  const r = x.recs.get(id);
  if (!r) return null;
  const edges: GE[] = [];
  const more: string[] = [];
  const up: GN[][] = [[], []];
  const seen = new Set([r.id]);
  let front = [r.id];
  for (let d = 0; d < 2; d++) {
    const next: string[] = [];
    for (const f of front)
      for (const e of x.rin.get(f) ?? []) {
        edges.push(recEdge(e, a));
        if (seen.has(e.src)) continue;
        seen.add(e.src);
        if (up[d].length >= 9) continue;
        const s = x.recs.get(e.src);
        if (s) {
          up[d].push(recNode(s, a));
          next.push(e.src);
        }
      }
    if (d === 0 && (x.rin.get(r.id) ?? []).length > 9)
      more.push(
        `${(x.rin.get(r.id) ?? []).length} records feed this one (9 shown - all in the inspector)`,
      );
    front = next;
  }
  const down: GN[][] = [[], [], []];
  front = [r.id];
  for (let d = 0; d < 3; d++) {
    const next: string[] = [];
    for (const f of front)
      recEdgesOut(x, f).forEach((e, i) => {
        if (!e.dst) {
          if (down[d].length < 9) {
            const gid = `absent:${e.src}#${i}`;
            down[d].push({
              id: gid,
              kind: "gap",
              label:
                e.kind === "member->support"
                  ? `no support (${e.end ?? "end"})`
                  : "not traced",
              sub: e.rule,
              title: `${e.rule}\nclick: show the row with no support`,
              data: { run: () => a.openREdge(e) },
            });
            edges.push(recEdge(e, a, gid));
          }
          return;
        }
        edges.push(recEdge(e, a));
        if (seen.has(e.dst)) return;
        seen.add(e.dst);
        if (down[d].length >= 9) return;
        const s = x.recs.get(e.dst);
        if (s) {
          down[d].push(recNode(s, a));
          next.push(e.dst);
        }
      });
    front = next;
  }
  const rls = x.rlByRec.get(r.id) ?? [];
  const els = [...new Set(rls.map((l) => l.el))];
  if (els.length > 12)
    more.push(`+${els.length - 12} more linked elements in the inspector`);
  for (const l of rls)
    edges.push(
      linkEdge(
        `rl:${l.el}:${l.calc}`,
        k("el", l.el),
        k("rec", r.id),
        l.score,
        `${l.tier} - ${l.rule} - click to compare evidence`,
        () => a.openRLink(l, r.id),
      ),
    );
  const conn: GN[] = [];
  if (r.type === "connection_design") {
    const t = x.ctypes.get(PARAPET_DETAIL);
    if (t) {
      conn.push({
        ...typeNode(t, a),
        dashed: true,
        sub: "candidate by title only",
      });
      edges.push({
        id: `cand:${t.id}`,
        source: k("rec", r.id),
        target: k("ctype", t.id),
        style: "inferred",
        color: CONN_COL,
        title: "candidate detail by title only - not a link",
        data: { run: () => a.select({ kind: "ctype", id: t.id }) },
      });
    }
  }
  const { lanes, nodes } = lanesOf([
    [
      {
        id: "els",
        label: "Elements linked",
        info: "graph.set-lane-rec-elements",
      },
      els.slice(0, 12).map((e) => elNode(x.els.get(e)!, a)),
    ],
    [
      { id: "up2", label: "Feeds (2 hops)", info: "graph.set-lane-rec-feeds2" },
      up[1],
    ],
    [{ id: "up1", label: "Feeds", info: "graph.set-lane-rec-feeds" }, up[0]],
    [
      { id: "rec", label: "Calc record", info: "graph.set-lane-rec" },
      [recNode(r, a, true)],
    ],
    [
      { id: "d1", label: "Carried by", info: "graph.set-lane-rec-carried" },
      down[0],
    ],
    [{ id: "d2", label: "then", info: "graph.set-lane-rec-then" }, down[1]],
    [{ id: "d3", label: "then", info: "graph.set-lane-rec-then" }, down[2]],
    [
      {
        id: "conn",
        label: "Connection detail",
        info: "graph.set-lane-rec-detail",
      },
      conn,
    ],
  ]);
  return {
    kind: "rec",
    nodes,
    edges: keep(edges, nodes),
    lanes,
    more,
    hint: `Calc load path of ${r.title} - ${r.run_title}. Solid = exact join on a shared label, dashed = inferred from coordinates, red dotted = no support found. Click any edge for both rows on the original pages.`,
  };
}

// ---------------------------------------------------------------- connection detail / instance
export function connGraph(
  x: SetIndex,
  sel: NonNullable<Sel>,
  a: Actions,
): Built {
  const edges: GE[] = [];
  const more: string[] = [];
  let insts: CInst[];
  let t: CType | undefined;
  let selInst: CInst | undefined;
  if (sel.kind === "ctype") {
    t = x.ctypes.get(sel.id);
    insts = (t?.instances ?? []).map((i) => x.cinst.get(i)!).filter(Boolean);
  } else {
    selInst = x.cinst.get(sel.id);
    insts = selInst ? [selInst] : [];
    t = selInst?.type_id ? x.ctypes.get(selInst.type_id) : undefined;
  }
  const elIds: string[] = [];
  for (const i of insts.slice(0, 14))
    for (const at of i.attached) {
      if (!elIds.includes(at.id)) elIds.push(at.id);
      edges.push({
        id: `cn:${at.id}>${i.id}`,
        source: k("el", at.id),
        target: k("cinst", i.id),
        style: "exact",
        color: CONN_COL,
        title: `${at.role ?? "attached"} (${at.dist} pt) - click for evidence`,
        data: { run: () => a.openInstEl(i, at.id) },
      });
    }
  if (insts.length > 14)
    more.push(`+${insts.length - 14} more instances in the inspector`);
  if (t)
    for (const i of insts.slice(0, 14))
      edges.push({
        id: `io:${i.id}`,
        source: k("cinst", i.id),
        target: k("ctype", t.id),
        style: "exact",
        color: CONN_COL,
        title: `instance of ${t.id}`,
        data: { run: () => a.select({ kind: "ctype", id: t!.id }) },
      });
  const col3: GN[] = [];
  const par = x.recs.get(PARAPET_REC);
  if (t?.id === PARAPET_DETAIL && par) {
    col3.push({
      ...recNode(par, a),
      dashed: true,
      sub: "candidate by title only",
    });
    edges.push({
      id: `cand:${par.id}`,
      source: k("ctype", t.id),
      target: k("rec", par.id),
      style: "inferred",
      color: CONN_COL,
      title: "candidate design by title only - the calc cites no detail",
      data: { run: () => a.select({ kind: "rec", id: par.id }) },
    });
  } else if (t) {
    const gid = `nocalc:${t.id}`;
    col3.push({
      id: gid,
      kind: "gap",
      label: "no connection calc",
      sub: "no calc page designs this detail",
      data: {
        run: () => a.openFindingKind("no connection calcs in the main package"),
      },
    });
    edges.push({
      id: `nc:${t.id}`,
      source: k("ctype", t.id),
      target: gid,
      style: "absent",
      title: "no calc page designs this detail",
      data: {
        run: () => a.openFindingKind("no connection calcs in the main package"),
      },
    });
  }
  const { lanes, nodes } = lanesOf([
    [
      { id: "els", label: "Elements", info: "graph.set-lane-conn-elements" },
      elIds
        .slice(0, 16)
        .filter((e) => x.els.has(e))
        .map((e) => elNode(x.els.get(e)!, a)),
    ],
    [
      {
        id: "inst",
        label: "Instances on the sheets",
        info: "graph.set-lane-conn-instances",
      },
      insts
        .slice(0, 14)
        .map((i) => ({
          ...instNode(i, a),
          tone: i === selInst ? ("accent" as const) : undefined,
        })),
    ],
    [
      {
        id: "type",
        label: "Connection detail",
        info: "graph.set-lane-conn-detail",
      },
      t
        ? [
            {
              ...typeNode(t, a),
              tone: sel.kind === "ctype" ? ("accent" as const) : undefined,
            },
          ]
        : [],
    ],
    [
      { id: "calc", label: "Design calc", info: "graph.set-lane-conn-calc" },
      col3,
    ],
  ]);
  return {
    kind: "conn",
    nodes,
    edges: keep(edges, nodes),
    lanes,
    more,
    hint: t
      ? `${t.id} ${t.title} - ${insts.length} instance${insts.length === 1 ? "" : "s"} (callout bubbles, plan symbols, text references), ${elIds.length} attached element${elIds.length === 1 ? "" : "s"}.`
      : `Plan symbol without a detail number${selInst?.legend_text ? `: ${selInst.legend_text}` : ""}`,
  };
}

export function buildGraph(x: SetIndex, sel: Sel, a: Actions): Built {
  if (!sel) return overviewGraph(x, a);
  if (sel.kind === "rec") return recGraph(x, sel.id, a) ?? overviewGraph(x, a);
  if (sel.kind === "ctype" || sel.kind === "cinst") return connGraph(x, sel, a);
  if (sel.kind === "el") return elGraph(x, sel.id, a);
  return calcGraph(x, sel.id, a);
}
export const selNodeId = (sel: Sel) => (sel ? `${sel.kind}:${sel.id}` : null);
