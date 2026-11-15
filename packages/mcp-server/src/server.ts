/**
 * The MCP server: schemas, descriptions, annotations and the result envelope. Tool bodies are in
 * tools.ts. Reads are read-only; record_decision / record_decisions append to the decisions file
 * (the only thing the server ever writes).
 */
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import type { CallToolResult } from "@modelcontextprotocol/sdk/types.js";
import * as z from "zod";
import type { Project } from "./project.ts";
import * as tools from "./tools.ts";

export const SERVER_NAME = "unloaded";
/** Pinned to package.json by a test. */
export const SERVER_VERSION = "0.1.0";

export const INSTRUCTIONS = `This server answers questions about ONE structural project on this machine: an IFC model \
(turned into an element graph: beams, columns, slabs, footings, braces and connection nodes, with physical connectivity and \
the load path inferred from geometry) mapped to one or more calc-package PDFs (split into calcs), optionally with older model \
revisions to compare against. Everything is computed locally and deterministically by the unLoaded engine (calc-mapper; no AI \
inside); each result has a "source" block naming the model and calc PDFs with their sha256 and the engine version - cite it.

Links between elements and calcs have a tier (exact, range, loose, family, size, partial, xref, type, manual), a \
confidence "conf" (0..1, the sum of weighted "reasons") with a band (high >= 0.75, medium >= 0.5, low), a role (design = the \
calc sizes the element; loads = it only takes loads from / refers to it), caveats in plain words, the rule, page, matched token \
and highlight rects, provenance, and a review "status" (auto = nobody has reviewed it; confirmed / rejected / manual = a person \
decided). An element's status counts DESIGN links only: confirmed (a confirmed/manual design link or a high-band one), review, or \
unmapped. Findings are size mismatches (the calc designs a different size than the model has). Typical groups are elements of \
one kind, storey and size that a size-only calc links to once.

Start with project_summary. Elements can be named by GlobalId or (unique) mark. Calc keys come from list_calcs; keys of \
every calc PDF after the first are prefixed "<file-stem>/". Page numbers are always within one PDF. To show evidence, \
call get_page_image with global_id + calc_key (a link) or edge_src + edge_dst (calc-edge evidence) - it crops to the \
highlighted words. impact_of_change, move_column and compare_revisions are what-if / read-only analyses.

Writing: record_decision / record_decisions append review decisions (confirm, reject, manual, undo) to the decisions \
file, as the engineer. Only record a decision the user has asked for or clearly agreed to; tell them what you recorded. \
Nothing else is ever modified. undo clears the element-calc pair back to its automatic state (the engine applies only the \
latest decision per pair, and an undo drops the pair): earlier decisions on that pair are NOT restored, and a hand link \
is removed. Decisions are named by origin + id: "decisions_file" ids are the decisions file's own, "project_file" ids \
number a project file's log 1..n. If a result's source carries "decisions_warning", the decisions file cannot be read: \
tell the user; answers use the last good log and writes are refused until it is fixed.`;

const RO = { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false } as const;
const WRITE = { readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: false } as const;

const offset = z.number().int().min(0).optional().describe("Pagination offset (default 0). Use next_offset from the previous page.");
const limit = (d: number, max = 500) => z.number().int().min(1).max(max).optional().describe(`Page size (default ${d}, max ${max}).`);
const elementId = z.string().describe('GlobalId, or a mark that names one element (e.g. "2B21", "C5").');
const decisionShape = {
  global_id: z.string().describe("Exact IFC GlobalId of the element (not a mark)."),
  calc_key: z.string().describe("Exact calc key (from list_calcs / get_element)."),
  action: z.enum(["confirm", "reject", "manual", "undo"]).describe(
    "confirm / reject an automatic link; manual = link by hand (any element + calc); undo = clear this pair back to its automatic " +
      "state (earlier decisions on the pair are not restored; a hand link is removed).",
  ),
  note: z.string().max(2000).optional().describe("Why (recorded in the file)."),
};

function json(v: unknown): CallToolResult {
  return { content: [{ type: "text", text: JSON.stringify(v) }] };
}

