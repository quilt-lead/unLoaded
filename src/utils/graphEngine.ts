// Pure helpers over the VIEW MODEL (src/types/bim.ts): node predicates, load-path tracing over the
// element graph's directed load-path edges, the radial layout, and the calc graph's mapping satellites.
// Nothing here infers structure: hierarchy, connectivity and load direction come from the element
// graph (src/loaders/elementGraphToBim.ts), calcs and calc dependencies from the backend
// (src/data/loadProject.ts).
import type { BimLink, BimNode, CalcLink, ConnectivityEdge, LoadPathEdge, TraceDirection } from '../types/bim';

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
      return node.elementKind ? node.elementKind.charAt(0).toUpperCase() + node.elementKind.slice(1) : node.ifcType ? node.ifcType.replace(/^Ifc/, '') : 'Element';
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
 * Follow the element graph's directed load-path edges (`supports`: source delivers load to target) from the seeds:
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

  const nodeMap = new Map(nodes.map((n) => [n.id, n]));
  const instanceSeeds = seedIds.filter((id) => {
    const n = nodeMap.get(id);
    return n && isInstanceNode(n);
  });
  if (instanceSeeds.length === 0) return { chainNodeIds, chainLinkKeys };

  const downstreamAdj = new Map<string, string[]>();
  const upstreamAdj = new Map<string, string[]>();
  const addLoadPath = (sourceId: string, targetId: string) => {
    const downstream = downstreamAdj.get(sourceId) || [];
    if (!downstream.includes(targetId)) {
      downstream.push(targetId);
      downstreamAdj.set(sourceId, downstream);
    }

    const upstream = upstreamAdj.get(targetId) || [];
    if (!upstream.includes(sourceId)) {
      upstream.push(sourceId);
      upstreamAdj.set(targetId, upstream);
    }
  };

  // Graphs built by @unloaded/element-graph carry explicit, directed load-path links
  // (source is supported by target). Use those as-is. Older hand-authored graphs only
  // have undirected connectivity, so their direction is inferred by orientLoadLink.
  const hasDirectedLoadPath = rawLinks.some((l) => l.relation === 'load-path');

  rawLinks.forEach((l) => {
    if (hasDirectedLoadPath && l.relation !== 'load-path') return;
    const s = nodeMap.get(l.source);
    const t = nodeMap.get(l.target);
    if (!s || !t || !isInstanceNode(s) || !isInstanceNode(t)) return;

    const oriented = hasDirectedLoadPath ? l : orientLoadLink(s, t, l);
    addLoadPath(oriented.source, oriented.target);
  });

  const hasLoadPath = (fromId: string, toId: string) => {
    const pending = [fromId];
    const visited = new Set(pending);
    while (pending.length > 0) {
      const current = pending.pop()!;
      if (current === toId) return true;
      (downstreamAdj.get(current) || []).forEach((next) => {
        if (!visited.has(next)) {
          visited.add(next);
          pending.push(next);
        }
      });
    }
    return false;
  };

  const stackMembers = new Map<string, BimNode[]>();
  nodes.forEach((node) => {
    if (!isInstanceNode(node) || !node.parent || !isColumnStackNode(nodeMap.get(node.parent))) return;
    const members = stackMembers.get(node.parent) || [];
    members.push(node);
    stackMembers.set(node.parent, members);
  });

  stackMembers.forEach((members) => {
    if (members.length < 2) return;
    const hasFloorOrder = members.every((node) => typeof node.floorNum === 'number');
    const hasHeightOrder = members.every((node) => typeof node.pos3d?.[1] === 'number');
    if (!hasFloorOrder && !hasHeightOrder) return;

    const ordered = [...members].sort((a, b) => {
      const floorDelta = hasFloorOrder ? a.floorNum! - b.floorNum! : 0;
      return floorDelta || (hasHeightOrder ? a.pos3d![1] - b.pos3d![1] : 0);
    });

    for (let i = 1; i < ordered.length; i++) {
      const lower = ordered[i - 1]!;
      const upper = ordered[i]!;
      if (!hasLoadPath(upper.id, lower.id)) addLoadPath(upper.id, lower.id);
    }
  });

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

/** Elements physically connected to one element (element-graph `connects` / `part_of`). */
export function getConnectivityNeighbors(nodeId: string, connectivity: ConnectivityEdge[]): string[] {
  const out = new Set<string>();
  for (const e of connectivity) {
    if (e.source === nodeId) out.add(e.target);
    else if (e.target === nodeId) out.add(e.source);
  }
  return [...out];
}

