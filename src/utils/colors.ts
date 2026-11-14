import type { BimNode, ColorMode, DiffStatus, HighlightTone, LinkReview, MappingStatus } from '../types/bim';

export const IFC_ENTITY_PALETTE: Record<string, string> = {
  IFCSLAB: '#0369a1',
  IFCCOLUMN: '#15803d',
  IFCBEAM: '#b45309',
  IFCMEMBER: '#0f766e',
  IFCWALL: '#be123c',
  IFCWALLSTANDARDCASE: '#be123c',
  IFCCURTAINWALL: '#0284c7',
  IFCFOOTING: '#9a3412',
  IFCPILE: '#334155',
  IFCPLATE: '#0e7490',
  IFCMECHANICALFASTENER: '#0e7490',
  IFCDISCRETEACCESSORY: '#0e7490',
  IFCROOF: '#1d4ed8',
  IFCSTAIR: '#4338ca',
  IFCSTAIRFLIGHT: '#4338ca',
  IFCRAMP: '#4338ca',
  IFCRAMPFLIGHT: '#4338ca',
  IFCRAILING: '#475569',
  IFCWINDOW: '#0891b2',
  IFCDOOR: '#7e22ce',
  IFCCOVERING: '#4f46e5',
  IFCREINFORCINGBAR: '#9f1239',
  IFCREINFORCINGMESH: '#9f1239',
  IFCTENDON: '#a16207',
  IFCTENDONANCHOR: '#a16207',
  IFCBUILDINGELEMENTPROXY: '#3f3f46',
  IFCSITE: '#1e3a8a',
  IFCBUILDING: '#312e81',
  IFCBUILDINGSTOREY: '#3730a3',
  IFCSPACE: '#5b21b6',
  IFCOPENINGELEMENT: '#52525b',
  IFCDISTRIBUTIONELEMENT: '#115e59',
  IFCFLOWSEGMENT: '#115e59',
  IFCFLOWTERMINAL: '#115e59',
};

export function hashStringToJewelColor(str: string): string {
  const jewelSwatches = [
    '#0369a1', '#15803d', '#b45309', '#be123c', '#6d28d9',
    '#0f766e', '#1d4ed8', '#9a3412', '#4338ca', '#0e7490',
    '#7e22ce', '#9f1239', '#334155', '#1e40af', '#065f46',
  ];
  let h = 2166136261;
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return jewelSwatches[Math.abs(h) % jewelSwatches.length];
}

export function getHeatmapColor(utilization?: number): string {
  const u = Math.max(0, Math.min(1, typeof utilization === 'number' ? utilization : 0.5));
  const stops = [
    { t: 0.25, r: 6, g: 182, b: 212 },
    { t: 0.55, r: 16, g: 185, b: 129 },
    { t: 0.78, r: 245, g: 158, b: 11 },
    { t: 0.93, r: 239, g: 68, b: 68 },
  ];
  if (u <= stops[0].t) return '#06b6d4';
  if (u >= stops[stops.length - 1].t) return '#ef4444';

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
  return '#f59e0b';
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
  if (lum > 0.36) {
    return { fill: '#090d16', shadow: '0 1px 0 rgba(255, 255, 255, 0.45)' };
  }
  return { fill: '#ffffff', shadow: '0 1px 2px rgba(0, 0, 0, 0.78)' };
}

/** Calc colours (the backend's palette, so a calc keeps its colour across views). */
export const CALC_PALETTE = [
  '#4e79a7', '#f28e2b', '#59a14f', '#b07aa1', '#e15759', '#76b7b2', '#edc948', '#9c755f', '#ff9da7',
  '#2b8c8c', '#8f6ed5', '#d4a017', '#3d9970', '#c2185b', '#5f7d95',
];

export const PROJECT_COLOR = '#312e81';
export const NO_DATA_COLOR = '#52525b';

export const STATUS_COLORS: Record<MappingStatus, string> = {
  confirmed: '#059669',
  review: '#d97706',
  unmapped: '#e11d48',
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
  added: '#10b981', // emerald: in B, not in A
  removed: '#ef4444', // crimson: in A, not in B
  modified: '#f59e0b', // amber: same GlobalId, different content
  unchanged: '#475569', // muted slate
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
};

/** Tailwind classes for a confidence chip. */
export function confidenceTone(conf: number): 'good' | 'warn' | 'bad' {
  return conf >= 0.8 ? 'good' : conf >= 0.5 ? 'warn' : 'bad';
}

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

/** element-graph kind -> colour (prod's category palette) */
export const KIND_PALETTE: Record<string, string> = {
  slab: '#0369a1',
  beam: '#b45309',
  brace: '#0f766e',
  connection: '#0e7490',
  fastener: '#155e75',
  column: '#15803d',
  wall: '#be123c',
  footing: '#9a3412',
  pile: '#334155',
  other: '#3f3f46',
};

/** Colour of an element / family / category by kind, else by IFC type. */
export function typeColor(node: BimNode): string {
  if (node.elementKind && KIND_PALETTE[node.elementKind]) return KIND_PALETTE[node.elementKind];
  if (node.elementKind) return hashStringToJewelColor(node.elementKind);
  return ifcTypeColor(node.ifcType, node.parent || node.id);
}

export function ifcTypeColor(ifcType: string | undefined, fallbackKey: string): string {
  const key = (ifcType || '').toUpperCase().replace(/[^A-Z0-9]/g, '');
  return IFC_ENTITY_PALETTE[key] ?? hashStringToJewelColor(fallbackKey);
}

/** Strongest live link of an element (rejected links ignored). */
export function topLiveConfidence(node: BimNode): number | undefined {
  const live = (node.calcLinks ?? []).filter((l) => l.review !== 'rejected');
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
      return hashStringToJewelColor(node.id);
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
      if (colorMode === 'review') return node.mappingStatus ? STATUS_COLORS[node.mappingStatus] : NO_DATA_COLOR;
      if (colorMode === 'confidence') return getConfidenceColor(topLiveConfidence(node));
      if (colorMode === 'utilisation') return typeof node.utilization === 'number' ? getHeatmapColor(node.utilization) : NO_DATA_COLOR;
      return typeColor(node);
  }
}
