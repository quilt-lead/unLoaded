/**
 * Build a project file in the app's format (src/data/projectStore.ts exportProject) without the
 * browser app: element graphs as model revisions, calc PDFs as calc revisions carrying the
 * extraction the app's worker makes (extractPdf + segmentCalcs), in the order given (ids 1, 2, ...),
 * so the last model and the last PDF are the heads, as in the app. For trying the server and for
 * tests; the app itself remains the way engineers make these files.
 */
import { extractPdf, parseGraph, segmentCalcs } from "@unloaded/calc-mapper";
import { nodePdfjs } from "./project.ts";
import { PROJECT_FILE_FORMAT, PROJECT_FILE_VERSION, encodeBase64, type ProjectFile, type ProjectFileDecision } from "@unloaded/project-file";

export interface InputRevision {
  kind: "model" | "calcs";
  /** File name, e.g. "model_rev1.graph.json" / "calc_package.pdf". */
  name: string;
  /** Model: a serialized element graph (JSON text bytes). Calcs: the PDF. */
  bytes: Uint8Array;
  label?: string;
}

export type InputDecision = Pick<ProjectFileDecision, "globalId" | "calcKey" | "action"> & Partial<Pick<ProjectFileDecision, "actor" | "note">>;

export async function makeProjectFile(opts: {
  name: string;
  revisions: InputRevision[];
  decisions?: InputDecision[];
  /** Timestamp written everywhere (a fixed one keeps the output byte-stable). */
  at?: string;
}): Promise<ProjectFile> {
  const at = opts.at ?? "2026-11-14T21:00:00-05:00";
  const seq = { model: 0, calcs: 0 };
  const revisions: ProjectFile["revisions"] = [];
  for (const r of opts.revisions) {
    const id = revisions.length + 1;
    const base = { id, seq: ++seq[r.kind], label: r.label ?? r.name, sourceName: r.name, createdAt: at, blob: encodeBase64(r.bytes) };
    if (r.kind === "model") {
      const graph = parseGraph(new TextDecoder().decode(r.bytes));
      revisions.push({ ...base, kind: "model", mediaType: "application/json", meta: { format: "element-graph", elements: graph.nodes.length, project: null }, graph });
    } else {
      const text = await extractPdf(r.bytes, { pdfjs: await nodePdfjs() });
      const pkg = segmentCalcs(text.pages, r.name);
      revisions.push({ ...base, kind: "calcs", mediaType: "application/pdf", meta: { pages: pkg.pages.length, calcs: pkg.calcs.length }, extraction: pkg });
    }
  }
  const last = (k: "model" | "calcs") => [...revisions].reverse().find((r) => r.kind === k)?.id ?? null;
  return {
    format: PROJECT_FILE_FORMAT, version: PROJECT_FILE_VERSION, exportedAt: at, project: { name: opts.name, createdAt: at }, revisions,
    decisions: (opts.decisions ?? []).map((d) => ({
      globalId: d.globalId, calcKey: d.calcKey, action: d.action, actor: d.actor ?? "reviewer", note: d.note ?? null, at,
      modelRev: last("model"), calcRev: last("calcs"),
    })),
  };
}
