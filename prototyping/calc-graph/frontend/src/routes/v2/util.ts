// Shared helpers for the v2 pages: colour scales (hex, because three.js needs real colours in both
// themes), the design index (element / record / gid lookups), and PdfSource builders.
import { useMemo } from "react";
import { useV2Design } from "../../api/hooks";
import { urls } from "../../api/client";
import type { PdfSource } from "../../components/PdfPage";
import type {
  V2Design,
  V2DesignElement,
  V2Occurrence,
  V2Record,
} from "../../api/types";
import type { Band } from "./api";

export const BANDS: readonly Band[] = [
  "easy",
  "moderate",
  "hard",
  "do-not-move",
];
export const BAND_COLOR: Record<Band, string> = {
  easy: "#1f9d5b",
  moderate: "#e0a020",
  hard: "#e2622b",
  "do-not-move": "#b0203a",
};
export const BAND_LABEL: Record<Band, string> = {
  easy: "Easy",
  moderate: "Moderate",
  hard: "Hard",
  "do-not-move": "Do not move",
};
export const BAND_TONE: Record<Band, "good" | "warn" | "bad"> = {
  easy: "good",
  moderate: "warn",
  hard: "bad",
  "do-not-move": "bad",
};

/** estimated UC colours */
export const UC_COLOR = {
  ok: "#1f9d5b",
  near: "#e0a020",
  over: "#d23c3c",
  stale: "#8a5cf0",
  moved: "#2f6fed",
  faded: "#d5dae0",
};

/** the lateral system drawn over the faded gravity framing, so the braced and moment frames read in 3D */
export const LATERAL_COLOR = "#3f7fbf";
const FRAME_ROLES = ["scbf_brace", "scbf_beam", "smf_beam"];
/** braces (and frame beams, lighter) in the lateral colour; undefined for any other element */
export function lateralStyle(e: { type: string; roles?: unknown }, dim = 1): { color: string; opacity: number } | undefined {
  const roles = Array.isArray(e.roles) ? (e.roles as string[]) : [];
  if (e.type === "brace" || roles.includes("scbf_brace")) return { color: LATERAL_COLOR, opacity: 0.95 * dim };
  if (roles.some((r) => FRAME_ROLES.includes(r))) return { color: LATERAL_COLOR, opacity: 0.5 * dim };
  return undefined;
}
export const ucColor = (uc: number | null | undefined) =>
  uc == null
    ? UC_COLOR.stale
    : uc > 1.0
      ? UC_COLOR.over
      : uc > 0.9
        ? UC_COLOR.near
        : UC_COLOR.ok;
export const ucTone = (
  uc: number | null | undefined,
): "good" | "warn" | "bad" | "neutral" =>
  uc == null ? "neutral" : uc > 1.0 ? "bad" : uc > 0.9 ? "warn" : "good";
export const fmtUc = (uc: number | null | undefined) =>
  uc == null ? "-" : uc.toFixed(2);

export const fmtUsd = (v: number) =>
  "$" + Math.round(v).toLocaleString("en-US");
export const fmtFt = (v: number) =>
  `${v >= 0 ? "+" : ""}${(Math.round(v * 100) / 100).toString()} ft`;

/** "COL-2B" -> "2B" */
export const colShort = (c: string) => c.replace(/^COL-/, "");

export interface SpecArticle {
  id: string;
  page: number;
  bbox: [number, number, number, number];
  section: string;
  article: string;
  title: string;
  text: string;
  section_title?: string;
}

export interface DesignIndex {
  design: V2Design;
  el: Map<string, V2DesignElement>;
  byGid: Map<string, V2DesignElement>;
  rec: Map<string, V2Record>;
  calcTitle: Map<string, { title: string; software: string; section: string }>;
  columns: V2DesignElement[];
  sheets: { sheet: string; page: number; title: string; kind: string }[];
  specArticles: Map<string, SpecArticle>;
  occurrences: V2Occurrence[];
  building: {
    columns: Record<string, [number, number]>;
    grids: { x: [string, number][]; y: [string, number][] };
    levels: { key: string; name: string; elev_ft: number }[];
    name: string;
  };
}

