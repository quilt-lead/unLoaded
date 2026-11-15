import { BimNode } from '../types/bim';
import { isProjectNode, isElementTypeNode, isColumnStackNode, isInstanceNode } from './graphEngine';

const GRAPH_NODE_PALETTE = [
  // Supplied swatches plus equal OKLab steps, reordered for contrast.
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
];

const GRAPH_ROOT_COLOR = '#D8D3D8';

const STRUCTURAL_CATEGORY_IDS = [
  'cat-slab',
  'cat-col',
  'cat-beam',
  'cat-mframe',
  'cat-brace',
  'cat-conn',
  'cat-wall',
  'cat-mat',
  'cat-pcap',
  'cat-pile',
  'cat-footing',
  'cat-stair',
  'cat-roof',
  'cat-curtain',
  'cat-window',
  'cat-door',
  'cat-railing',
  'cat-covering',
  'cat-rebar',
  'cat-tendon',
  'cat-proxy',
];

const structuralCategoryColors = Object.fromEntries(
  STRUCTURAL_CATEGORY_IDS.map((id, index) => [id, GRAPH_NODE_PALETTE[index % GRAPH_NODE_PALETTE.length]])
);

const GRAPH_CATEGORY_PALETTE: Record<string, string> = {
  ...structuralCategoryColors,
  'calc-cat-beam': GRAPH_NODE_PALETTE[2],
  'calc-cat-col': GRAPH_NODE_PALETTE[1],
  'calc-cat-conn': GRAPH_NODE_PALETTE[5],
  'calc-cat-slab': GRAPH_NODE_PALETTE[0],
  'calc-cat-wall': GRAPH_NODE_PALETTE[6],
  'calc-cat-fdn': GRAPH_NODE_PALETTE[10],
};

export const CATEGORY_PALETTE: Record<string, string> = {
  'proj-1': '#14AE5C',
  'proj-root': '#14AE5C',
  'cat-slab': '#0369a1',
  'cat-col': '#15803d',
  'cat-beam': '#b45309',
  'cat-mframe': '#6d28d9',
  'cat-brace': '#0f766e',
  'cat-conn': '#0e7490',
  'cat-wall': '#be123c',
  'cat-mat': '#9a3412',
  'cat-pcap': '#c2410c',
  'cat-pile': '#334155',
  'cat-footing': '#9a3412',
  'cat-stair': '#4338ca',
  'cat-roof': '#1d4ed8',
  'cat-curtain': '#0284c7',
  'cat-window': '#0891b2',
  'cat-door': '#7e22ce',
  'cat-railing': '#475569',
  'cat-covering': '#4f46e5',
  'cat-rebar': '#9f1239',
  'cat-tendon': '#a16207',
  'cat-proxy': '#3f3f46',
  'calc-root': '#14AE5C',
  'calc-cat-beam': '#b45309',
  'calc-cat-col': '#15803d',
  'calc-cat-conn': '#0e7490',
  'calc-cat-slab': '#0369a1',
  'calc-cat-wall': '#be123c',
  'calc-cat-fdn': '#9a3412',
};

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
  if (typeof utilization !== 'number' || !Number.isFinite(utilization)) return '#FF1493';
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


export const DIFF_PALETTE: Record<'added' | 'removed' | 'modified' | 'unchanged', string> = {
  added: '#A3D900',
  removed: '#FF5E7E',
  modified: '#FF8A00',
  unchanged: '#00AEEF',
};

function hashStringToGraphNodeColor(str: string): string {
  let hash = 2166136261;
  for (let i = 0; i < str.length; i++) {
    hash ^= str.charCodeAt(i);
    hash = Math.imul(hash, 16777619);
  }
  return GRAPH_NODE_PALETTE[Math.abs(hash) % GRAPH_NODE_PALETTE.length];
}

function getGraphBaseNodeColor(node: BimNode): string {
  if (isProjectNode(node)) return GRAPH_ROOT_COLOR;
  if (GRAPH_CATEGORY_PALETTE[node.id]) return GRAPH_CATEGORY_PALETTE[node.id];
  if (isColumnStackNode(node)) return GRAPH_CATEGORY_PALETTE['cat-col'];
  if (node.categoryParent && GRAPH_CATEGORY_PALETTE[node.categoryParent]) {
    return GRAPH_CATEGORY_PALETTE[node.categoryParent];
  }
  if (node.parent && GRAPH_CATEGORY_PALETTE[node.parent]) {
    return GRAPH_CATEGORY_PALETTE[node.parent];
  }
  if (node.ifcType) return hashStringToGraphNodeColor(node.ifcType.toUpperCase());
  if (isElementTypeNode(node)) {
    return hashStringToGraphNodeColor(node.id || node.label);
  }
  return hashStringToGraphNodeColor(node.parent || node.id || node.label);
}

export function getEffectiveNodeColor(node: BimNode | null | undefined, heatmapMode: boolean, diffMode = false): string {
  if (!node) return '#14AE5C';
  if (isProjectNode(node)) return GRAPH_ROOT_COLOR;
  if (diffMode && node.diffStatus && isInstanceNode(node)) {
    return DIFF_PALETTE[node.diffStatus];
  }
  if (heatmapMode && isInstanceNode(node)) {
    return getHeatmapColor(node.utilization);
  }
  return getGraphBaseNodeColor(node);
}

export function getGraphNodeColor(
  node: BimNode | null | undefined,
  heatmapMode: boolean,
  diffMode = false
): string {
  return getEffectiveNodeColor(node, heatmapMode, diffMode);
}
