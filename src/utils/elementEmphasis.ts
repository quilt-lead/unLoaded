// How an element is emphasised in the model views (3D and 2D plan) - one rule set, so both views
// agree on what a selection, a load-path trace, an impact overlay, a diff or a filter lights up.
import type { BimNode, ColorMode, HighlightOverlay } from '../types/bim';
import { TONE_COLORS, getEffectiveNodeColor } from './colors';
import { elementIdsUnder } from './graphEngine';

export const UNMAPPED_ELEMENT = '#6b7280';

export interface LitSet {
  /** everything a selection lights up: the selected ids, all under a selected category / family, the load chain */
  ids: Set<string>;
  /** the selection itself */
  primary: Set<string>;
  any: boolean;
}

export function computeLitSet(
  nodes: BimNode[],
  selectedNodeId: string | null,
  selectedNodeIds: Set<string>,
  activeLoadChainNodeIds: Set<string>,
): LitSet {
  const ids = new Set<string>(activeLoadChainNodeIds);
  const sel = selectedNodeIds.size > 0 ? selectedNodeIds : selectedNodeId ? new Set([selectedNodeId]) : new Set<string>();
  sel.forEach((id) => elementIdsUnder(id, nodes).forEach((e) => ids.add(e)));
  return { ids, primary: sel, any: sel.size > 0 };
}

export interface EmphasisContext {
  colorMode: ColorMode;
  diffMode: boolean;
  overlay: HighlightOverlay | null;
  lit: LitSet;
  isFilterActive: boolean;
  matchingNodeIds: Set<string>;
}

export type EmphasisState = 'primary' | 'lit' | 'normal' | 'dim';

export interface Emphasis {
  color: string;
  /** 0..1, tuned for the 3D view's solid meshes (slabs see-through) */
  opacity: number;
  /** an outline / glow colour when the element is called out */
  glow: string | null;
  state: EmphasisState;
}

export function elementEmphasis(id: string, node: BimNode | undefined, ctx: EmphasisContext): Emphasis {
  const slab = node?.elementKind === 'slab';
  const s: Emphasis = { color: UNMAPPED_ELEMENT, opacity: 0.22, glow: null, state: 'normal' };
  if (node) {
    s.color = getEffectiveNodeColor(node, ctx.colorMode, ctx.diffMode);
    s.opacity = slab ? 0.32 : 1;
  }
  if (ctx.diffMode) {
    const st = node?.diffStatus ?? 'unchanged';
    s.opacity = st === 'unchanged' ? 0.11 : st === 'removed' ? 0.45 : slab ? 0.42 : 1;
    if (st !== 'unchanged') s.glow = s.color;
    else s.state = 'dim';
  }
  if (ctx.overlay) {
    const tone = ctx.overlay.tones.get(id);
    if (tone) {
      s.color = TONE_COLORS[tone];
      s.opacity = 1;
      s.glow = tone === 'origin' ? '#6366f1' : TONE_COLORS[tone];
      s.state = 'lit';
    } else {
      s.opacity = Math.min(s.opacity, 0.07);
      s.glow = null;
      s.state = 'dim';
    }
  } else if (ctx.lit.any) {
    if (ctx.lit.primary.has(id)) {
      s.opacity = 1;
      s.glow = s.color;
      s.state = 'primary';
    } else if (ctx.lit.ids.has(id)) {
      s.opacity = Math.max(s.opacity, slab ? 0.42 : 1);
      s.glow = s.color;
      s.state = 'lit';
    } else {
      s.opacity = Math.min(s.opacity, 0.06);
      s.glow = null;
      s.state = 'dim';
    }
  } else if (ctx.isFilterActive && !ctx.matchingNodeIds.has(id)) {
    s.opacity = Math.min(s.opacity, 0.07);
    s.glow = null;
    s.state = 'dim';
  }
  return s;
}
