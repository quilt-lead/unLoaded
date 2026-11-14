import {
  BimDocument,
  BimGraphData,
  BimLink,
  BimNode,
  FlattenedDocument,
  DatabaseDiffSummary,
  DiffStatus,
  NodeDiffFieldChange,
  TraceDirection,
} from '../types/bim';
import { getEffectiveNodeColor } from './colors';

export function isProjectNode(n?: BimNode | null): boolean {
  return Boolean(n && (n.type === 'Project' || n.level === 0));
}

export function isElementTypeNode(n?: BimNode | null): boolean {
  return Boolean(n && (n.type === 'Category' || n.level === 1));
}

export function isColumnStackNode(n?: BimNode | null): boolean {
  return Boolean(n && (n.type === 'ColumnStack' || n.level === 1.5));
}

export function isInstanceNode(n?: BimNode | null): boolean {
  return Boolean(n && !isProjectNode(n) && !isElementTypeNode(n) && !isColumnStackNode(n));
}

export function getDisplayType(node: BimNode): string {
  if (isProjectNode(node)) return 'Project';
  if (isElementTypeNode(node)) return 'Element Type';
  if (isColumnStackNode(node)) return 'Column Stack';
  return node.type || 'Instance';
}

export function getNodeDocuments(node?: BimNode | null): BimDocument[] {
  if (!node) return [];
  if (Array.isArray(node.documents) && node.documents.length > 0) {
    return node.documents.map((d) => ({
      ...d,
      revisions: d.revisions || [
        {
          rev: d.rev || 'Rev B',
          date: d.date || '2026-10-21',
          pages: d.pages || 4,
          pageRef: d.pageRef || 'pp. 1–4',
          summary: d.summary || 'Issued for structural design coordination.',
        },
        {
          rev: 'Rev A',
          date: '2026-09-12',
          pages: Math.max(2, (d.pages || 4) - 1),
          pageRef: 'pp. 1–3',
          summary: 'Initial sizing & preliminary member check submittal.',
        },
      ],
    }));
  }
  return [
    {
      id: `doc-${node.id}`,
      title: `${node.label} Structural Calculation Sheet`,
      type: 'Calculation (PDF)',
      code: 'IFC 4.3 / ACI 318 / AISC 360',
      rev: 'Rev A',
      pages: 4,
      pageRef: 'pp. 1–4',
      date: '2026-10-15',
      summary: node.desc || 'Mapped structural engineering calculation.',
      revisions: [
        {
          rev: 'Rev A',
          date: '2026-10-15',
          pages: 4,
          pageRef: 'pp. 1–4',
          summary: node.desc || 'Initial structural sizing calculation.',
        },
      ],
    },
  ];
}

export function getAllDocumentsFlattened(
  nodes: BimNode[],
  matchingNodeIds: Set<string>,
  heatmapMode: boolean
): FlattenedDocument[] {
  const byDocId = new Map<string, FlattenedDocument>();

  nodes.forEach((node) => {
    if (matchingNodeIds.size > 0 && isInstanceNode(node) && !matchingNodeIds.has(node.id)) {
      return;
    }
    const docs = getNodeDocuments(node);
    docs.forEach((doc) => {
      const existing = byDocId.get(doc.id);
      if (existing) {
        if (!existing.mappedElementIds.includes(node.id)) {
          existing.mappedElementIds.push(node.id);
        }
      } else {
        byDocId.set(doc.id, {
          ...doc,
          nodeId: node.id,
          nodeLabel: node.label,
          nodeColor: getEffectiveNodeColor(node, heatmapMode),
          nodeDisplayType: getDisplayType(node),
          mappedElementIds: [node.id],
        });
      }
    });
  });

  return Array.from(byDocId.values());
}

export function getStructuralGravityRank(node?: BimNode | null): number {
  if (!node) return 99;
  const id = (node.id || '').toLowerCase();
  const label = (node.label || '').toLowerCase();
  const parent = (node.parent || '').toLowerCase();
  const desc = (node.desc || '').toLowerCase();

  if (parent === 'cat-pile' || id.startsWith('pile-')) return 7;
  if (parent === 'cat-mat' || parent === 'cat-pcap' || id.startsWith('mat-') || id.startsWith('pcap-')) return 6;
  if (parent === 'cat-conn' || id.startsWith('conn-')) {
    return label.includes('bp') || desc.includes('base plate') ? 5 : 3;
  }
  if (parent === 'cat-col' || parent === 'cat-wall' || id.startsWith('col-') || id.startsWith('wall-')) return 4;
  if (parent === 'cat-mframe' || id.startsWith('mf-') || id.startsWith('smf-')) return 3;
  if (parent === 'cat-beam' || id.startsWith('beam-')) {
    return node.beamRole === 'InfillBeam' || id.startsWith('beam-b-') ? 2 : 3;
  }
  if (parent === 'cat-slab' || id.startsWith('slab-')) return 1;
  return 4;
}

