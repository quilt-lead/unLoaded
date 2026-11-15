/**
 * Element-side helpers: section-size parsing, IFC type -> category, and the
 * adapter from the app's ModelInput / element graph to the matcher's records.
 * Ports of norm_profile / profile_from / cat_of in ifc_ingest.py.
 */
import { pyRe } from './pyre.ts';
import type { CalcElement, ElementCat } from './types.ts';

const PROFILE_RE = pyRe(
  String.raw`\b(?:W|HSS|WT|MC|C|L|UB|UC|PFC|SHS|RHS|CHS|IPE|HEA|HEB)\s?\d+(?:\.\d+)?X\d+(?:\.\d+)?(?:X\d+(?:\.\d+)?)?\b` +
    String.raw`|\b\d{3,4}X\d{3,4}\b`,
);

export function normProfile(s: string | null | undefined): string {
  return s ? s.toUpperCase().replaceAll(' ', '').replaceAll('×', 'X') : '';
}

/** First section designation found in the strings, normalised ("W12X26"), or "". */
export function profileFrom(...strs: Array<string | null | undefined>): string {
  for (const s of strs) {
    if (!s) continue;
    const m = PROFILE_RE.exec(String(s).toUpperCase().replaceAll('×', 'X'));
    if (m) return normProfile(m[0]);
  }
  return '';
}

/** Category from the IFC entity type (and name, for connection plates). */
export function catOf(ifcType: string, name = ''): ElementCat {
  const t = ifcType.toUpperCase();
  const n = name.toLowerCase();
  if (t.includes('BEAM')) return 'Beam';
  if (t.includes('COLUMN')) return 'Column';
  if (t.includes('SLAB') || t.includes('ROOF')) return 'Slab';
  if (t.includes('FOOTING')) return 'Footing';
  if (t.includes('PILE')) return 'Pile';
  if (t.includes('WALL')) return 'Wall';
  if (t.includes('MEMBER')) return 'Brace';
  if (t.includes('PLATE') || t.includes('FASTENER') || /connection|shear tab|fin plate|base plate/.test(n)) {
    return 'Connection';
  }
  return 'Other';
}

/** Category from an element-graph kind, for elements without a native IFC type. */
const KIND_CAT: Record<string, ElementCat> = {
  beam: 'Beam',
  column: 'Column',
  slab: 'Slab',
  footing: 'Footing',
  pile: 'Pile',
  wall: 'Wall',
  brace: 'Brace',
  connection: 'Connection',
  fastener: 'Connection',
};

/** The subset of an element-graph `ElementInput` the adapter reads. */
export interface ModelElementLike {
  id: string;
  kind: string;
  mark?: string;
  name?: string;
  profile?: string;
  levelId?: string;
  params?: Record<string, unknown>;
  source?: { nativeType?: string };
}

/**
 * ModelInput / ElementGraph nodes -> matcher records.
 * `levelNames` maps a level id to its name (the storey the calcs refer to).
 */
export function toCalcElements(
  elements: Iterable<ModelElementLike>,
  levelNames: ReadonlyMap<string, string> | Record<string, string> = {},
): CalcElement[] {
  const levelName = (id: string | undefined) =>
    id === undefined
      ? ''
      : levelNames instanceof Map
        ? (levelNames.get(id) ?? '')
        : ((levelNames as Record<string, string>)[id] ?? '');
  const out: CalcElement[] = [];
  for (const e of elements) {
    const nativeType = e.source?.nativeType;
    const objectType = typeof e.params?.['Attr.ObjectType'] === 'string' ? (e.params['Attr.ObjectType'] as string) : '';
    const cat = nativeType ? catOf(nativeType, `${e.name ?? ''} ${objectType}`) : (KIND_CAT[e.kind] ?? 'Other');
    let mark = e.mark ?? '';
    if (/^(n\.?a\.?|-|none)$/i.test(mark)) mark = '';
    const profile = normProfile(e.profile);
    out.push({
      global_id: e.id,
      cat,
      mark,
      profile: profile === 'N.A' ? '' : profile,
      storey: levelName(e.levelId),
      name: e.name ?? '',
    });
  }
  return out;
}
