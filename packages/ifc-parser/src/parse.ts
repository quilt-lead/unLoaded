/**
 * IFC (STEP) -> ModelInput. See README.md for conventions.
 */
import {
  IfcAPI,
  IFCBUILDINGSTOREY,
  IFCPROJECT,
  IFCRELAGGREGATES,
  IFCRELASSIGNSTOPRODUCT,
  IFCRELASSOCIATESMATERIAL,
  IFCRELCONNECTSELEMENTS,
  IFCRELCONNECTSPATHELEMENTS,
  IFCRELCONNECTSSTRUCTURALMEMBER,
  IFCRELCONNECTSWITHREALIZINGELEMENTS,
  IFCRELCONTAINEDINSPATIALSTRUCTURE,
  IFCRELDEFINESBYPROPERTIES,
  IFCRELDEFINESBYTYPE,
} from "web-ifc";
import {
  MODEL_INPUT_VERSION,
  type ElementInput,
  type ElementKind,
  type LevelInput,
  type ModelInput,
  type ParamValue,
  type RelationInput,
} from "@unloaded/element-graph/input";
import { createKindResolver, IGNORED_TYPES, LINEAR_KINDS, type KindMap } from "./kind-map.ts";
import { IfcReader, isPlaceholder, num, ref, refs, str } from "./reader.ts";
import { readUnits } from "./units.ts";
import { flattenPropertyDefinition } from "./properties.ts";
import { findSweptProfile, normaliseProfile, profileFromText, readProfileDef, type ProfileInfo } from "./profile.ts";
import { readMaterial } from "./materials.ts";
import { axis2Placement, IDENTITY, mul, PointAccumulator, round6, summarise, type Mat4 } from "./geometry.ts";

export type IfcParsePhase = "init" | "open" | "index" | "elements" | "geometry" | "relations" | "done";

export interface IfcParseOptions {
  /** Original file name, recorded in meta.source.file. */
  fileName?: string;
  /**
   * Directory (URL or path, trailing slash optional) containing `web-ifc.wasm`.
   * Required in the browser (e.g. "/wasm/" with the file copied into Vite's
   * public dir). In Node it may be omitted: web-ifc resolves its own wasm.
   */
  wasmPath?: string;
  /** Compute geometry summaries (bbox / axis / section). Default true. */
  geometry?: boolean;
  /** Only emit elements of these kinds (after kind resolution). */
  includeKinds?: ElementKind[];
  /**
   * Kind overrides keyed by IFC entity name ("IfcMember") or entity + predefined
   * type ("IfcMember.STUD"). Keys for entities not in the default table make
   * those entities extracted too (e.g. { IfcChimney: "other" }).
   */
  kindMap?: KindMap;
  /** Progress callback; fraction in [0, 1] within the phase. */
  onProgress?(phase: IfcParsePhase, fraction: number): void;
}

// ---------------------------------------------------------------------------
// web-ifc runtime (one initialised IfcAPI per wasm location)

const apis = new Map<string, Promise<IfcAPI>>();

function getApi(wasmPath: string | undefined): Promise<IfcAPI> {
  const key = wasmPath ?? "";
  let p = apis.get(key);
  if (!p) {
    p = (async () => {
      const api = new IfcAPI();
      if (wasmPath) api.SetWasmPath(wasmPath.endsWith("/") || wasmPath.endsWith("\\") ? wasmPath : `${wasmPath}/`, true);
      await api.Init(undefined, true);
      return api;
    })();
    p.catch(() => apis.delete(key));
    apis.set(key, p);
  }
  return p;
}

/** True if the bytes start (after BOM / whitespace) with the STEP magic. */
export function hasStepHeader(head: Uint8Array): boolean {
  let s = "";
  for (let i = 0; i < Math.min(head.length, 64); i++) s += String.fromCharCode(head[i]!);
  return s.replace(/^﻿|^ï»¿/, "").trimStart().startsWith("ISO-10303-21");
}

// ---------------------------------------------------------------------------