export function orientLoadLink(sNode: BimNode, tNode: BimNode, rawLink: BimLink): BimLink {
  const sFloor = typeof sNode.floorNum === 'number' ? sNode.floorNum : 0;
  const tFloor = typeof tNode.floorNum === 'number' ? tNode.floorNum : 0;

  if (sFloor !== tFloor) {
    return sFloor > tFloor
      ? { ...rawLink, source: sNode.id, target: tNode.id, isLoadPath: true }
      : { ...rawLink, source: tNode.id, target: sNode.id, isLoadPath: true };
  }

  const sRank = getStructuralGravityRank(sNode);
  const tRank = getStructuralGravityRank(tNode);
  if (sRank > tRank) {
    return { ...rawLink, source: tNode.id, target: sNode.id, isLoadPath: true };
  }
  return { ...rawLink, source: sNode.id, target: tNode.id, isLoadPath: true };
}

export function computeLoadPathTrace(
  nodes: BimNode[],
  rawLinks: BimLink[],
  seedIds: string[],
  traceDirection: TraceDirection,
  traceSteps: number
): { chainNodeIds: Set<string>; chainLinkKeys: Set<string> } {
  const chainNodeIds = new Set<string>();
  const chainLinkKeys = new Set<string>();
  if (seedIds.length === 0) return { chainNodeIds, chainLinkKeys };

  const nodeMap = new Map(nodes.map((n) => [n.id, n]));
  const instanceSeeds = seedIds.filter((id) => {
    const n = nodeMap.get(id);
    return n && isInstanceNode(n);
  });
  if (instanceSeeds.length === 0) return { chainNodeIds, chainLinkKeys };

  const downstreamAdj = new Map<string, string[]>();
  const upstreamAdj = new Map<string, string[]>();

  rawLinks.forEach((l) => {
    const s = nodeMap.get(l.source);
    const t = nodeMap.get(l.target);
    if (!s || !t || !isInstanceNode(s) || !isInstanceNode(t)) return;

    const oriented = orientLoadLink(s, t, l);
    if (!downstreamAdj.has(oriented.source)) downstreamAdj.set(oriented.source, []);
    downstreamAdj.get(oriented.source)!.push(oriented.target);

    if (!upstreamAdj.has(oriented.target)) upstreamAdj.set(oriented.target, []);
    upstreamAdj.get(oriented.target)!.push(oriented.source);
  });

  const maxSteps = traceSteps >= 16 ? Infinity : Math.max(1, traceSteps);

  instanceSeeds.forEach((startNodeId) => {
    chainNodeIds.add(startNodeId);

    if (traceDirection === 'down' || traceDirection === 'both') {
      const downQueue = [{ id: startNodeId, depth: 0 }];
      const visitedDown = new Set([startNodeId]);
      while (downQueue.length > 0) {
        const { id: curr, depth } = downQueue.shift()!;
        if (depth >= maxSteps) continue;
        (downstreamAdj.get(curr) || []).forEach((nxt) => {
          chainNodeIds.add(nxt);
          chainLinkKeys.add(`${curr}->${nxt}`);
          if (!visitedDown.has(nxt)) {
            visitedDown.add(nxt);
            downQueue.push({ id: nxt, depth: depth + 1 });
          }
        });
      }
    }

    if (traceDirection === 'up' || traceDirection === 'both') {
      const upQueue = [{ id: startNodeId, depth: 0 }];
      const visitedUp = new Set([startNodeId]);
      while (upQueue.length > 0) {
        const { id: curr, depth } = upQueue.shift()!;
        if (depth >= maxSteps) continue;
        (upstreamAdj.get(curr) || []).forEach((prev) => {
          chainNodeIds.add(prev);
          chainLinkKeys.add(`${prev}->${curr}`);
          if (!visitedUp.has(prev)) {
            visitedUp.add(prev);
            upQueue.push({ id: prev, depth: depth + 1 });
          }
        });
      }
    }
  });

  return { chainNodeIds, chainLinkKeys };
}

