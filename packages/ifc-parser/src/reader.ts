/**
 * Thin, cached accessor over a web-ifc model plus helpers for unwrapping the
 * `{ type, name, value }` objects web-ifc returns from `GetLine`.
 */
import type { IfcAPI } from "web-ifc";
import type { ParamValue } from "@unloaded/element-graph/input";

/** web-ifc token type for references (`#123`). */
const REF = 5;

export type Line = Record<string, unknown> & { expressID: number; type: number };

export class IfcReader {
  private lines = new Map<number, Line | null>();
  private typeNames = new Map<number, string>();

  readonly api: IfcAPI;
  readonly modelID: number;

  // No TS parameter properties: keeps the source runnable with Node's type stripping.
  constructor(api: IfcAPI, modelID: number) {
    this.api = api;
    this.modelID = modelID;
  }

  line(id: number | undefined | null): Line | undefined {
    if (id === undefined || id === null) return undefined;
    let l = this.lines.get(id);
    if (l === undefined) {
      try {
        l = (this.api.GetLine(this.modelID, id) as Line) ?? null;
      } catch {
        l = null;
      }
      this.lines.set(id, l);
    }
    return l ?? undefined;
  }

  /** CamelCase IFC entity name ("IfcBeam") for a line or type code. */
  nameOfCode(code: number): string {
    let n = this.typeNames.get(code);
    if (n === undefined) {
      try {
        n = String(this.api.GetNameFromTypeCode(code) ?? "");
      } catch {
        n = "";
      }
      this.typeNames.set(code, n);
    }
    return n;
  }

  typeOf(id: number | undefined): string {
    const l = this.line(id);
    return l ? this.nameOfCode(l.type) : "";
  }

  ids(typeCode: number): number[] {
    const out: number[] = [];
    try {
      const v = this.api.GetLineIDsWithType(this.modelID, typeCode);
      const n = v.size();
      for (let i = 0; i < n; i++) out.push(v.get(i));
    } catch {
      /* type not in this schema */
    }
    return out;
  }
}

/** Express id of a reference attribute, if it is one. */
export function ref(v: unknown): number | undefined {
  if (v && typeof v === "object" && (v as { type?: unknown }).type === REF) {
    const id = (v as { value?: unknown }).value;
    return typeof id === "number" ? id : undefined;
  }
  return undefined;
}

/** All express ids of a reference or a list of references. */
export function refs(v: unknown): number[] {
  if (Array.isArray(v)) return v.map(ref).filter((x): x is number => x !== undefined);
  const r = ref(v);
  return r === undefined ? [] : [r];
}

/** Decodes IFC STEP string escapes (\X2\...\X0\, \X\hh, \S\c) if still present. */
export function decodeIfcString(s: string): string {
  if (!s.includes("\\")) return s;
  return s
    .replace(/\\X2\\((?:[0-9A-F]{4})+)\\X0\\/gi, (_, hex: string) => {
      let out = "";
      for (let i = 0; i < hex.length; i += 4) out += String.fromCharCode(parseInt(hex.slice(i, i + 4), 16));
      return out;
    })
    .replace(/\\X\\([0-9A-F]{2})/gi, (_, h: string) => String.fromCharCode(parseInt(h, 16)))
    .replace(/\\S\\(.)/g, (_, c: string) => String.fromCharCode(c.charCodeAt(0) + 128));
}

/** Plain string value of an attribute (label, identifier, text, enum). */
export function str(v: unknown): string | undefined {
  if (v === null || v === undefined) return undefined;
  if (typeof v === "string") return decodeIfcString(v);
  if (typeof v === "object" && "value" in (v as object)) {
    const inner = (v as { value: unknown; type?: unknown }).value;
    if ((v as { type?: unknown }).type === REF) return undefined;
    if (typeof inner === "string") return decodeIfcString(inner);
    if (typeof inner === "number" || typeof inner === "boolean") return String(inner);
  }
  return undefined;
}

/** Numeric value of an attribute, if numeric. */
export function num(v: unknown): number | undefined {
  if (typeof v === "number") return Number.isFinite(v) ? v : undefined;
  if (v && typeof v === "object" && "value" in (v as object)) {
    if ((v as { type?: unknown }).type === REF) return undefined;
    const inner = (v as { value: unknown }).value;
    if (typeof inner === "number" && Number.isFinite(inner)) return inner;
    if (typeof inner === "string" && inner.trim() !== "" && Number.isFinite(Number(inner))) return Number(inner);
  }
  return undefined;
}

/** Upper-case IFC measure/type name of a typed value, e.g. "IFCLENGTHMEASURE". */
export function measureName(v: unknown): string | undefined {
  if (v && typeof v === "object" && typeof (v as { name?: unknown }).name === "string") {
    return ((v as { name: string }).name).toUpperCase();
  }
  return undefined;
}

/**
 * Unwraps an IFC typed value into a primitive ParamValue.
 * Booleans/logicals -> boolean (UNKNOWN -> null); numbers -> number; enums and
 * labels -> string; references -> undefined (not representable).
 */
export function primitive(v: unknown): ParamValue | undefined {
  if (v === null || v === undefined) return undefined;
  if (typeof v === "boolean") return v;
  if (typeof v === "number") return Number.isFinite(v) ? v : null;
  if (typeof v === "string") return decodeIfcString(v);
  if (Array.isArray(v)) {
    const parts = v.map(primitive).filter((x): x is Exclude<ParamValue, null> => x !== undefined && x !== null);
    if (parts.length === 0) return undefined;
    if (parts.length === 1) return parts[0]!;
    return parts.map(String).join(", ");
  }
  if (typeof v === "object") {
    const o = v as { type?: unknown; name?: unknown; value?: unknown };
    if (o.type === REF) return undefined;
    const name = typeof o.name === "string" ? o.name.toUpperCase() : "";
    const inner = o.value;
    if (name === "IFCBOOLEAN" || name === "IFCLOGICAL") {
      if (typeof inner === "boolean") return inner;
      if (typeof inner === "string") {
        const s = inner.replace(/\./g, "").toUpperCase();
        if (s === "T" || s === "TRUE") return true;
        if (s === "F" || s === "FALSE") return false;
        return null;
      }
      return null;
    }
    return primitive(inner);
  }
  return undefined;
}

const PLACEHOLDERS = new Set(["", "-", "--", "n.a.", "n.a", "na", "n/a", "none", "null", "undefined", "?", "<none>", "default"]);

export function isPlaceholder(s: string | undefined): boolean {
  return s === undefined || PLACEHOLDERS.has(s.trim().toLowerCase());
}