// Get direct physical connectivity neighbors (e.g., Beam A101 <-> Connection <-> Column C2012)
export function getDirectConnectivityNeighbors(
  nodeId: string,
  nodes: BimNode[],
  rawLinks: BimLink[]
): BimNode[] {
  const nodeMap = new Map(nodes.map((n) => [n.id, n]));
  const neighborIds = new Set<string>();

  rawLinks.forEach((l) => {
    const s = nodeMap.get(l.source);
    const t = nodeMap.get(l.target);
    if (!s || !t || !isInstanceNode(s) || !isInstanceNode(t)) return;
    if (l.source === nodeId) neighborIds.add(l.target);
    if (l.target === nodeId) neighborIds.add(l.source);
  });

  return Array.from(neighborIds)
    .map((id) => nodeMap.get(id))
    .filter((n): n is BimNode => Boolean(n));
}

// Build the Structural Calculation Graph (Calculation Types -> PDF Calculation Packages -> Mapped Structural Elements)
export function buildCalculationGraph(
  elementNodes: BimNode[],
  projectName: string
): {
  calcNodes: BimNode[];
  calcLinks: BimLink[];
  docToElementIds: Map<string, string[]>;
  elementToCalcNodeIds: Map<string, string[]>;
} {
  const docToElementIds = new Map<string, string[]>();
  const elementToCalcNodeIds = new Map<string, string[]>();
  const docMetaMap = new Map<string, { doc: BimDocument; categoryKey: string; categoryLabel: string; color: string }>();

  const classifyCalcCategory = (node: BimNode, doc: BimDocument) => {
    const hay = `${node.parent || ''} ${node.ifcType || ''} ${doc.title} ${doc.type}`.toLowerCase();
    if (hay.includes('beam') || hay.includes('girder')) {
      return { key: 'calc-cat-beam', label: 'Beam Sizing Calcs', color: '#b45309' };
    }
    if (hay.includes('col')) {
      return { key: 'calc-cat-col', label: 'Column Sizing Calcs', color: '#15803d' };
    }
    if (hay.includes('conn') || hay.includes('fastener') || hay.includes('plate') || hay.includes('screw') || hay.includes('anchor')) {
      return { key: 'calc-cat-conn', label: 'Connection & Fastener Calcs', color: '#0e7490' };
    }
    if (hay.includes('slab') || hay.includes('roof')) {
      return { key: 'calc-cat-slab', label: 'Slab & Punching Shear Calcs', color: '#0369a1' };
    }
    if (hay.includes('wall') || hay.includes('core')) {
      return { key: 'calc-cat-wall', label: 'Shear Wall & Lateral Calcs', color: '#be123c' };
    }
    return { key: 'calc-cat-fdn', label: 'Foundation & Geotech Calcs', color: '#9a3412' };
  };

  elementNodes.forEach((elNode) => {
    if (isProjectNode(elNode) || isElementTypeNode(elNode)) return;
    const docs = getNodeDocuments(elNode);
    docs.forEach((doc) => {
      const calcNodeId = `calc-doc-${doc.id}`;
      if (!docToElementIds.has(calcNodeId)) {
        docToElementIds.set(calcNodeId, []);
      }
      if (!docToElementIds.get(calcNodeId)!.includes(elNode.id)) {
        docToElementIds.get(calcNodeId)!.push(elNode.id);
      }

      if (!elementToCalcNodeIds.has(elNode.id)) {
        elementToCalcNodeIds.set(elNode.id, []);
      }
      if (!elementToCalcNodeIds.get(elNode.id)!.includes(calcNodeId)) {
        elementToCalcNodeIds.get(elNode.id)!.push(calcNodeId);
      }

      if (!docMetaMap.has(calcNodeId)) {
        const cat = classifyCalcCategory(elNode, doc);
        docMetaMap.set(calcNodeId, {
          doc,
          categoryKey: cat.key,
          categoryLabel: cat.label,
          color: cat.color,
        });
      }
    });
  });

  const rawCalcNodes: BimNode[] = [
    {
      id: 'calc-root',
      label: projectName ? `${projectName} Calcs` : 'Calculation Graph',
      type: 'Project',
      level: 0,
      floor: 'ALL',
      floorNum: 0,
      r: 36,
      x: 0,
      y: 0,
      color: '#14AE5C',
      desc: `Structural Calculation Graph mapping ${docMetaMap.size} PDF calculation sheets to physical BIM elements.`,
    },
  ];
  const rawCalcLinks: BimLink[] = [];
  const addedCats = new Set<string>();

  docMetaMap.forEach(({ doc, categoryKey, categoryLabel, color }, calcNodeId) => {
    if (!addedCats.has(categoryKey)) {
      addedCats.add(categoryKey);
      rawCalcNodes.push({
        id: categoryKey,
        label: categoryLabel,
        type: 'Category',
        level: 1,
        floor: 'ALL',
        floorNum: 0,
        r: 26,
        x: 0,
        y: 0,
        color,
        desc: `${categoryLabel} — grouped engineering calculation packages.`,
      });
      rawCalcLinks.push({ source: 'calc-root', target: categoryKey, relation: 'hierarchy' });
    }

    const mappedCount = docToElementIds.get(calcNodeId)?.length || 1;
    rawCalcNodes.push({
      id: calcNodeId,
      label: doc.id.replace(/^doc-/, '').toUpperCase(),
      type: doc.type,
      level: 2,
      parent: categoryKey,
      floor: 'ALL',
      floorNum: 0,
      strengthLabel: `${doc.code} • ${doc.rev}`,
      axialLoadKn: mappedCount,
      r: mappedCount > 5 ? 14 : 11,
      x: 0,
      y: 0,
      color,
      desc: `${doc.title} (${doc.rev}, ${doc.pages} pp.) — Linked to ${mappedCount} structural element${mappedCount === 1 ? '' : 's'}.`,
      documents: [doc],
    });
    rawCalcLinks.push({ source: categoryKey, target: calcNodeId, relation: 'hierarchy' });
  });

  const laidOutCalcNodes = computeRadialLayout(rawCalcNodes);
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
    const fallbackAngle = (idx / Math.max(rawNodes.length, 1)) * Math.PI * 2;
    const isProj = isProjectNode(n);
    const isCategory = isElementTypeNode(n);
    return {
      ...n,
      x: Math.cos(fallbackAngle) * 320,
      y: Math.sin(fallbackAngle) * 320,
      r: n.r || (isProj ? 36 : isCategory ? 26 : 14),
      color: n.color || '#14AE5C',
    };
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
  // every category gets at least enough arc for its own circle on the type ring, the rest by demand
  const minArc = Math.min(0.32, (Math.PI * 2) / plan.length);
  const spare = Math.PI * 2 - minArc * plan.length;
  const arcOf = (p: (typeof plan)[number]) => minArc + (p.demand / total) * spare;

  let cursor = -Math.PI / 2 - arcOf(plan[0]) / 2;
  for (const p of plan) {
    const arc = arcOf(p);
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
        elementKind: el.elementKind,
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

export function normalizeGraphData(parsed: Partial<BimGraphData>, fallbackName: string): BimGraphData {
  const rawLinks: BimLink[] = Array.isArray(parsed.links)
    ? parsed.links.map((l: any) => ({
        ...l,
        source: l && typeof l.source === 'object' ? l.source.id : l.source,
        target: l && typeof l.target === 'object' ? l.target.id : l.target,
      }))
    : [];

  const rawNodes = Array.isArray(parsed.nodes) ? parsed.nodes : [];
  const projectLabel = parsed.projectName || (parsed as any).project || fallbackName;

  const hasProject = rawNodes.some(isProjectNode);
  const nodesWithProject: BimNode[] = hasProject
    ? rawNodes.map((n) => (isProjectNode(n) ? { ...n, label: projectLabel } : { ...n }))
    : [
        {
          id: 'proj-1',
          label: projectLabel,
          type: 'Project',
          level: 0,
          floor: 'ALL',
          floorNum: 0,
          r: 36,
          x: 0,
          y: 0,
          color: '#14AE5C',
          desc: `Root structural BIM model: ${projectLabel}`,
        },
        ...rawNodes,
      ];

  const laidOutNodes = computeRadialLayout(nodesWithProject);
  const links = buildHierarchyLinks(laidOutNodes, rawLinks);

  return {
    projectName: projectLabel,
    nodes: laidOutNodes,
    links,
  };
}


// =========================================================================
// DUAL-DATABASE DIFF ENGINE (BASE DB A vs COMPARE DB B)
// =========================================================================
export function computeDatabaseDiff(
  baseGraph: BimGraphData,
  baseRawLinks: BimLink[],
  compareGraph: BimGraphData,
  compareRawLinks: BimLink[]
): {
  mergedNodes: BimNode[];
  mergedRawLinks: BimLink[];
  mergedHierarchyLinks: BimLink[];
  summary: DatabaseDiffSummary;
} {
  const baseMap = new Map<string, BimNode>(baseGraph.nodes.map((n) => [n.id, n]));
  const compMap = new Map<string, BimNode>(compareGraph.nodes.map((n) => [n.id, n]));

  const allIds = new Set<string>([...baseMap.keys(), ...compMap.keys()]);
  const rawMergedNodes: BimNode[] = [];

  let addedCount = 0;
  let removedCount = 0;
  let modifiedCount = 0;
  let unchangedCount = 0;

  const inspectFields = (a: BimNode, b: BimNode): NodeDiffFieldChange[] => {
    const changes: NodeDiffFieldChange[] = [];
    if ((a.sectionSize || '') !== (b.sectionSize || '')) {
      changes.push({ field: 'Section / Profile', before: a.sectionSize || '—', after: b.sectionSize || '—' });
    }
    if ((a.strengthLabel || String(a.ratedStrength ?? '')) !== (b.strengthLabel || String(b.ratedStrength ?? ''))) {
      changes.push({
        field: 'Material / Strength',
        before: a.strengthLabel || `${a.ratedStrength ?? '—'} MPa`,
        after: b.strengthLabel || `${b.ratedStrength ?? '—'} MPa`,
      });
    }
    if ((a.axialLoadKn ?? 0) !== (b.axialLoadKn ?? 0)) {
      changes.push({
        field: 'Axial / Gravity Load',
        before: `${(a.axialLoadKn ?? 0).toLocaleString()} kN`,
        after: `${(b.axialLoadKn ?? 0).toLocaleString()} kN`,
      });
    }
    if (Math.round((a.utilization ?? 0) * 100) !== Math.round((b.utilization ?? 0) * 100)) {
      changes.push({
        field: 'Utilization',
        before: `${Math.round((a.utilization ?? 0) * 100)}%`,
        after: `${Math.round((b.utilization ?? 0) * 100)}%`,
      });
    }
    if ((a.floor || '') !== (b.floor || '')) {
      changes.push({ field: 'Level / Floor', before: a.floor || '—', after: b.floor || '—' });
    }
    const aDocs = (a.documents || []).map((d) => `${d.id}:${d.rev}`).join(',');
    const bDocs = (b.documents || []).map((d) => `${d.id}:${d.rev}`).join(',');
    if (aDocs !== bDocs) {
      changes.push({
        field: 'Mapped PDF / Rev',
        before: (a.documents || []).map((d) => `${d.id} (${d.rev})`).join(', ') || 'None',
        after: (b.documents || []).map((d) => `${d.id} (${d.rev})`).join(', ') || 'None',
      });
    }
    return changes;
  };

  allIds.forEach((id) => {
    const a = baseMap.get(id);
    const b = compMap.get(id);

    if (a && !b) {
      const status: DiffStatus = 'removed';
      if (isInstanceNode(a)) removedCount++;
      rawMergedNodes.push({
        ...a,
        diffStatus: status,
        diffChanges: [{ field: 'Presence', before: 'Present in primary model', after: 'Removed from comparison model' }],
        diffBefore: a,
      });
    } else if (!a && b) {
      const status: DiffStatus = 'added';
      if (isInstanceNode(b)) addedCount++;
      rawMergedNodes.push({
        ...b,
        diffStatus: status,
        diffChanges: [{ field: 'Presence', before: 'Not in primary model', after: 'Added to comparison model' }],
      });
    } else if (a && b) {
      if (isProjectNode(b)) {
        rawMergedNodes.push({
          ...b,
          label: `${baseGraph.projectName || 'Primary model'} vs ${compareGraph.projectName || 'Comparison model'}`,
          diffStatus: 'unchanged',
          diffChanges: [],
        });
        return;
      }
      const changes = isInstanceNode(b) ? inspectFields(a, b) : [];
      const status: DiffStatus = changes.length > 0 ? 'modified' : 'unchanged';
      if (isInstanceNode(b)) {
        if (status === 'modified') modifiedCount++;
        else unchangedCount++;
      }
      rawMergedNodes.push({
        ...b,
        diffStatus: status,
        diffChanges: changes,
        diffBefore: status === 'modified' ? a : undefined,
      });
    }
  });

  // Merge links from both DBs
  const linkKeySet = new Set<string>();
  const mergedRawLinks: BimLink[] = [];
  [...baseRawLinks, ...compareRawLinks].forEach((l) => {
    const k = `${l.source}=>${l.target}`;
    if (!linkKeySet.has(k)) {
      linkKeySet.add(k);
      mergedRawLinks.push(l);
    }
  });

  const laidOutNodes = computeRadialLayout(rawMergedNodes);
  const mergedHierarchyLinks = buildHierarchyLinks(laidOutNodes, mergedRawLinks);

  return {
    mergedNodes: laidOutNodes,
    mergedRawLinks,
    mergedHierarchyLinks,
    summary: {
      baseName: baseGraph.projectName || 'Primary model',
      compareName: compareGraph.projectName || 'Comparison model',
      addedCount,
      removedCount,
      modifiedCount,
      unchangedCount,
    },
  };
}