export function buildHierarchyLinks(nodes: BimNode[], rawLinks: BimLink[]): BimLink[] {
  const visibleNodeMap = new Map(nodes.map((n) => [n.id, n]));
  const projectNode = nodes.find(isProjectNode);
  const baseLinks: BimLink[] = [];
  const seenLinkKeys = new Set<string>();

  rawLinks.forEach((l) => {
    const s = visibleNodeMap.get(l.source);
    const t = visibleNodeMap.get(l.target);
    if (!s || !t) return;

    const isHierarchy =
      (isProjectNode(s) && isElementTypeNode(t)) ||
      (isElementTypeNode(s) && isProjectNode(t)) ||
      (isElementTypeNode(s) && isColumnStackNode(t)) ||
      (isColumnStackNode(s) && isElementTypeNode(t)) ||
      (isColumnStackNode(s) && isInstanceNode(t)) ||
      (isInstanceNode(s) && isColumnStackNode(t)) ||
      (isElementTypeNode(s) && isInstanceNode(t)) ||
      (isInstanceNode(s) && isElementTypeNode(t));

    if (isHierarchy) {
      const key = `${l.source}=>${l.target}`;
      if (!seenLinkKeys.has(key)) {
        seenLinkKeys.add(key);
        baseLinks.push({ ...l, relation: 'hierarchy', isLoadPath: false });
      }
    }
  });

  if (projectNode) {
    nodes.filter(isElementTypeNode).forEach((et) => {
      const key = `${projectNode.id}=>${et.id}`;
      if (!seenLinkKeys.has(key)) {
        seenLinkKeys.add(key);
        baseLinks.push({ source: projectNode.id, target: et.id, relation: 'hierarchy', isLoadPath: false });
      }
    });
  }

  return baseLinks;
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
      label: `${projectName} Calcs`,
      type: 'Project',
      level: 0,
      floor: 'ALL',
      floorNum: 0,
      r: 36,
      x: 0,
      y: 0,
      color: '#312e81',
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
    calcNodes: laidOutCalcNodes,
    calcLinks: rawCalcLinks,
    docToElementIds,
    elementToCalcNodeIds,
  };
}

