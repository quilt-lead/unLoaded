import type { BimNode, ColorMode, DiffStatus, HighlightTone, LinkReview, MappingStatus } from '../types/bim';

/** Supplied node swatches plus equal OKLab steps, ordered to keep neighbouring categories distinct. */
export const GRAPH_NODE_PALETTE = [
  '#FF1493',
  '#A3D900',
  '#00AEEF',
  '#FF8A00',
  '#FF5E7E',
  '#FFAE42',
  '#67C8A4',
  '#D6C52E',
  '#43BCCB',
  '#86D173',
  '#FF7659',
  '#FF4489',
  '#BFD01F',
  '#ECBA39',
  '#FF9C2B',
  '#FF803E',
  '#FF6B6D',
  '#FF328E',
  '#FF5284',
  '#FFA537',
  '#FF931C',
] as const;

/** Element-graph kinds use the first six palette steps in a high-contrast order. */
export const KIND_PALETTE: Record<string, string> = {
  slab: GRAPH_NODE_PALETTE[0],
  column: GRAPH_NODE_PALETTE[1],
  beam: GRAPH_NODE_PALETTE[2],
  brace: GRAPH_NODE_PALETTE[4],
  connection: GRAPH_NODE_PALETTE[5],
  fastener: GRAPH_NODE_PALETTE[6],
  wall: GRAPH_NODE_PALETTE[7],
  footing: GRAPH_NODE_PALETTE[10],
  pile: GRAPH_NODE_PALETTE[11],
  other: GRAPH_NODE_PALETTE[12],
};

export const IFC_ENTITY_PALETTE: Record<string, string> = {
  IFCSLAB: KIND_PALETTE.slab,
  IFCCOLUMN: KIND_PALETTE.column,
  IFCBEAM: KIND_PALETTE.beam,
  IFCMEMBER: KIND_PALETTE.brace,
  IFCWALL: KIND_PALETTE.wall,
  IFCWALLSTANDARDCASE: KIND_PALETTE.wall,
  IFCCURTAINWALL: GRAPH_NODE_PALETTE[13],
  IFCFOOTING: KIND_PALETTE.footing,
  IFCPILE: KIND_PALETTE.pile,
  IFCPLATE: KIND_PALETTE.connection,
  IFCMECHANICALFASTENER: KIND_PALETTE.fastener,
  IFCDISCRETEACCESSORY: KIND_PALETTE.connection,
  IFCROOF: GRAPH_NODE_PALETTE[14],
  IFCSTAIR: GRAPH_NODE_PALETTE[15],
  IFCSTAIRFLIGHT: GRAPH_NODE_PALETTE[15],
  IFCRAMP: GRAPH_NODE_PALETTE[16],
  IFCRAMPFLIGHT: GRAPH_NODE_PALETTE[16],
  IFCRAILING: GRAPH_NODE_PALETTE[17],
  IFCWINDOW: GRAPH_NODE_PALETTE[18],
  IFCDOOR: GRAPH_NODE_PALETTE[19],
  IFCCOVERING: GRAPH_NODE_PALETTE[20],
  IFCREINFORCINGBAR: GRAPH_NODE_PALETTE[8],
  IFCREINFORCINGMESH: GRAPH_NODE_PALETTE[8],
  IFCTENDON: GRAPH_NODE_PALETTE[9],
  IFCTENDONANCHOR: GRAPH_NODE_PALETTE[9],
  IFCBUILDINGELEMENTPROXY: KIND_PALETTE.other,
  IFCSITE: GRAPH_NODE_PALETTE[3],
  IFCBUILDING: GRAPH_NODE_PALETTE[3],
  IFCBUILDINGSTOREY: GRAPH_NODE_PALETTE[3],
  IFCSPACE: GRAPH_NODE_PALETTE[3],
  IFCOPENINGELEMENT: GRAPH_NODE_PALETTE[3],
  IFCDISTRIBUTIONELEMENT: GRAPH_NODE_PALETTE[6],
  IFCFLOWSEGMENT: GRAPH_NODE_PALETTE[6],
  IFCFLOWTERMINAL: GRAPH_NODE_PALETTE[6],
};

export function hashStringToJewelColor(str: string): string {
  let h = 2166136261;
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return GRAPH_NODE_PALETTE[Math.abs(h) % GRAPH_NODE_PALETTE.length];
}

