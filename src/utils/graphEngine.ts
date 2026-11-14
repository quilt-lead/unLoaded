// Pure helpers over the VIEW MODEL (src/types/bim.ts): node predicates, load-path tracing over the
// backend's directed load-path edges, the radial layout, and the calc graph's mapping satellites.
// Nothing here infers structure: hierarchy, calcs, calc dependencies and load direction all come
// from the backend through src/data/loadProject.ts.
import type { BimLink, BimNode, CalcLink, LoadPathEdge, TraceDirection } from '../types/bim';

export function isProjectNode(n?: BimNode | null): boolean {
  return Boolean(n && (n.kind === 'project' || n.kind === 'calc-root'));
}

export function isElementTypeNode(n?: BimNode | null): boolean {
  return Boolean(n && (n.kind === 'category' || n.kind === 'calc-category'));
}

export function isFamilyNode(n?: BimNode | null): boolean {
  return Boolean(n && n.kind === 'family');
}

/** A leaf: an element, a calc, or an element drawn beside its calc. */
export function isInstanceNode(n?: BimNode | null): boolean {
  return Boolean(n && (n.kind === 'element' || n.kind === 'calc' || n.kind === 'mapped-element'));
}

export function isElementNode(n?: BimNode | null): boolean {
  return Boolean(n && n.kind === 'element');
}

export function getDisplayType(node: BimNode): string {
  switch (node.kind) {
    case 'project':
      return 'Project';
    case 'calc-root':
      return 'Calc package';
    case 'category':
      return 'Element type';
    case 'calc-category':
      return 'Calc group';
    case 'family':
      return 'Mark family';
    case 'calc':
      return 'Calculation';
    case 'mapped-element':
      return 'Linked element';
    default:
      return node.ifcType ? node.ifcType.replace(/^Ifc/, '') : 'Element';
  }
}

/** Element ids a graph node stands for (itself, or every element under a category / family / project). */
export function elementIdsUnder(nodeId: string, nodes: BimNode[]): string[] {
  const node = nodes.find((n) => n.id === nodeId);
  if (!node) return [];
  if (node.kind === 'element') return [node.id];
  if (node.kind === 'mapped-element') return node.elementId ? [node.elementId] : [];
  if (node.kind === 'project') return nodes.filter(isElementNode).map((n) => n.id);
  if (node.kind === 'category') return nodes.filter((n) => isElementNode(n) && n.categoryParent === node.id).map((n) => n.id);
  if (node.kind === 'family') return nodes.filter((n) => isElementNode(n) && n.parent === node.id).map((n) => n.id);
  return [];
}

export function loadPathKey(source: string, target: string): string {
  return `${source}->${target}`;
}

/**
 * Follow the backend's directed load-path edges (source delivers load to target) from the seeds:
 * 'down' toward the foundations, 'up' toward what the seeds carry, or both.
 */
export function computeLoadPathTrace(
  loadPath: LoadPathEdge[],
  seedIds: string[],
  traceDirection: TraceDirection,
  traceSteps: number,
): { chainNodeIds: Set<string>; chainLinkKeys: Set<string> } {
  const chainNodeIds = new Set<string>();
  const chainLinkKeys = new Set<string>();
  if (seedIds.length === 0 || loadPath.length === 0) return { chainNodeIds, chainLinkKeys };

  const down = new Map<string, string[]>();
  const up = new Map<string, string[]>();
  for (const e of loadPath) {
    (down.get(e.source) ?? down.set(e.source, []).get(e.source)!).push(e.target);
    (up.get(e.target) ?? up.set(e.target, []).get(e.target)!).push(e.source);
  }
  const seeds = seedIds.filter((id) => down.has(id) || up.has(id));
  if (seeds.length === 0) return { chainNodeIds, chainLinkKeys };

  const maxSteps = traceSteps >= 16 ? Infinity : Math.max(1, traceSteps);
  const walk = (start: string, adj: Map<string, string[]>, forward: boolean) => {
    const queue = [{ id: start, depth: 0 }];
    const visited = new Set([start]);
    while (queue.length > 0) {
      const { id, depth } = queue.shift()!;
      if (depth >= maxSteps) continue;
      for (const nxt of adj.get(id) ?? []) {
        chainNodeIds.add(nxt);
        chainLinkKeys.add(forward ? loadPathKey(id, nxt) : loadPathKey(nxt, id));
        if (!visited.has(nxt)) {
          visited.add(nxt);
          queue.push({ id: nxt, depth: depth + 1 });
        }
      }
    }
  };

  for (const s of seeds) {
    chainNodeIds.add(s);
    if (traceDirection === 'down' || traceDirection === 'both') walk(s, down, true);
    if (traceDirection === 'up' || traceDirection === 'both') walk(s, up, false);
  }
  return { chainNodeIds, chainLinkKeys };
}

