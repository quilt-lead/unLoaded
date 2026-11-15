/** The human-readable `--check` report (stderr). Built from project_summary, so it shows what the tools see. */
import { compactRanges, type Project } from "./project.ts";
import { projectSummary } from "./tools.ts";
import { ENGINE_VERSION } from "./engine.ts";

const list = (o: Record<string, number>) =>
  Object.entries(o)
    .sort((a, b) => b[1] - a[1] || (a[0] < b[0] ? -1 : 1))
    .map(([k, v]) => `${k} ${v}`)
    .join(", ") || "none";

export function checkReport(p: Project, opts: { serverName: string; version: string; suppressedWebIfc?: number; suppressedPdfjs?: number }): string {
  const s = projectSummary(p);
  const L: string[] = [];
  L.push(`${opts.serverName} ${opts.version} --check   engine ${ENGINE_VERSION}`);
  L.push("");
  L.push(`Model       ${s.model.file}  (${s.project.model_format}${s.project.schema ? `, ${s.project.schema}` : ""}${s.project.name ? `, project "${s.project.name}"` : ""})`);
  L.push(`  sha256    ${s.model.sha256}`);
  L.push(`  elements  ${s.model.elements}: ${list(s.model.nodes_by_kind)}`);
  L.push(`  category  ${list(s.model.elements_by_category)}`);
  L.push(`  storeys   ${s.model.storeys.map((l) => `${l.name} (${l.elevation_m} m) ${l.elements}`).join(", ") || "none"}`);
  L.push(`  edges     ${list(s.model.edges_by_kind)} (supports = load path); connection nodes ${s.model.connections}`);
  L.push("");
  L.push("Calc PDFs");
  for (const d of s.calc_pdfs) {
    const pdf = p.pdfs.find((x) => x.name === d.file)!;
    L.push(`  ${d.main ? "[main]" : `[${d.key_prefix}]`} ${d.file}  ${d.pages} pages, ${d.calcs} calcs, ${d.links} live links`);
    L.push(`    sha256  ${d.sha256}`);
    if (d.no_text_pages.length) L.push(`    no text layer on page(s) ${compactRanges(d.no_text_pages)}`);
    for (const c of pdf.calcs) {
      const flags = [c.scanned ? "scanned" : "", c.front ? "front matter" : "", c.cat, c.software].filter(Boolean).join(", ");
      const n = (p.linksByCalc.get(c.key) ?? []).filter((l) => l.status !== "rejected").length;
      L.push(`    p.${compactRanges(c.pages).padEnd(6)} ${c.key}${flags ? `  (${flags})` : ""}  ${n} links`);
    }
  }
  L.push("");
  L.push(`Links       ${s.links.live} live of ${s.links.total}: ${list(s.links.by_tier)}`);
  L.push(`  review    ${list(s.links.by_status)}`);
  L.push(`Status      confirmed ${s.element_status.confirmed}, review ${s.element_status.review}, unmapped ${s.element_status.unmapped}`);
  L.push(`Calc edges  ${s.calc_edges.total} (within a PDF ${s.calc_edges.within_pdf}, across PDFs ${s.calc_edges.cross_pdf}): ${list(s.calc_edges.by_rule)}`);
  if (p.decisions) {
    L.push(
      `Decisions   ${p.decisions.path}: ${s.decisions.exists ? `${s.decisions.entries} entries, ${s.decisions.effective} effective, ${s.decisions.not_applied} not applied` : "does not exist yet (created on the first recorded decision)"}`,
    );
    if (p.decisions.sha256) L.push(`  sha256    ${p.decisions.sha256}`);
    L.push(`  writable  yes, as actor "${p.actor}"`);
  } else {
    L.push("Decisions   none (read-only: add --decisions <file> to let your AI record review decisions)");
  }
  const warnings = [...s.warnings];
  if (opts.suppressedWebIfc) warnings.push(`web-ifc printed ${opts.suppressedWebIfc} parser message(s) (suppressed; --verbose shows them)`);
  if (opts.suppressedPdfjs) warnings.push(`pdf.js printed ${opts.suppressedPdfjs} warning(s) (suppressed; --verbose shows them)`);
  L.push(`Warnings    ${warnings.length ? "" : "none"}`);
  for (const w of warnings) L.push(`  - ${w}`);
  const t = p.timings;
  const pdfT = p.pdfs.map((d) => `${d.name} read ${d.readMs} ms + map ${d.mapMs} ms`).join(", ");
  L.push(`Timings     model ${t.model_ms} ms, ${pdfT}, review ${t.review_ms} ms, total ${t.total_ms} ms`);
  L.push("");
  L.push("OK: ready to serve. Add the same arguments (without --check) to your MCP client config.");
  return L.join("\n");
}