export function getHeatmapColor(utilization?: number): string {
  // Unknown is not a measurement: keep it neutral rather than implying a utilization level.
  if (typeof utilization !== 'number' || !Number.isFinite(utilization)) return NO_UTILIZATION_COLOR;
  const u = Math.max(0, Math.min(1, utilization));
  const stops = [
    { t: 0.25, r: 0, g: 174, b: 239 },
    { t: 0.55, r: 163, g: 217, b: 0 },
    { t: 0.78, r: 255, g: 174, b: 66 },
    { t: 0.93, r: 255, g: 94, b: 126 },
  ];
  if (u <= stops[0].t) return '#00AEEF';
  if (u >= stops[stops.length - 1].t) return '#FF5E7E';

  for (let i = 0; i < stops.length - 1; i++) {
    const a = stops[i];
    const b = stops[i + 1];
    if (u >= a.t && u <= b.t) {
      const f = (u - a.t) / (b.t - a.t);
      const r = Math.round(a.r + (b.r - a.r) * f);
      const g = Math.round(a.g + (b.g - a.g) * f);
      const bl = Math.round(a.b + (b.b - a.b) * f);
      return `rgb(${r}, ${g}, ${bl})`;
    }
  }
  return '#FFAE42';
}

function parseColorRgb(colorStr: string): { r: number; g: number; b: number } {
  const s = colorStr.trim();
  if (s.startsWith('#')) {
    let hex = s.slice(1);
    if (hex.length === 3) hex = hex.split('').map((c) => c + c).join('');
    const num = parseInt(hex, 16);
    if (!Number.isNaN(num)) {
      return { r: (num >> 16) & 255, g: (num >> 8) & 255, b: num & 255 };
    }
  }
  const m = s.match(/rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/i);
  if (m) {
    return { r: +m[1], g: +m[2], b: +m[3] };
  }
  return { r: 30, g: 41, b: 59 };
}

export function getContrastingTextStyle(bgColorStr: string): { fill: string; shadow: string } {
  const { r, g, b } = parseColorRgb(bgColorStr);
  const toLinear = (c: number) => {
    const v = c / 255;
    return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
  };
  const lum = 0.2126 * toLinear(r) + 0.7152 * toLinear(g) + 0.0722 * toLinear(b);
  if (lum > 0.179) {
    return { fill: '#090d16', shadow: '0 1px 0 rgba(255, 255, 255, 0.45)' };
  }
  return { fill: '#ffffff', shadow: '0 1px 2px rgba(0, 0, 0, 0.78)' };
}

/** Calc colours (the backend's palette, so a calc keeps its colour across views). */
export const CALC_PALETTE = [
  '#4e79a7', '#f28e2b', '#59a14f', '#b07aa1', '#e15759', '#76b7b2', '#edc948', '#9c755f', '#ff9da7',
  '#2b8c8c', '#8f6ed5', '#d4a017', '#3d9970', '#c2185b', '#5f7d95',
];

export const PROJECT_COLOR = '#D8D3D8';
export const NO_DATA_COLOR = '#FF1493';
export const NO_UTILIZATION_COLOR = '#71717a';

export const STATUS_COLORS: Record<MappingStatus, string> = {
  confirmed: '#059669',
  review: '#d97706',
  unmapped: '#ef4444',
};

export const STATUS_LABELS: Record<MappingStatus, string> = {
  confirmed: 'Mapped',
  review: 'Needs review',
  unmapped: 'No calc found',
};

export const REVIEW_COLORS: Record<LinkReview, string> = {
  confirmed: '#34d399',
  manual: '#818cf8',
  auto: '#fbbf24',
  rejected: '#fb7185',
};

export const REVIEW_LABELS: Record<LinkReview, string> = {
  confirmed: 'Confirmed',
  manual: 'Linked by hand',
  auto: 'Proposed',
  rejected: 'Rejected',
};

export const TONE_COLORS: Record<HighlightTone, string> = {
  origin: '#ffffff',
  removed: '#f43f5e',
  hit: '#f59e0b',
  stale: '#f59e0b',
};

export const DIFF_PALETTE: Record<DiffStatus, string> = {
  added: '#A3D900',
  removed: '#FF5E7E',
  modified: '#FF8A00',
  unchanged: '#00AEEF',
};