/** Direct load-path neighbours of one element. */
export function getLoadNeighbors(nodeId: string, loadPath: LoadPathEdge[]): { carriesFrom: LoadPathEdge[]; deliversTo: LoadPathEdge[] } {
  return {
    carriesFrom: loadPath.filter((e) => e.target === nodeId),
    deliversTo: loadPath.filter((e) => e.source === nodeId),
  };
}

// ------------------------------------------------------------------------------------------------
// Radial layout: project at the centre, categories on a ring, then either mark-family clusters
// (hub + concentric rings of members, any size) or, for categories without families, arcs of
// leaves (the calc graph).

const TYPE_RADIUS = 215;

interface Cluster {
  hub: BimNode;
  members: BimNode[];
  memberR: number;
  rings: { radius: number; count: number }[];
  R: number;
}

function buildCluster(hub: BimNode, members: BimNode[]): Cluster {
  const memberR = members.length > 60 ? 4.6 : members.length > 16 ? 5.6 : 6.8;
  const pitch = memberR * 2 * 1.42;
  const rings: Cluster['rings'] = [];
  let radius = hub.r + 9 + memberR;
  let placed = 0;
  while (placed < members.length) {
    const cap = Math.max(6, Math.floor((2 * Math.PI * radius) / pitch));
    const count = Math.min(cap, members.length - placed);
    rings.push({ radius, count });
    placed += count;
    radius += pitch * 1.06;
  }
  const R = rings.length ? rings[rings.length - 1].radius + memberR : hub.r;
  return { hub, members, memberR, rings, R };
}