const MARK_PROPS = ["mark", "piece mark", "piecemark", "reference mark", "reference", "type mark"];
const LEVEL_WALK_LIMIT = 16;

function pushMulti<K, V>(m: Map<K, V[]>, k: K, v: V) {
  const a = m.get(k);
  if (a) a.push(v);
  else m.set(k, [v]);
}

function propName(key: string): string {
  const i = key.indexOf(".");
  return (i >= 0 ? key.slice(i + 1) : key).toLowerCase();
}

function findMark(sets: Array<Record<string, ParamValue>>): string | undefined {
  for (const wanted of MARK_PROPS) {
    for (const params of sets) {
      for (const [k, v] of Object.entries(params)) {
        if (propName(k) !== wanted) continue;
        if (v === null || typeof v === "boolean") continue;
        const s = String(v).trim();
        if (!isPlaceholder(s)) return s;
      }
    }
  }
  return undefined;
}

/** A Tag is only used as a mark if it doesn't look like an authoring-tool id. */
function tagAsMark(tag: string | undefined): string | undefined {
  if (!tag || isPlaceholder(tag)) return undefined;
  const t = tag.trim();
  if (/^[\d.\-]{6,}$/.test(t)) return undefined; // e.g. Revit/SketchUp element ids
  if (/^[0-9a-f]{8}-[0-9a-f]{4}-/i.test(t)) return undefined; // GUIDs
  return t;
}

interface RawRel {
  a: number;
  b: number;
  kind: string;
  rule: string;
  relId: number;
  relGuid?: string;
  extra?: Record<string, ParamValue>;
}

export async function parseIfc(data: Uint8Array, opts: IfcParseOptions = {}): Promise<ModelInput> {
  const progress = (phase: IfcParsePhase, f: number) => {
    try {
      opts.onProgress?.(phase, f);
    } catch {
      /* never let a UI callback break parsing */
    }
  };
  progress("init", 0);
  if (!hasStepHeader(data.subarray(0, 64))) {
    throw new Error("Not an IFC STEP file (missing ISO-10303-21 header)");
  }
  const api = await getApi(opts.wasmPath);
  progress("init", 1);
  progress("open", 0);
  const modelID = api.OpenModel(data, { COORDINATE_TO_ORIGIN: false });
  if (modelID < 0) throw new Error("web-ifc could not open the model (unsupported schema?)");
  try {
    progress("open", 1);
    const result = extract(api, modelID, opts, progress);
    progress("done", 1);
    return result;
  } finally {
    try {
      api.CloseModel(modelID);
    } catch {
      /* ignore */
    }
  }
}