function failure(e: unknown): CallToolResult {
  const err = e as Error;
  return { isError: true, content: [{ type: "text", text: `${err?.name ?? "Error"}: ${err?.message ?? String(e)}` }] };
}

export function createServer(project: Project): McpServer {
  const server = new McpServer({ name: SERVER_NAME, version: SERVER_VERSION }, { instructions: INSTRUCTIONS });

  // reads first pick up decisions written by someone else; a write does not: it re-reads the file
  // under the lock itself, and reports whether it found changes this server had not seen
  const run =
    <A>(fn: (p: Project, a: A) => unknown | Promise<unknown>, opts: { write?: boolean } = {}) =>
    async (a: A): Promise<CallToolResult> => {
      try {
        if (!opts.write) await project.refresh();
        return json(await fn(project, a));
      } catch (e) {
        return failure(e);
      }
    };

  server.registerTool(
    "project_summary",
    {
      title: "Project summary",
      description:
        "Overview: model (elements by kind / category / storey, connection nodes, edges by kind incl. supports = load path), model " +
        "revisions, each calc PDF (pages, calcs, key prefix, pages with no text layer), every calc (key, title, software, category, PDF, " +
        "pages), links by tier / role / band / review status, element status counts (confirmed / review / unmapped), calc edges (within / " +
        "across PDFs), typical groups, findings, the decisions file, warnings and source hashes. Call this first.",
      inputSchema: {},
      annotations: RO,
    },
    run((p) => tools.projectSummary(p)),
  );

  server.registerTool(
    "search_elements",
    {
      title: "Search elements",
      description:
        "Find elements. Filters combine with AND (case-insensitive): query (any of GlobalId / mark / name / profile / storey / kind), mark, " +
        "name, kind (element-graph kind: beam, column, slab, footing, brace, wall, connection... or IFC type like IfcBeam), category " +
        "(engine category: Beam, Column, Slab, Footing, Pile, Wall, Brace, Connection, Other), profile (spaces ignored: W18X35, HSS6), " +
        "storey, status (confirmed | review | unmapped), calc (linked to this calc key). Returns a page of elements with status and best link.",
      inputSchema: {
        query: z.string().optional(),
        mark: z.string().optional(),
        name: z.string().optional(),
        kind: z.string().optional(),
        category: z.string().optional(),
        profile: z.string().optional(),
        storey: z.string().optional(),
        status: z.enum(["confirmed", "review", "unmapped"]).optional(),
        calc: z.string().optional(),
        offset,
        limit: limit(50),
      },
      annotations: RO,
    },
    run((p, a: tools.SearchElementsArgs) => tools.searchElements(p, a)),
  );

  server.registerTool(
    "get_element",
    {
      title: "Get element",
      description:
        "Everything about one element: graph node data (params, geometry in metres, IFC type), mapping status, every calc link sorted by " +
        "confidence (tier, conf, band, role, reasons, caveats, rule, page, token, snippet, rects, PDF, provenance, review status and " +
        "decision: who / when / note), its typical groups and their group links, size-mismatch findings, its decisions, connectivity " +
        "(connections, members, parts, bears_on = supports out, carries = supports in, connected) with edge evidence, and one hop of the " +
        "load path up and down.",
      inputSchema: { id: elementId },
      annotations: RO,
    },
    run((p, a: { id: string }) => tools.getElement(p, a)),
  );

  server.registerTool(
    "list_calcs",
    {
      title: "List calcs",
      description:
        "Calcs across all calc PDFs (key, title, software, category, PDF, pages, scanned / front matter, live link counts by tier, element " +
        "count, calc edges in / out). Filter by pdf (file name or key prefix), category, software, query (key / title text).",
      inputSchema: { pdf: z.string().optional(), category: z.string().optional(), software: z.string().optional(), query: z.string().optional(), offset, limit: limit(100) },
      annotations: RO,
    },
    run((p, a: tools.ListCalcsArgs) => tools.listCalcs(p, a)),
  );

  server.registerTool(
    "get_calc",
    {
      title: "Get calc",
      description:
        "One calc: metadata, its PDF, pages and page regions (a calc can start or end mid-page), provenance, linked elements sorted by " +
        "confidence (tier, conf, band, role, caveats, review status; paginated with element_offset / element_limit), group links, findings, " +
        "calc edges in (fed_by) and out (feeds) with rules and evidence. include_text returns the calc's page text with the ranges that " +
        "belong to the calc, paginated by page (page_offset / page_limit, default 5 pages).",
      inputSchema: {
        key: z.string().describe("Calc key (or exact title)."),
        include_text: z.boolean().optional(),
        page_offset: z.number().int().min(0).optional(),
        page_limit: z.number().int().min(1).max(50).optional(),
        element_offset: z.number().int().min(0).optional(),
        element_limit: z.number().int().min(1).max(1000).optional(),
      },
      annotations: RO,
    },
    run((p, a: tools.GetCalcArgs) => tools.getCalc(p, a)),
  );

  server.registerTool(
    "search_calc_text",
    {
      title: "Search calc text",
      description:
        "Full-text search (literal, case-insensitive by default) over the text of every page of every calc PDF. Each hit: pdf, page, " +
        "calc key / title, span [start, end) in the page text, snippet and highlight rects. Pass span + pdf + page to get_page_image to see it.",
      inputSchema: { query: z.string().min(1), pdf: z.string().optional(), calc: z.string().optional(), case_sensitive: z.boolean().optional(), offset, limit: limit(50) },
      annotations: RO,
    },
    run((p, a: tools.SearchTextArgs) => tools.searchCalcText(p, a)),
  );

  server.registerTool(
    "trace_load_path",
    {
      title: "Trace load path",
      description:
        "Multi-hop load path from an element over supports edges: down = what it bears on, transitively (to the footings); up = what " +
        "bears on it. Each element has its depth (connection nodes are pass-through) and best calc; plus the supports edges among them.",
      inputSchema: {
        id: elementId,
        direction: z.enum(["down", "up", "both"]).optional().describe("Default down."),
        max_depth: z.number().int().min(1).max(500).optional().describe("Default 50."),
      },
      annotations: RO,
    },
    run((p, a: tools.TraceArgs) => tools.traceLoadPath(p, a)),
  );

  server.registerTool(
    "calc_dependencies",
    {
      title: "Calc dependencies",
      description:
        "The calc graph: edges src -> dst where src's output feeds dst's input, with rules (page reference, cross-reference) and evidence " +
        "(calc, pdf, page, text, line, rects). With key: the neighbourhood up to depth hops (direction feeds | fed_by | both). Without: " +
        "the whole graph, paginated. cross_pdf marks edges between two PDFs.",
      inputSchema: {
        key: z.string().optional(),
        depth: z.number().int().min(1).max(20).optional().describe("Default 1."),
        direction: z.enum(["feeds", "fed_by", "both"]).optional(),
        cross_pdf_only: z.boolean().optional(),
        offset,
        limit: limit(100),
      },
      annotations: RO,
    },
    run((p, a: tools.CalcDepsArgs) => tools.calcDependencies(p, a)),
  );

  server.registerTool(
    "impact_of_change",
    {
      title: "Impact of a change",
      description:
        "What a change to (mode change) or the removal of (mode remove) one element hits down the load path, and which calcs go stale " +
        "(linked to a hit / removed element, or downstream of a stale calc in the calc graph), with reasons and PDFs. Returns the engine's " +
        "impact (with provenance) plus readable lists. What-if analysis only; nothing is changed.",
      inputSchema: { id: elementId, mode: z.enum(["change", "remove"]).optional().describe("Default change.") },
      annotations: RO,
    },
    run((p, a: { id: string; mode?: "change" | "remove" }) => tools.impactOfChange(p, a)),
  );

  server.registerTool(
    "review_status",
    {
      title: "Review status",
      description:
        "Review progress: status counts, elements that need review (with their links), unmapped elements (with any loads-only links), and " +
        "unreviewed links below a confidence threshold (default 0.75, the high band), each list paginated with the same offset / limit.",
      inputSchema: { offset, limit: limit(50), low_conf_below: z.number().min(0).max(1).optional() },
      annotations: RO,
    },
    run((p, a: { offset?: number; limit?: number; low_conf_below?: number }) => tools.reviewStatus(p, a)),
  );

  server.registerTool(
    "list_findings",
    {
      title: "List findings",
      description:
        "Size-mismatch findings: a design line names the element's mark and a different size than the model gives (model size, calc " +
        "size, page, span, rects, snippet, provenance), with the element and calc. Findings on rejected links are left out. Filter by calc, " +
        "element (GlobalId or mark) or pdf.",
      inputSchema: { calc: z.string().optional(), element: z.string().optional(), pdf: z.string().optional(), offset, limit: limit(100) },
      annotations: RO,
    },
    run((p, a: tools.FindingsArgs) => tools.listFindings(p, a)),
  );

  server.registerTool(
    "list_typical_groups",
    {
      title: "List typical groups",
      description:
        "Typical groups: the elements of one kind, storey and size (id group:<category>:<storey>:<profile>, members with marks), and the " +
        "group links of size-only calcs (\"Level 3 typical beams W18X35\") that link a calc to the whole group once. Filter by kind " +
        "(category), storey, profile; linked_only keeps groups some calc links to.",
      inputSchema: {
        kind: z.string().optional(),
        storey: z.string().optional(),
        profile: z.string().optional(),
        linked_only: z.boolean().optional(),
        offset,
        limit: limit(100),
      },
      annotations: RO,
    },
    run((p, a: tools.GroupsArgs) => tools.listTypicalGroups(p, a)),
  );

  server.registerTool(
    "compare_revisions",
    {
      title: "Compare model revisions",
      description:
        "Diff two model revisions (the engine's diffGraphs, keyed on GlobalId): removed, added and changed elements (each changed field " +
        "before / after) and load-path edges removed / added, plus the calcs linked to an element in the diff. a and b are revision " +
        "numbers (project_summary.model_revisions) or file names; default: b = the current model, a = the revision before it. Needs " +
        "two model revisions (repeat --model, or a project file with several).",
      inputSchema: {
        a: z.union([z.string(), z.number().int()]).optional().describe("Base revision (before)."),
        b: z.union([z.string(), z.number().int()]).optional().describe("Compared revision (after). Default: the current model."),
        limit: z.number().int().min(1).max(20000).optional().describe("Max items per list (default 500)."),
      },
      annotations: RO,
    },
    run((p, a: tools.CompareArgs) => tools.compareRevisions(p, a)),
  );

  server.registerTool(
    "move_column",
    {
      title: "Move or remove a column (what-if)",
      description:
        "What happens if a column moves by dx / dy metres in plan, or is removed (remove true): @unloaded/move-impact on the current " +
        "model's geometry and supports edges - elements on the path with reasons and chains, the geometric screen (governing quantity " +
        "before / after, > 5 % change), re-framing, clashes, notes, assumptions, and stale calcs from the reviewed links. No calc values " +
        "are read, so no utilisation estimates or health band. Nothing is changed.",
      inputSchema: {
        column: elementId,
        dx: z.number().optional().describe("Plan move in x, metres."),
        dy: z.number().optional().describe("Plan move in y, metres."),
        remove: z.boolean().optional().describe("Remove the column instead of moving it."),
      },
      annotations: RO,
    },
    run((p, a: tools.MoveArgs) => tools.moveColumn(p, a)),
  );

  server.registerTool(
    "export_mapping",
    {
      title: "Export mapping",
      description:
        "The engine's export (buildExport), one report per calc PDF: calcs, calc edges, load path, connectivity, typical groups, group " +
        "links, findings, producers, and every element with its status and calcs (confidence, tier, role, band, reasons, caveats, rule, " +
        "matched text, review, provenance). Large: page the elements with element_offset / element_limit.",
      inputSchema: { element_offset: z.number().int().min(0).optional(), element_limit: z.number().int().min(1).max(5000).optional() },
      annotations: RO,
    },
    run((p, a: { element_offset?: number; element_limit?: number }) => tools.exportMappingTool(p, a)),
  );

  server.registerTool(
    "get_page_image",
    {
      title: "Calc page image",
      description:
        "Render a calc PDF page as PNG, highlighting evidence: global_id + calc_key (a link's matched words), edge_src + edge_dst " +
        "(+ evidence_index) for calc-edge evidence, span [start, end) of the page text (from search_calc_text), or highlight rects. With " +
        "evidence it crops to a full-width band around the highlight, padding pt above / below (default 48; tight true pads all four sides); " +
        "crop false for the full page, or rect [x0, y0, x1, y1] to choose. " +
        "Frame: PDF points, origin top-left. pdf defaults to the main PDF; page defaults to the evidence page. width in pixels (200-3000).",
      inputSchema: {
        pdf: z.string().optional(),
        page: z.number().int().min(1).optional(),
        global_id: z.string().optional(),
        calc_key: z.string().optional(),
        span: z.tuple([z.number().int(), z.number().int()]).optional(),
        edge_src: z.string().optional(),
        edge_dst: z.string().optional(),
        evidence_index: z.number().int().min(0).optional(),
        highlight: z.array(z.array(z.number()).length(4)).optional(),
        crop: z.boolean().optional(),
        tight: z.boolean().optional(),
        padding: z.number().min(0).max(500).optional(),
        rect: z.array(z.number()).length(4).optional(),
        width: z.number().int().min(200).max(3000).optional(),
      },
      annotations: RO,
    },
    async (a: tools.PageImageArgs): Promise<CallToolResult> => {
      try {
        await project.refresh();
        const { image, meta } = await tools.getPageImage(project, a);
        return {
          content: [
            { type: "image", data: Buffer.from(image.png).toString("base64"), mimeType: "image/png" },
            { type: "text", text: JSON.stringify(meta) },
          ],
        };
      } catch (e) {
        return failure(e);
      }
    },
  );

  server.registerTool(
    "record_decision",
    {
      title: "Record a review decision",
      description:
        "WRITES: append one review decision to the decisions file (append-only; nothing is deleted or rewritten): confirm or reject an " +
        "automatic element-calc link, manual = link an element to a calc by hand, undo = clear that pair back to its automatic state " +
        "(earlier decisions on the pair are not restored; a hand link is removed). Recorded with the time and the configured actor. Only " +
        "on the user's request. Returns the decision (origin decisions_file + its id in the file), the link and element status before and " +
        "after, and reloaded_external_changes (true when the file held decisions written elsewhere since this server last read it; they " +
        "are kept).",
      inputSchema: decisionShape,
      annotations: WRITE,
    },
    run((p, a: tools.DecisionInput) => tools.recordDecisions(p, { decisions: [a] }), { write: true }),
  );

  server.registerTool(
    "record_decisions",
    {
      title: "Record review decisions (batch)",
      description:
        "WRITES: append several review decisions at once (same rules as record_decision). All or nothing: if any decision is invalid, " +
        "none is written and every problem is listed.",
      inputSchema: { decisions: z.array(z.object(decisionShape)).min(1).max(500) },
      annotations: WRITE,
    },
    run((p, a: { decisions: tools.DecisionInput[] }) => tools.recordDecisions(p, a), { write: true }),
  );

  // resources: cheap read-only views
  server.registerResource(
    "summary",
    "unloaded://project/summary",
    { title: "Project summary", description: "project_summary as a resource", mimeType: "application/json" },
    async (uri) => {
      await project.refresh();
      return { contents: [{ uri: uri.href, mimeType: "application/json", text: JSON.stringify(tools.projectSummary(project)) }] };
    },
  );
  server.registerResource(
    "decisions",
    "unloaded://project/decisions",
    { title: "Decisions log", description: "The review decisions file, as currently on disk", mimeType: "application/json" },
    async (uri) => {
      await project.refresh();
      return { contents: [{ uri: uri.href, mimeType: "application/json", text: JSON.stringify(tools.decisionsLog(project)) }] };
    },
  );

  return server;
}

/** Tool names, in registration order (the README, tests and parity script list them). */
export const TOOL_NAMES = [
  "project_summary",
  "search_elements",
  "get_element",
  "list_calcs",
  "get_calc",
  "search_calc_text",
  "trace_load_path",
  "calc_dependencies",
  "impact_of_change",
  "review_status",
  "list_findings",
  "list_typical_groups",
  "compare_revisions",
  "move_column",
  "export_mapping",
  "get_page_image",
  "record_decision",
  "record_decisions",
] as const;
export const WRITE_TOOLS = ["record_decision", "record_decisions"] as const;