export function computeRadialLayout(rawNodes: BimNode[]): BimNode[] {
  const nodes: BimNode[] = rawNodes.map((n, idx) => {
    const a = (idx / Math.max(rawNodes.length, 1)) * Math.PI * 2;
    return { ...n, x: Math.cos(a) * 320, y: Math.sin(a) * 320 };
  });

  const project = nodes.find(isProjectNode);
  if (project) {
    project.x = 0;
    project.y = 0;
  }
  const cats = nodes.filter(isElementTypeNode);
  if (cats.length === 0) return nodes;

  const childrenOf = new Map<string, BimNode[]>();
  for (const n of nodes) {
    if (!n.parent) continue;
    (childrenOf.get(n.parent) ?? childrenOf.set(n.parent, []).get(n.parent)!).push(n);
  }

  const plan = cats.map((cat) => {
    const kids = childrenOf.get(cat.id) ?? [];
    const clusters = kids.filter(isFamilyNode).map((f) => buildCluster(f, (childrenOf.get(f.id) ?? []).filter(isInstanceNode)));
    const leaves = kids.filter(isInstanceNode);
    const demand = clusters.reduce((acc, c) => acc + 2 * c.R + 22, 0) + leaves.length * 34;
    return { cat, clusters, leaves, demand: Math.max(demand, 90) };
  });
  const total = plan.reduce((acc, p) => acc + p.demand, 0);

  let cursor = -Math.PI / 2 - (plan[0].demand / total) * Math.PI;
  for (const p of plan) {
    const arc = (p.demand / total) * Math.PI * 2;
    const angle = cursor + arc / 2;
    cursor += arc;
    p.cat.x = Math.cos(angle) * TYPE_RADIUS;
    p.cat.y = Math.sin(angle) * TYPE_RADIUS;

    const usable = Math.max(arc * 0.88, 0.25);
    let rowStart = TYPE_RADIUS + 110;

    // family clusters, row by row outward
    const queue = [...p.clusters];
    while (queue.length) {
      const row: Cluster[] = [];
      let rMax = 0;
      while (queue.length) {
        const c = queue[0];
        const nextMax = Math.max(rMax, c.R);
        const d = rowStart + nextMax;
        const width = [...row, c].reduce((acc, x) => acc + (2 * x.R + 16) / d, 0);
        if (row.length && width > usable) break;
        row.push(queue.shift()!);
        rMax = nextMax;
      }
      let d = rowStart + rMax;
      let width = row.reduce((acc, x) => acc + (2 * x.R + 16) / d, 0);
      if (width > usable) {
        d = row.reduce((acc, x) => acc + 2 * x.R + 16, 0) / usable;
        width = usable;
      }
      let a = angle - width / 2;
      for (const c of row) {
        const w = (2 * c.R + 16) / d;
        const ca = a + w / 2;
        a += w;
        c.hub.x = Math.cos(ca) * d;
        c.hub.y = Math.sin(ca) * d;
        let k = 0;
        c.rings.forEach((ring, ri) => {
          for (let i = 0; i < ring.count; i++) {
            const m = c.members[k++];
            const ma = (i / ring.count) * Math.PI * 2 - Math.PI / 2 + (ri % 2 ? Math.PI / ring.count : 0);
            m.x = c.hub.x + Math.cos(ma) * ring.radius;
            m.y = c.hub.y + Math.sin(ma) * ring.radius;
            m.r = c.memberR;
          }
        });
      }
      rowStart = d + rMax + 26;
    }

    // leaves straight under the category, in arcs
    const leaves = p.leaves;
    if (leaves.length) {
      const pad = leaves.length > 80 ? 26 : 38;
      const spread = Math.min(arc * 0.82, Math.PI * 1.2);
      let placed = 0;
      let ring = 0;
      const base = p.clusters.length ? rowStart : TYPE_RADIUS + 150;
      while (placed < leaves.length) {
        const dist = base + ring * pad * 1.2;
        const max = Math.max(1, Math.min(18, Math.floor((dist * spread) / pad)));
        const count = Math.min(max, leaves.length - placed);
        const step = spread / count;
        for (let i = 0; i < count; i++) {
          const la = angle - spread / 2 + (i + 0.5) * step;
          leaves[placed + i].x = Math.cos(la) * dist;
          leaves[placed + i].y = Math.sin(la) * dist;
        }
        placed += count;
        ring++;
      }
    }
  }
  return nodes;
}

/**
 * The calc graph with the selected calc's linked elements drawn around it, each joined by a
 * calc-mapping edge that carries the link's review state (so edge styling shows confirmed /
 * proposed / rejected / linked by hand).
 */
export function withMappingSatellites(
  calcNodes: BimNode[],
  calcLinks: BimLink[],
  anchorCalcKey: string | null,
  elementNodes: BimNode[],
): { nodes: BimNode[]; links: BimLink[] } {
  if (!anchorCalcKey) return { nodes: calcNodes, links: calcLinks };
  const anchor = calcNodes.find((n) => n.kind === 'calc' && n.calcKey === anchorCalcKey);
  if (!anchor) return { nodes: calcNodes, links: calcLinks };

  const linked = elementNodes
    .filter(isElementNode)
    .map((el) => ({ el, link: (el.calcLinks ?? []).find((l) => l.calcKey === anchorCalcKey) }))
    .filter((x): x is { el: BimNode; link: CalcLink } => x.link !== undefined)
    .sort((a, b) => b.link.confidence - a.link.confidence)
    .slice(0, 120);
  if (!linked.length) return { nodes: calcNodes, links: calcLinks };

  const out = Math.hypot(anchor.x, anchor.y) || 1;
  const ux = anchor.x / out;
  const uy = anchor.y / out;
  const satR = linked.length > 40 ? 4.2 : 5.5;
  const pitch = satR * 2 * 1.5;
  const sats: BimNode[] = [];
  const links: BimLink[] = [];
  let placed = 0;
  let radius = anchor.r + 30;
  while (placed < linked.length) {
    // a fan opening away from the centre so the satellites do not cover the rest of the graph
    const spread = Math.PI * 1.25;
    const cap = Math.max(4, Math.floor((radius * spread) / pitch));
    const count = Math.min(cap, linked.length - placed);
    const base = Math.atan2(uy, ux);
    for (let i = 0; i < count; i++) {
      const { el, link } = linked[placed + i];
      const a = base - spread / 2 + ((i + 0.5) / count) * spread;
      const id = `map:${anchorCalcKey}:${el.id}`;
      sats.push({
        id,
        label: el.label,
        kind: 'mapped-element',
        level: 3,
        parent: anchor.id,
        elementId: el.id,
        ifcType: el.ifcType,
        storey: el.storey,
        link,
        r: satR,
        x: anchor.x + Math.cos(a) * radius,
        y: anchor.y + Math.sin(a) * radius,
        desc: el.desc,
      });
      links.push({ source: anchor.id, target: id, relation: 'calc-mapping', review: link.review, confidence: link.confidence });
    }
    placed += count;
    radius += pitch * 1.1;
  }
  return { nodes: [...calcNodes, ...sats], links: [...calcLinks, ...links] };
}

