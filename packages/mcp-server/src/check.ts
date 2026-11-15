/** The human-readable `--check` report (stderr). Built from project_summary, so it shows what the tools see. */
import { compactRanges, type Project } from "./project.ts";
import { projectSummary } from "./tools.ts";
import { ENGINE_PRODUCERS, ENGINE_VERSION } from "./engine.ts";

const list = (o: Record<string, number>) =>
  Object.entries(o)
    .sort((a, b) => b[1] - a[1] || (a[0] < b[0] ? -1 : 1))
    .map(([k, v]) => `${k} ${v}`)
    .join(", ") || "none";

export function checkReport(p: Project, opts: { serverName: string; version: string; suppressedWebIfc?: number; suppressedPdfjs?: number }): string {
  const s = projectSummary(p);
  const L: string[] = [];
  L.push(`${opts.serverName} ${opts.version} --check   engine ${ENGINE_VERSION} (${ENGINE_PRODUCERS.calc_mapper}, ${ENGINE_PRODUCERS.move_impact})`);
  L.push("");
  if (p.projectFile) {
    L.push(`Project     ${p.projectFile.name}  ("${p.projectFile.project}", exported ${p.projectFile.exportedAt})`);
    L.push(`  sha256    ${p.projectFile.sha256}`);
  }
  L.push(`Model       ${s.model.file}  (${s.project.model_format}${s.project.schema ? `, ${s.project.schema}` : ""}${s.project.name ? `, project "${s.project.name}"` : ""}; revision ${s.model.revision}, current)`);
  L.push(`  sha256    ${s.model.sha256}`);
  L.push(`  graph     sha256 ${s.model.graph_sha256} (canonical element-graph JSON, the engine's input)`);
  L.push(`  elements  ${s.model.elements}: ${list(s.model.nodes_by_kind)}`);
  L.push(`  category  ${list(s.model.elements_by_category)}`);
  L.push(`  storeys   ${s.model.storeys.map((l) => `${l.name} (${l.elevation_m} m) ${l.elements}`).join(", ") || "none"}`);
  L.push(`  edges     ${list(s.model.edges_by_kind)} (supports = load path); connection nodes ${s.model.connections}`);
  if (s.model_revisions.length > 1) {
    L.push(`Revisions   ${s.model_revisions.length} model revisions (compare_revisions diffs any two):`);
    for (const r of s.model_revisions) L.push(`  ${String(r.revision).padStart(3)}  ${r.file}  ${r.elements} elements${r.current ? "  [current]" : ""}  sha256 ${r.sha256.slice(0, 16)}...`);
  }
  L.push("");
  L.push("Calc PDFs");
  for (const d of s.calc_pdfs) {
    const pdf = p.pdfs.find((x) => x.name === d.file)!;
    L.push(`  [${d.doc_id}] ${d.file}  ${d.pages} pages, ${d.calcs} calcs, ${d.links} live links`);
    L.push(`    sha256  ${d.sha256}`);
    if (d.extraction !== "extracted") L.push(`    calcs   ${d.extraction === "stored" ? "the project file's stored extraction" : `re-extracted (${d.extraction_note})`}`);
    if (d.no_text_pages.length) L.push(`    no text layer on page(s) ${compactRanges(d.no_text_pages)}`);
    for (const c of pdf.calcs) {
      const flags = [c.scanned ? "scanned" : "", c.front ? "front matter" : "", c.cat, c.software].filter(Boolean).join(", ");
      const n = (p.linksByCalc.get(c.key) ?? []).filter((l) => l.status !== "rejected").length;
      L.push(`    p.${compactRanges(c.pages).padEnd(6)} ${c.key}${flags ? `  (${flags})` : ""}  ${n} links`);
    }
  }
  L.push("");
  L.push(`Links       ${s.links.live} live of ${s.links.total}: ${list(s.links.by_tier)}`);
  L.push(`  role      ${list(s.links.by_role)}; band ${list(s.links.by_band)}`);
  L.push(`  review    ${list(s.links.by_status)}`);
  L.push(`Status      confirmed ${s.element_status.confirmed}, review ${s.element_status.review}, unmapped ${s.element_status.unmapped}`);
  L.push(`Calc edges  ${s.calc_edges.total} (within a PDF ${s.calc_edges.within_pdf}, across PDFs ${s.calc_edges.cross_pdf}): ${list(s.calc_edges.by_rule)}`);
  L.push(`Groups      ${s.typical_groups.total} typical groups, ${s.typical_groups.linked} linked by ${s.typical_groups.group_links} group links`);
  L.push(`Findings    ${s.findings.total}${s.findings.total ? `: ${list(s.findings.by_kind)}` : ""}`);
  if (p.projectFile) L.push(`Decisions   ${p.baseLog.length} in the project file (read-only; applied first)`);
  if (p.decisions) {
    L.push(
      `${p.projectFile ? "  file      " : "Decisions   "}${p.decisions.path}: ${s.decisions.exists ? `${s.decisions.entries} entries` : "does not exist yet (created on the first recorded decision)"}; ${s.decisions.effective} effective, ${s.decisions.not_applied} not applied`,
    );
    if (p.decisions.sha256) L.push(`  sha256    ${p.decisions.sha256}`);
    L.push(`  writable  yes, as actor "${p.actor}"`);
  } else {
    L.push(`${p.projectFile ? "  file      " : "Decisions   "}none (read-only: add --decisions <file> to let your AI record review decisions)`);
  }
  const warnings = [...s.warnings];
  if (opts.suppressedWebIfc) warnings.push(`web-ifc printed ${opts.suppressedWebIfc} parser message(s) (suppressed; --verbose shows them)`);
  if (opts.suppressedPdfjs) warnings.push(`pdf.js printed ${opts.suppressedPdfjs} warning(s) (suppressed; --verbose shows them)`);
  L.push(`Warnings    ${warnings.length ? "" : "none"}`);
  for (const w of warnings) L.push(`  - ${w}`);
  const t = p.timings;
  const pdfT = `${p.pdfs.map((d) => `${d.name} read ${d.readMs} ms`).join(", ")}, map ${t.map_ms} ms`;
  L.push(`Timings     model${p.models.length > 1 ? "s" : ""} ${t.model_ms} ms, ${pdfT}, review ${t.review_ms} ms, total ${t.total_ms} ms`);
  L.push("");
  L.push("OK: ready to serve. Add the same arguments (without --check) to your MCP client config.");
  return L.join("\n");
}