/** One index over /api/v2/design (cached by TanStack Query; the index is memoised per payload). */
export function useDesignIndex(): {
  idx: DesignIndex | null;
  isLoading: boolean;
  error: unknown;
} {
  const q = useV2Design();
  const idx = useMemo(() => {
    const d = q.data;
    if (!d) return null;
    const el = new Map(d.elements.map((e) => [e.id, e]));
    for (const t of ((d as Record<string, unknown>).types as
      V2DesignElement[] | undefined) ?? [])
      if (!el.has(t.id)) el.set(t.id, t);
    const byGid = new Map(
      d.elements.filter((e) => e.global_id).map((e) => [e.global_id!, e]),
    );
    const rec = new Map(d.records.map((r) => [r.id, r]));
    const calcs =
      ((d as Record<string, unknown>).calcs as {
        id: string;
        title: string;
        software: string;
        section: string;
      }[]) ?? [];
    const calcTitle = new Map(calcs.map((c) => [c.id, c]));
    const sa =
      ((d as Record<string, unknown>).spec_articles as SpecArticle[] | undefined) ?? [];
    return {
      design: d,
      el,
      byGid,
      rec,
      calcTitle,
      columns: d.elements.filter((e) => e.type === "column"),
      sheets:
        ((d as Record<string, unknown>).sheets as DesignIndex["sheets"]) ?? [],
      specArticles: new Map(sa.map((a) => [a.id, a])),
      occurrences:
        ((d as Record<string, unknown>).occurrences as V2Occurrence[]) ?? [],
      building: (d as Record<string, unknown>)
        .building as DesignIndex["building"],
    } satisfies DesignIndex;
  }, [q.data]);
  return { idx, isLoading: q.isLoading, error: q.error };
}

const DOC_NAME: Record<string, string> = {
  calcs: "Calc package",
  drawings: "Drawing set",
  specs: "Spec book",
};

export function occSource(o: V2Occurrence): PdfSource | null {
  if (!o.page || !["calcs", "drawings", "specs"].includes(o.doc)) return null;
  return {
    url: urls.v2DocFile(o.doc),
    page: o.page,
    rects: o.bbox ? [o.bbox] : [],
    label: `${o.article ?? o.ref} - ${howLabel(o.how)}${o.label && o.doc !== "etabs" ? ` (${o.label})` : ""}`,
    sub: `${DOC_NAME[o.doc] ?? o.doc} p.${o.page}${o.sheet ? `, sheet ${o.sheet}` : ""}${o.via?.length ? `, via ${o.via.join(", ")}` : ""}${o.text ? ` - "${o.text.slice(0, 80)}"` : ""}${o.text_layer === false ? " (scanned page, no text layer)" : ""}`,
  };
}

export function recordSource(
  r: V2Record | undefined,
  note?: string,
): PdfSource | null {
  if (!r?.page) return null;
  return {
    url: urls.v2DocFile("calcs"),
    page: r.page,
    rects: r.bbox ? [r.bbox] : [],
    label: `${r.id} - ${r.calc_title ?? r.kind}`,
    sub: `Calc package p.${r.page}${r.sheet ? `, sheet ${r.sheet}` : ""}${r.uc != null ? ` - UC ${fmtUc(r.uc)}` : ""}${note ? ` - ${note}` : ""}`,
  };
}

export const HOW_LABEL: Record<string, string> = {
  "ifc-element": "IFC element",
  calc_row: "calc row",
  plan_tag: "plan tag",
  schedule_row: "schedule row",
  detail_callout: "detail callout",
  elevation: "elevation",
  elevation_tag: "elevation tag",
  section: "section",
  spec_article: "spec article",
  "governing-spec": "governing spec",
  "etabs-object": "ETABS object",
};
export const howLabel = (h: string) => HOW_LABEL[h] ?? h.replace(/[_-]/g, " ");

export const PLATFORM_LABEL: Record<string, string> = {
  procore: "Procore",
  autodesk_build: "Autodesk Build",
  acc: "Autodesk Build",
  forma: "Autodesk Forma",
};

/** Why the handcalcs re-run sheet (math) of one re-run record cannot be shown, or null when it can.
 * Every reason comes from the revision itself: the render error, the record's own `missing` note, or
 * a revision written without re-run sheets (restored from one that had none). */
export function rerunSheetUnavailable(
  result: { new_page?: { rerun_sheet?: { page: number | null; missing?: string } } },
  rev: { files?: Record<string, unknown> },
): string | null {
  const err = rev.files?.rerun_sheets_error;
  if (typeof err === "string" && err) return `The re-run sheets failed to render: ${err.split("\n")[0].slice(0, 300)}`;
  const rs = result.new_page?.rerun_sheet;
  if (rs?.missing) return `No math sheet for this record: ${rs.missing}`;
  if (!rev.files?.rerun_sheets_pdf) return "This calc revision has no re-run sheets (it was written without them).";
  if (!rs || rs.page == null) return "No math sheet for this record in this revision.";
  return null;
}