// Center-to-center radial spline: every wire starts at (s.x, s.y) and terminates at (t.x, t.y)
export function computeCenterToCenterSplinePath(s: BimNode, t: BimNode): string {
  const sx = Number.isFinite(s.x) ? s.x : 0;
  const sy = Number.isFinite(s.y) ? s.y : 0;
  const tx = Number.isFinite(t.x) ? t.x : 0;
  const ty = Number.isFinite(t.y) ? t.y : 0;

  const dx = tx - sx;
  const dy = ty - sy;
  const dist = Math.hypot(dx, dy) || 1;
  const chordUx = dx / dist;
  const chordUy = dy / dist;

  const sRad = Math.hypot(sx, sy);
  const tRad = Math.hypot(tx, ty);

  if (sRad < 1e-3 || isProjectNode(s)) {
    return `M ${sx.toFixed(2)} ${sy.toFixed(2)} L ${tx.toFixed(2)} ${ty.toFixed(2)}`;
  }

  const sOutX = sx / sRad;
  const sOutY = sy / sRad;
  const tOutX = tRad > 1e-3 ? tx / tRad : chordUx;
  const tOutY = tRad > 1e-3 ? ty / tRad : chordUy;

  const cross = Math.abs(sOutX * chordUy - sOutY * chordUx);
  if (cross < 0.045) {
    return `M ${sx.toFixed(2)} ${sy.toFixed(2)} L ${tx.toFixed(2)} ${ty.toFixed(2)}`;
  }

  const endDirX = tOutX * 0.65 + chordUx * 0.35;
  const endDirY = tOutY * 0.65 + chordUy * 0.35;
  const endNorm = Math.hypot(endDirX, endDirY) || 1;
  const eUx = endDirX / endNorm;
  const eUy = endDirY / endNorm;

  const h1 = dist * 0.44;
  const h2 = dist * 0.42;

  const c1x = sx + sOutX * h1;
  const c1y = sy + sOutY * h1;
  const c2x = tx - eUx * h2;
  const c2y = ty - eUy * h2;

  return `M ${sx.toFixed(2)} ${sy.toFixed(2)} C ${c1x.toFixed(2)} ${c1y.toFixed(2)}, ${c2x.toFixed(2)} ${c2y.toFixed(2)}, ${tx.toFixed(2)} ${ty.toFixed(2)}`;
}

/** A gentle arc between two leaves (calc -> calc dependencies, load-path edges): bows to the left of travel. */
export function computeArcPath(s: BimNode, t: BimNode, bow = 0.18): string {
  const dx = t.x - s.x;
  const dy = t.y - s.y;
  const mx = (s.x + t.x) / 2 - dy * bow;
  const my = (s.y + t.y) / 2 + dx * bow;
  return `M ${s.x.toFixed(2)} ${s.y.toFixed(2)} Q ${mx.toFixed(2)} ${my.toFixed(2)} ${t.x.toFixed(2)} ${t.y.toFixed(2)}`;
}
