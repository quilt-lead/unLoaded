/**
 * Minimal structural runtime validator for ModelInput (test-only).
 * Returns a list of problems; empty means valid.
 */
import { MODEL_INPUT_VERSION } from "@unloaded/element-graph/input";

const isObj = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);
const isStr = (v: unknown): v is string => typeof v === "string";
const isNum = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);
const isVec3 = (v: unknown) => Array.isArray(v) && v.length === 3 && v.every(isNum);
const isParam = (v: unknown) => v === null || ["string", "number", "boolean"].includes(typeof v);

function checkSource(s: unknown, where: string, errs: string[]) {
  if (!isObj(s)) return void errs.push(`${where}: source missing`);
  if (!isStr(s.format)) errs.push(`${where}: source.format must be string`);
  for (const k of ["file", "nativeType"] as const) if (s[k] !== undefined && !isStr(s[k])) errs.push(`${where}: source.${k} must be string`);
  if (s.nativeId !== undefined && !isStr(s.nativeId) && !isNum(s.nativeId)) errs.push(`${where}: source.nativeId bad`);
}

export function validateModelInput(m: unknown): string[] {
  const errs: string[] = [];
  if (!isObj(m)) return ["not an object"];
  const meta = m.meta;
  if (!isObj(meta)) errs.push("meta missing");
  else {
    if (meta.version !== MODEL_INPUT_VERSION) errs.push("meta.version");
    if (meta.units !== "m") errs.push("meta.units must be 'm'");
    if (meta.schema !== undefined && !isStr(meta.schema)) errs.push("meta.schema");
    if (meta.project !== undefined && !isStr(meta.project)) errs.push("meta.project");
    checkSource(meta.source, "meta", errs);
  }
  for (const k of ["levels", "elements", "relations", "warnings"]) if (!Array.isArray(m[k])) errs.push(`${k} must be array`);
  if (errs.length) return errs;

  const levelIds = new Set<string>();
  for (const [i, l] of (m.levels as unknown[]).entries()) {
    if (!isObj(l) || !isStr(l.id) || !isStr(l.name) || !isNum(l.elevation)) errs.push(`levels[${i}] bad`);
    else levelIds.add(l.id);
  }
  const ids = new Set<string>();
  for (const [i, e] of (m.elements as unknown[]).entries()) {
    const w = `elements[${i}]`;
    if (!isObj(e)) {
      errs.push(`${w} not object`);
      continue;
    }
    if (!isStr(e.id) || !e.id) errs.push(`${w}.id`);
    else if (ids.has(e.id)) errs.push(`${w}.id duplicate ${e.id}`);
    else ids.add(e.id);
    if (!isStr(e.kind) || !e.kind) errs.push(`${w}.kind`);
    for (const k of ["mark", "name", "profile", "material", "levelId"] as const)
      if (e[k] !== undefined && !isStr(e[k])) errs.push(`${w}.${k} must be string`);
    if (isStr(e.levelId) && !levelIds.has(e.levelId)) errs.push(`${w}.levelId unknown`);
    if (!isObj(e.params)) errs.push(`${w}.params`);
    else for (const [k, v] of Object.entries(e.params)) if (!isParam(v)) errs.push(`${w}.params.${k} not primitive`);
    checkSource(e.source, w, errs);
    if (e.geometry !== undefined) {
      const g = e.geometry;
      if (!isObj(g) || !isObj(g.bbox) || !isVec3(g.bbox.min) || !isVec3(g.bbox.max)) errs.push(`${w}.geometry.bbox`);
      else {
        const { min, max } = g.bbox as { min: number[]; max: number[] };
        if (min.some((v, k) => v > max[k]!)) errs.push(`${w}.geometry.bbox min>max`);
        if (g.axis !== undefined && (!isObj(g.axis) || !isVec3(g.axis.start) || !isVec3(g.axis.end))) errs.push(`${w}.geometry.axis`);
        if (g.section !== undefined) {
          if (!isObj(g.section)) errs.push(`${w}.geometry.section`);
          else for (const k of ["depth", "width"]) if (g.section[k] !== undefined && !isNum(g.section[k])) errs.push(`${w}.geometry.section.${k}`);
        }
      }
    }
  }
  for (const [i, r] of (m.relations as unknown[]).entries()) {
    const w = `relations[${i}]`;
    if (!isObj(r) || !isStr(r.a) || !isStr(r.b) || !isStr(r.kind)) {
      errs.push(`${w} bad`);
      continue;
    }
    if (!ids.has(r.a) || !ids.has(r.b)) errs.push(`${w} endpoint not an element`);
    const ev = r.evidence;
    if (!isObj(ev) || !isStr(ev.rule) || (ev.source !== "explicit" && ev.source !== "inferred")) errs.push(`${w}.evidence`);
    else if (ev.detail !== undefined) {
      if (!isObj(ev.detail)) errs.push(`${w}.evidence.detail`);
      else for (const [k, v] of Object.entries(ev.detail)) if (!isParam(v)) errs.push(`${w}.evidence.detail.${k}`);
    }
  }
  if (!(m.warnings as unknown[]).every(isStr)) errs.push("warnings must be strings");
  return errs;
}