/** How a link was made, in words (matcher tier -> label). */
export const TIER_LABELS: Record<string, string> = {
  exact: 'Named by mark',
  range: 'In a mark range',
  loose: 'Mark, punctuation ignored',
  family: 'Mark family',
  partial: 'Partial mark',
  xref: 'Cross-reference only',
  size: 'Section size + type',
  type: 'Element type only',
  manual: 'Linked by hand',
  stated: 'Stated by the file',
};

export function getConfidenceColor(conf: number | undefined): string {
  if (typeof conf !== 'number') return NO_DATA_COLOR;
  if (conf >= 0.8) return '#059669';
  if (conf >= 0.5) return '#d97706';
  return '#e11d48';
}

/** Stroke colour + dash of a calc-mapping edge, styled by its review state. */
export function linkStrokeStyle(review: LinkReview | undefined, confidence = 0): { stroke: string; dash?: string; width: number } {
  switch (review) {
    case 'confirmed':
      return { stroke: REVIEW_COLORS.confirmed, width: 1.6 };
    case 'manual':
      return { stroke: REVIEW_COLORS.manual, width: 1.6 };
    case 'rejected':
      return { stroke: REVIEW_COLORS.rejected, dash: '1.5 3', width: 1.1 };
    default:
      return { stroke: confidence >= 0.8 ? '#a3e635' : REVIEW_COLORS.auto, dash: confidence >= 0.8 ? undefined : '4 3', width: 1.2 };
  }
}

/** Colour of an element / family / category by kind, else by IFC type. */
export function typeColor(node: BimNode): string {
  if (node.elementKind && KIND_PALETTE[node.elementKind]) return KIND_PALETTE[node.elementKind];
  if (node.elementKind) return hashStringToJewelColor(node.elementKind);
  return ifcTypeColor(node.ifcType, node.parent || node.id);
}

function calcCategoryColor(node: BimNode): string {
  const label = `${node.id} ${node.label}`.toLowerCase();
  if (/beam|girder/.test(label)) return KIND_PALETTE.beam;
  if (/column/.test(label)) return KIND_PALETTE.column;
  if (/connection|fastener/.test(label)) return KIND_PALETTE.connection;
  if (/slab|punch/.test(label)) return KIND_PALETTE.slab;
  if (/wall|lateral/.test(label)) return KIND_PALETTE.wall;
  if (/foundation|footing|geotech|pile/.test(label)) return KIND_PALETTE.footing;
  return hashStringToJewelColor(node.id);
}

export function ifcTypeColor(ifcType: string | undefined, fallbackKey: string): string {
  const key = (ifcType || '').toUpperCase().replace(/[^A-Z0-9]/g, '');
  return IFC_ENTITY_PALETTE[key] ?? hashStringToJewelColor(fallbackKey);
}

/** Strongest live DESIGN link of an element (rejected and loads-only links ignored, as the mapping status does). */
export function topLiveConfidence(node: BimNode): number | undefined {
  const live = (node.calcLinks ?? []).filter((l) => l.review !== 'rejected' && l.role === 'design');
  if (!live.length) return undefined;
  return Math.max(...live.map((l) => (l.review === 'confirmed' || l.review === 'manual' ? 1 : l.confidence)));
}

export function getEffectiveNodeColor(node: BimNode | null | undefined, colorMode: ColorMode = 'type', diffMode = false): string {
  if (!node) return NO_DATA_COLOR;
  if (diffMode && node.kind === 'element') return DIFF_PALETTE[node.diffStatus ?? 'unchanged'];
  switch (node.kind) {
    case 'project':
    case 'calc-root':
      return PROJECT_COLOR;
    case 'calc':
      return node.color ?? hashStringToJewelColor(node.id);
    case 'calc-category':
      return calcCategoryColor(node);
    case 'mapped-element': {
      const l = node.link;
      if (!l) return NO_DATA_COLOR;
      if (l.review === 'rejected') return '#9f1239';
      if (l.review === 'confirmed' || l.review === 'manual') return '#059669';
      return getConfidenceColor(l.confidence);
    }
    case 'category':
    case 'family':
      return typeColor(node);
    case 'element':
    default:
      if (colorMode === 'review') return STATUS_COLORS[node.mappingStatus ?? 'unmapped'];
      if (colorMode === 'confidence') return getConfidenceColor(topLiveConfidence(node));
      if (colorMode === 'utilisation') return getHeatmapColor(node.utilization);
      return typeColor(node);
  }
}