export function computeRadialLayout(rawNodes: BimNode[]): BimNode[] {
  const centerX = 0;
  const centerY = 0;

  const nodes: BimNode[] = rawNodes.map((n, idx) => {
    const fallbackAngle = (idx / Math.max(rawNodes.length, 1)) * Math.PI * 2;
    const isProj = isProjectNode(n);
    const isCategory = isElementTypeNode(n);
    return {
      ...n,
      x: Math.cos(fallbackAngle) * 320,
      y: Math.sin(fallbackAngle) * 320,
      r: n.r || (isProj ? 36 : isCategory ? 26 : 14),
      color: n.color || '#312e81',
    };
  });

  const projectNode = nodes.find(isProjectNode);
  if (projectNode) {
    projectNode.x = centerX;
    projectNode.y = centerY;
  }

  const elementTypes = nodes.filter(isElementTypeNode);
  if (elementTypes.length === 0) return nodes;

  const typeRadius = 215;

  const sectorWeights = elementTypes.map((elType) => {
    const colStacks = nodes.filter((n) => isColumnStackNode(n) && n.parent === elType.id);
    if (colStacks.length > 0) return 1.55;
    const instCount = nodes.filter((n) => isInstanceNode(n) && n.parent === elType.id).length;
    return instCount > 40 ? 1.15 : 0.88;
  });
  const totalWeight = sectorWeights.reduce((acc, w) => acc + w, 0);

  let cursorAngle = -Math.PI / 2 - (sectorWeights[0] / totalWeight) * Math.PI;

  elementTypes.forEach((elType, i) => {
    const allocatedArc = (sectorWeights[i] / totalWeight) * Math.PI * 2;
    const angle = cursorAngle + allocatedArc * 0.5;
    cursorAngle += allocatedArc;

    elType.x = centerX + Math.cos(angle) * typeRadius;
    elType.y = centerY + Math.sin(angle) * typeRadius;

    const colStacks = nodes
      .filter((n) => isColumnStackNode(n) && n.parent === elType.id)
      .sort((a, b) => a.id.localeCompare(b.id, undefined, { numeric: true }));

    if (colStacks.length > 0) {
      const stackSector = allocatedArc * 0.86;
      const stackCols = 6;
      const segOrbitR = 40;
      const rosetteOuterR = segOrbitR + 6.5 + 14;
      const minArcPitch = rosetteOuterR * 2.15;

      colStacks.forEach((stackNode, sIdx) => {
        const row = Math.floor(sIdx / stackCols);
        const col = sIdx % stackCols;
        const countInRow = Math.min(stackCols, colStacks.length - row * stackCols);
        const sAngleStep = stackSector / Math.max(countInRow, 1);
        const sAngle = angle - stackSector / 2 + (col + 0.5) * sAngleStep;

        const minRForArc = (minArcPitch * Math.max(countInRow, 1)) / Math.max(stackSector, 0.35);
        const baseRowR = Math.max(typeRadius + 215, minRForArc);
        const sDist = baseRowR + row * (rosetteOuterR * 2.25);

        stackNode.x = centerX + Math.cos(sAngle) * sDist;
        stackNode.y = centerY + Math.sin(sAngle) * sDist;
        stackNode.r = stackNode.r || 15;

        const segs = nodes
          .filter((n) => isInstanceNode(n) && n.parent === stackNode.id)
          .sort((a, b) => (a.floorNum || 0) - (b.floorNum || 0) || a.id.localeCompare(b.id));

        const ring1Cap = Math.min(16, segs.length);
        const ring2Cap = Math.max(0, segs.length - ring1Cap);

        segs.forEach((seg, k) => {
          const isOuter = k >= ring1Cap;
          const idxInRing = isOuter ? k - ring1Cap : k;
          const totalInRing = isOuter ? ring2Cap : ring1Cap;
          const orbitR = isOuter ? 56 : segOrbitR;
          const segAngle = (idxInRing / Math.max(totalInRing, 1)) * Math.PI * 2 - Math.PI / 2;

          seg.x = stackNode.x + Math.cos(segAngle) * orbitR;
          seg.y = stackNode.y + Math.sin(segAngle) * orbitR;
          seg.r = 6.5;
        });
      });
      return;
    }

    const instances = nodes
      .filter((n) => isInstanceNode(n) && n.parent === elType.id)
      .sort((a, b) => (a.floorNum || 0) - (b.floorNum || 0) || a.id.localeCompare(b.id));

    const isHuge = instances.length > 400;
    const sectorSpread = allocatedArc * 0.82;
    const nodePadDiameter = isHuge ? 20 : instances.length > 80 ? 29 : 34;

    let placed = 0;
    let ringIdx = 0;
    while (placed < instances.length) {
      const instDist = typeRadius + 150 + ringIdx * (nodePadDiameter * 1.15);
      const arcLen = instDist * sectorSpread;
      const maxInThisRing = isHuge ? 30 : Math.max(1, Math.min(18, Math.floor(arcLen / nodePadDiameter)));
      const countInThisRing = Math.min(maxInThisRing, instances.length - placed);
      const instAngleStep = sectorSpread / Math.max(countInThisRing, 1);

      for (let posInRing = 0; posInRing < countInThisRing; posInRing++) {
        const inst = instances[placed + posInRing];
        const instAngle = angle - sectorSpread / 2 + (posInRing + 0.5) * instAngleStep;
        inst.x = centerX + Math.cos(instAngle) * instDist;
        inst.y = centerY + Math.sin(instAngle) * instDist;
        if (isHuge) inst.r = 5.5;
        else if (instances.length > 80) inst.r = 9.5;
      }

      placed += countInThisRing;
      ringIdx++;
    }
  });

  return nodes;
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
          color: '#312e81',
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
        diffChanges: [{ field: 'Presence', before: 'Present in Base DB', after: 'Removed in Compare DB' }],
        diffBefore: a,
      });
    } else if (!a && b) {
      const status: DiffStatus = 'added';
      if (isInstanceNode(b)) addedCount++;
      rawMergedNodes.push({
        ...b,
        diffStatus: status,
        diffChanges: [{ field: 'Presence', before: 'Not in Base DB', after: 'Added in Compare DB' }],
      });
    } else if (a && b) {
      if (isProjectNode(b)) {
        rawMergedNodes.push({
          ...b,
          label: `${baseGraph.projectName || 'DB A'} vs ${compareGraph.projectName || 'DB B'}`,
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
      baseName: baseGraph.projectName || 'Base DB (A)',
      compareName: compareGraph.projectName || 'Compare DB (B)',
      addedCount,
      removedCount,
      modifiedCount,
      unchangedCount,
    },
  };
}