function extract(
  api: IfcAPI,
  modelID: number,
  opts: IfcParseOptions,
  progress: (phase: IfcParsePhase, f: number) => void,
): ModelInput {
  const warnings: string[] = [];
  const r = new IfcReader(api, modelID);
  const units = readUnits(r, warnings);
  const schema = String(api.GetModelSchema(modelID) ?? "") || undefined;

  // ---- index relationship entities once (O(n)) ----------------------------
  progress("index", 0);
  const psetsOf = new Map<number, number[]>();
  for (const id of r.ids(IFCRELDEFINESBYPROPERTIES)) {
    const rel = r.line(id);
    const defs = refs(rel?.RelatingPropertyDefinition);
    for (const o of refs(rel?.RelatedObjects)) for (const d of defs) pushMulti(psetsOf, o, d);
  }
  const typeOf = new Map<number, number>();
  for (const id of r.ids(IFCRELDEFINESBYTYPE)) {
    const rel = r.line(id);
    const t = ref(rel?.RelatingType);
    if (t !== undefined) for (const o of refs(rel?.RelatedObjects)) typeOf.set(o, t);
  }
  const materialOf = new Map<number, number>();
  for (const id of r.ids(IFCRELASSOCIATESMATERIAL)) {
    const rel = r.line(id);
    const m = ref(rel?.RelatingMaterial);
    if (m !== undefined) for (const o of refs(rel?.RelatedObjects)) if (!materialOf.has(o)) materialOf.set(o, m);
  }
  const containerOf = new Map<number, number>();
  for (const id of r.ids(IFCRELCONTAINEDINSPATIALSTRUCTURE)) {
    const rel = r.line(id);
    const s = ref(rel?.RelatingStructure);
    if (s !== undefined) for (const o of refs(rel?.RelatedElements)) if (!containerOf.has(o)) containerOf.set(o, s);
  }
  const parentOf = new Map<number, number>();
  const aggregates: Array<{ relId: number; parent: number; children: number[]; guid?: string }> = [];
  for (const id of r.ids(IFCRELAGGREGATES)) {
    const rel = r.line(id);
    const p = ref(rel?.RelatingObject);
    const children = refs(rel?.RelatedObjects);
    if (p === undefined) continue;
    for (const c of children) if (!parentOf.has(c)) parentOf.set(c, p);
    aggregates.push({ relId: id, parent: p, children, guid: str(rel?.GlobalId) });
  }
  progress("index", 1);

  // ---- levels ---------------------------------------------------------------
  const placementCache = new Map<number, Mat4>();
  const placement = (id: number | undefined, depth = 0): Mat4 => {
    if (id === undefined || depth > 64) return IDENTITY;
    const hit = placementCache.get(id);
    if (hit) return hit;
    const lp = r.line(id);
    let m = IDENTITY;
    if (lp && r.nameOfCode(lp.type) === "IfcLocalPlacement") {
      const parent = placement(ref(lp.PlacementRelTo), depth + 1);
      const a = r.line(ref(lp.RelativePlacement));
      if (a && r.nameOfCode(a.type) === "IfcAxis2Placement3D") {
        const coords = (pid: unknown, key: string) => {
          const l = r.line(ref(pid));
          const arr = l?.[key];
          return Array.isArray(arr) ? arr.map((v) => num(v) ?? 0) : undefined;
        };
        const loc = coords(a.Location, "Coordinates") ?? [0, 0, 0];
        m = mul(parent, axis2Placement(loc, coords(a.Axis, "DirectionRatios"), coords(a.RefDirection, "DirectionRatios")));
      } else m = parent;
    }
    placementCache.set(id, m);
    return m;
  };

  const levels: LevelInput[] = [];
  const levelIdByExpress = new Map<number, string>();
  for (const id of r.ids(IFCBUILDINGSTOREY)) {
    const s = r.line(id);
    if (!s) continue;
    const gid = str(s.GlobalId);
    if (!gid) {
      warnings.push(`IfcBuildingStorey #${id} has no GlobalId; skipped`);
      continue;
    }
    const attrElev = num(s.Elevation);
    let elevation: number | undefined;
    if (ref(s.ObjectPlacement) !== undefined) elevation = placement(ref(s.ObjectPlacement))[14]! * units.length;
    if (elevation === undefined && attrElev !== undefined) elevation = attrElev * units.length;
    if (elevation === undefined) {
      elevation = 0;
      warnings.push(`IfcBuildingStorey ${gid} has neither placement nor Elevation; using 0`);
    } else if (attrElev !== undefined && Math.abs(attrElev * units.length - elevation) > 0.001) {
      warnings.push(
        `IfcBuildingStorey ${gid}: Elevation attribute ${round6(attrElev * units.length)} m differs from placement z ${round6(elevation)} m; using placement`,
      );
    }
    levelIdByExpress.set(id, gid);
    levels.push({ id: gid, name: str(s.Name) ?? str(s.LongName) ?? gid, elevation: round6(elevation) });
  }
  levels.sort((a, b) => a.elevation - b.elevation || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0));

  const levelFor = (id: number): string | undefined => {
    let cur: number | undefined = id;
    for (let i = 0; i < LEVEL_WALK_LIMIT && cur !== undefined; i++) {
      const lvl = levelIdByExpress.get(cur);
      if (lvl) return lvl;
      cur = containerOf.get(cur) ?? parentOf.get(cur);
    }
    return undefined;
  };

  // ---- explicit relations (express ids; filtered to emitted elements later) --
  const rawRels: RawRel[] = [];
  const realizing = new Set<number>();
  const relGuid = (l: Record<string, unknown> | undefined) => str(l?.GlobalId);
  for (const [code, rule] of [
    [IFCRELCONNECTSELEMENTS, "IfcRelConnectsElements"],
    [IFCRELCONNECTSPATHELEMENTS, "IfcRelConnectsPathElements"],
  ] as const) {
    for (const id of r.ids(code)) {
      const rel = r.line(id);
      const a = ref(rel?.RelatingElement);
      const b = ref(rel?.RelatedElement);
      if (a === undefined || b === undefined) continue;
      const extra: Record<string, ParamValue> = {};
      if (rule === "IfcRelConnectsPathElements") {
        const ra = str(rel?.RelatingConnectionType);
        const rb = str(rel?.RelatedConnectionType);
        if (ra) extra.relatingConnectionType = ra;
        if (rb) extra.relatedConnectionType = rb;
      }
      rawRels.push({ a, b, kind: "connects", rule, relId: id, relGuid: relGuid(rel), extra });
    }
  }
  for (const id of r.ids(IFCRELCONNECTSWITHREALIZINGELEMENTS)) {
    const rel = r.line(id);
    const ends = [ref(rel?.RelatingElement), ref(rel?.RelatedElement)].filter((x): x is number => x !== undefined);
    const ctype = str(rel?.ConnectionType);
    for (const re of refs(rel?.RealizingElements)) {
      realizing.add(re);
      for (const e of ends) {
        rawRels.push({
          a: e,
          b: re,
          kind: "connects",
          rule: "IfcRelConnectsWithRealizingElements",
          relId: id,
          relGuid: relGuid(rel),
          extra: ctype ? { connectionType: ctype } : {},
        });
      }
    }
  }
  for (const agg of aggregates) {
    for (const c of agg.children) {
      rawRels.push({ a: c, b: agg.parent, kind: "part_of", rule: "IfcRelAggregates", relId: agg.relId, relGuid: agg.guid });
    }
  }
  // Structural analysis model: members joined at a structural connection.
  const structRels = r.ids(IFCRELCONNECTSSTRUCTURALMEMBER);
  if (structRels.length > 0) {
    const productOf = new Map<number, number>();
    for (const id of r.ids(IFCRELASSIGNSTOPRODUCT)) {
      const rel = r.line(id);
      const p = ref(rel?.RelatingProduct);
      if (p !== undefined) for (const o of refs(rel?.RelatedObjects)) if (!productOf.has(o)) productOf.set(o, p);
    }
    const membersAt = new Map<number, Array<{ member: number; relId: number }>>();
    for (const id of structRels) {
      const rel = r.line(id);
      const m = ref(rel?.RelatingStructuralMember);
      const c = ref(rel?.RelatedStructuralConnection);
      if (m !== undefined && c !== undefined) pushMulti(membersAt, c, { member: m, relId: id });
    }
    let unmapped = 0;
    for (const [conn, members] of [...membersAt.entries()].sort((x, y) => x[0] - y[0])) {
      const physConn = productOf.get(conn);
      const phys = members.map((m) => ({ p: productOf.get(m.member), relId: m.relId }));
      unmapped += phys.filter((x) => x.p === undefined).length;
      const mapped = phys.filter((x): x is { p: number; relId: number } => x.p !== undefined);
      const extra = { structuralConnectionId: conn };
      if (physConn !== undefined) {
        for (const m of mapped)
          rawRels.push({ a: m.p, b: physConn, kind: "connects", rule: "IfcRelConnectsStructuralMember", relId: m.relId, extra });
      } else {
        for (let i = 0; i < mapped.length; i++)
          for (let j = i + 1; j < mapped.length; j++)
            rawRels.push({ a: mapped[i]!.p, b: mapped[j]!.p, kind: "connects", rule: "IfcRelConnectsStructuralMember", relId: mapped[i]!.relId, extra });
      }
    }
    if (unmapped > 0)
      warnings.push(
        `structural analysis: ${unmapped} IfcRelConnectsStructuralMember member(s) have no IfcRelAssignsToProduct link to a physical element; skipped`,
      );
  }

  // ---- elements -------------------------------------------------------------
  progress("elements", 0);
  const kinds = createKindResolver(opts.kindMap);
  const include = opts.includeKinds ? new Set<string>(opts.includeKinds) : undefined;
  const candidates: Array<{ id: number; ifcType: string }> = [];
  const skipped = new Map<string, number>();
  for (const t of api.GetAllTypesOfModel(modelID)) {
    if (!api.IsIfcElement(t.typeID)) continue;
    const name = r.nameOfCode(t.typeID) || t.typeName;
    if (kinds.handles(name)) {
      for (const id of r.ids(t.typeID)) candidates.push({ id, ifcType: name });
    } else if (!IGNORED_TYPES.has(name.toLowerCase())) {
      skipped.set(name, (skipped.get(name) ?? 0) + r.ids(t.typeID).length);
    }
  }
  candidates.sort((a, b) => a.id - b.id);

  const elements: ElementInput[] = [];
  const byExpress = new Map<number, ElementInput>();
  const profileDims = new Map<number, ProfileInfo>();
  const seenIds = new Set<string>();
  let missingGuid = 0;
  let duplicateGuid = 0;
  let excludedByKind = 0;
  const profileCache = new Map<number, ProfileInfo | undefined>();
  const profileDef = (id: number | undefined) => {
    if (id === undefined) return undefined;
    if (!profileCache.has(id)) profileCache.set(id, readProfileDef(r, id, units.length));
    return profileCache.get(id);
  };
  const psetCache = new Map<number, Record<string, ParamValue>>();
  const flattenDefs = (ids: number[]) => {
    const out: Record<string, ParamValue> = {};
    for (const d of [...ids].sort((a, b) => a - b)) {
      let flat = psetCache.get(d);
      if (!flat) {
        flat = {};
        flattenPropertyDefinition(r, d, flat, units);
        psetCache.set(d, flat);
      }
      Object.assign(out, flat);
    }
    return out;
  };

  for (let i = 0; i < candidates.length; i++) {
    if (i % 200 === 0) progress("elements", i / Math.max(1, candidates.length));
    const { id, ifcType } = candidates[i]!;
    const e = r.line(id);
    if (!e) continue;
    let gid = str(e.GlobalId);
    if (!gid) {
      missingGuid++;
      gid = `ifc-express-${id}`;
    }
    if (seenIds.has(gid)) {
      duplicateGuid++;
      continue;
    }

    const typeId = typeOf.get(id);
    const typeObj = r.line(typeId);
    const name = str(e.Name);
    const objectType = str(e.ObjectType);
    const tag = str(e.Tag);
    const typeName = str(typeObj?.Name);
    const instPre = str(e.PredefinedType);
    const typePre = str(typeObj?.PredefinedType);
    const predefined =
      instPre && instPre !== "NOTDEFINED" && !(instPre === "USERDEFINED" && typePre && typePre !== "NOTDEFINED" && typePre !== "USERDEFINED")
        ? instPre
        : typePre && typePre !== "NOTDEFINED"
          ? typePre
          : instPre;

    let { kind, overridden } = kinds.resolve({ ifcType, predefinedType: predefined, names: [name, objectType, typeName] });
    if (realizing.has(id) && !overridden && kind !== "fastener") kind = "connection";
    if (include && !include.has(kind)) {
      excludedByKind++;
      continue;
    }

    // params: type first, instance overrides
    const typeParams = typeObj ? flattenDefs(refs(typeObj.HasPropertySets)) : {};
    const instParams = flattenDefs(psetsOf.get(id) ?? []);
    const params: Record<string, ParamValue> = {};
    if (name !== undefined) params["Attr.Name"] = name;
    if (objectType !== undefined) params["Attr.ObjectType"] = objectType;
    if (tag !== undefined) params["Attr.Tag"] = tag;
    if (predefined !== undefined) params["Attr.PredefinedType"] = predefined;
    if (typeName !== undefined) params["Attr.TypeName"] = typeName;
    Object.assign(params, typeParams, instParams);

    // material + profile
    const mat = readMaterial(r, materialOf.get(id) ?? (typeId !== undefined ? materialOf.get(typeId) : undefined));
    const matProfile = profileDef(mat.profileDefId);
    const sweptId = findSweptProfile(r, ref(e.Representation));
    const swept = profileDef(sweptId);
    const named = matProfile?.name ?? swept?.name;
    let profile: string | undefined;
    if (named && !isPlaceholder(named)) profile = normaliseProfile(named);
    profile ??= profileFromText([name, objectType, typeName, mat.profileSetName]);
    profile ??= matProfile?.synthesized ?? swept?.synthesized;
    const dims = matProfile?.depth !== undefined ? matProfile : swept;
    if (dims?.depth !== undefined || dims?.width !== undefined) profileDims.set(id, dims!);

    const el: ElementInput = {
      id: gid,
      kind,
      params,
      source: { format: "ifc", nativeId: id, nativeType: ifcType },
    };
    const mark = findMark([instParams, typeParams]) ?? tagAsMark(tag);
    if (mark) el.mark = mark;
    if (name) el.name = name;
    if (profile) el.profile = profile;
    if (mat.name) el.material = mat.name;
    const lvl = levelFor(id);
    if (lvl) el.levelId = lvl;

    seenIds.add(gid);
    elements.push(el);
    byExpress.set(id, el);
  }
  progress("elements", 1);
  if (missingGuid) warnings.push(`${missingGuid} element(s) without GlobalId; used unstable fallback ids "ifc-express-<expressID>"`);
  if (duplicateGuid) warnings.push(`${duplicateGuid} element(s) with duplicate GlobalId; kept the first occurrence`);
  if (excludedByKind) warnings.push(`${excludedByKind} element(s) excluded by includeKinds`);
  for (const [t, n] of [...skipped.entries()].sort()) {
    if (n > 0) warnings.push(`unsupported element type ${t}: ${n} instance(s) skipped (add it to kindMap to include)`);
  }

  // ---- geometry ---------------------------------------------------------------
  if (opts.geometry !== false && byExpress.size > 0) {
    progress("geometry", 0);
    const ids = [...byExpress.keys()];
    const accs = new Map<number, PointAccumulator>();
    let failed = 0;
    let done = 0;
    try {
      api.StreamMeshes(modelID, ids, (mesh) => {
        done++;
        if (done % 100 === 0) progress("geometry", done / ids.length);
        try {
          const acc = accs.get(mesh.expressID) ?? new PointAccumulator();
          const n = mesh.geometries.size();
          for (let g = 0; g < n; g++) {
            const pg = mesh.geometries.get(g);
            const geom = api.GetGeometry(modelID, pg.geometryExpressID);
            try {
              const verts = api.GetVertexArray(geom.GetVertexData(), geom.GetVertexDataSize());
              acc.addWebIfcVertices(verts, pg.flatTransformation);
            } finally {
              geom.delete();
            }
          }
          accs.set(mesh.expressID, acc);
        } catch {
          failed++;
        }
      });
    } catch (err) {
      warnings.push(`geometry: web-ifc mesh streaming failed (${err instanceof Error ? err.message : String(err)}); partial geometry`);
    }
    if (failed) warnings.push(`geometry: ${failed} element mesh(es) could not be read`);

    const noGeom: Record<string, number> = {};
    let decomposed = 0;
    const hasChildren = new Set(aggregates.filter((a) => a.children.length).map((a) => a.parent));
    for (const [id, el] of byExpress) {
      const acc = accs.get(id);
      const linear = LINEAR_KINDS.has(el.kind);
      const s = acc ? summarise(acc, linear, el.kind === "column") : undefined;
      if (!s) {
        const t = el.source.nativeType ?? "?";
        noGeom[t] = (noGeom[t] ?? 0) + 1;
        if (hasChildren.has(id)) decomposed++;
        continue;
      }
      const g = s.geometry;
      const dims = profileDims.get(id);
      if (dims) {
        g.section = {};
        if (dims.depth !== undefined) g.section.depth = round6(dims.depth);
        if (dims.width !== undefined) g.section.width = round6(dims.width);
      } else if (s.axis) {
        g.section =
          el.kind === "column"
            ? { depth: Math.max(s.axis.crossVertical, s.axis.crossHorizontal), width: Math.min(s.axis.crossVertical, s.axis.crossHorizontal) }
            : { depth: s.axis.crossVertical, width: s.axis.crossHorizontal };
      }
      if (s.axis) {
        el.params["Geom.Length"] = s.axis.length;
        el.params["Geom.InclinationDeg"] = s.axis.inclinationDeg;
      }
      el.geometry = g;
    }
    const total = Object.values(noGeom).reduce((a, b) => a + b, 0);
    if (total > 0) {
      const detail = Object.entries(noGeom)
        .sort()
        .map(([t, n]) => `${t}: ${n}`)
        .join(", ");
      warnings.push(
        `geometry: ${total} element(s) without own body geometry (${detail})` +
          (decomposed ? `; ${decomposed} of them are decomposed into parts (IfcRelAggregates)` : ""),
      );
    }
    progress("geometry", 1);
  }

  // ---- relations --------------------------------------------------------------
  progress("relations", 0);
  const relations: RelationInput[] = [];
  const seenRel = new Set<string>();
  let droppedRel = 0;
  rawRels.sort((x, y) => x.relId - y.relId || x.a - y.a || x.b - y.b);
  for (const raw of rawRels) {
    const ea = byExpress.get(raw.a);
    const eb = byExpress.get(raw.b);
    if (!ea || !eb) {
      droppedRel++;
      continue;
    }
    if (ea.id === eb.id) continue;
    let a = ea.id;
    let b = eb.id;
    if (raw.kind === "connects" && b < a) [a, b] = [b, a];
    const key = `${raw.kind}|${a}|${b}|${raw.rule}`;
    if (seenRel.has(key)) continue;
    seenRel.add(key);
    const detail: Record<string, ParamValue> = { ifcRelId: raw.relId, ...(raw.extra ?? {}) };
    if (raw.relGuid) detail.ifcRelGlobalId = raw.relGuid;
    relations.push({ a, b, kind: raw.kind, evidence: { rule: raw.rule, source: "explicit", detail } });
  }
  // Relations with neither end emitted (e.g. spatial aggregation) are expected; only
  // report those that touch an emitted element.
  const halfDropped = rawRels.filter((x) => byExpress.has(x.a) !== byExpress.has(x.b)).length;
  if (droppedRel && halfDropped)
    warnings.push(`relations: ${halfDropped} explicit relation(s) link an emitted element to a non-emitted entity; skipped`);
  progress("relations", 1);

  // ---- assemble -----------------------------------------------------------------
  const cmp = (x: string, y: string) => (x < y ? -1 : x > y ? 1 : 0);
  elements.sort((x, y) => cmp(x.id, y.id));
  relations.sort((x, y) => cmp(String(x.kind), String(y.kind)) || cmp(x.a, y.a) || cmp(x.b, y.b) || cmp(x.evidence.rule, y.evidence.rule));

  const project = r.line(r.ids(IFCPROJECT)[0]);
  const projectName = str(project?.LongName) ?? str(project?.Name);
  const meta: ModelInput["meta"] = {
    version: MODEL_INPUT_VERSION,
    units: "m",
    source: { format: "ifc", ...(opts.fileName ? { file: opts.fileName } : {}) },
  };
  if (schema) meta.schema = schema;
  if (projectName) meta.project = projectName;
  return { meta, levels, elements, relations, warnings };
}
