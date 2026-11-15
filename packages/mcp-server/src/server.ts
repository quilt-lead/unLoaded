/**
 * The MCP server: one tool per question an engineer asks of a project, every one read-only
 * (annotations say so; nothing here can write - the project file is only ever read).
 * Tool bodies are in tools.ts; this file is the schemas, descriptions and the result envelope.
 */
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import type { CallToolResult } from "@modelcontextprotocol/sdk/types.js";
import * as z from "zod";
import type { LoadedProject, ProjectSource } from "./project.ts";
import * as tools from "./tools.ts";

export const SERVER_NAME = "unloaded-calc-graph";
/** Pinned to package.json by a test. */
export const SERVER_VERSION = "0.1.0";

export const INSTRUCTIONS = `This server answers questions about ONE structural project saved from the unLoaded calc-graph app \
(a *.calcgraph.json file on this machine): the element graph built from the IFC model (beams, columns, connections, \
footings... with their load path and connectivity), the calc package PDF split into calcs, the links between elements \
and calcs with their evidence, typical groups, size-mismatch findings, revisions, and what goes stale when an element changes.

Everything is computed locally by the app's own calc engine (@unloaded/calc-mapper) from the file. Every link, calc, \
calc edge, finding and impact carries "provenance" (producer, rule, method, and the sha256 of the documents it rests on), \
and every result has a "source" block naming the project file, revisions and engine. Quote those when you cite a result. \
Links have a confidence "band" (high / medium / low), a "role" (design = the calc sizes the element; loads = it only takes \
loads from it), "reasons" (weighted evidence) and "caveats" - surface the caveats; a low or medium band is not a confirmed link. \
"review" says whether a person confirmed or rejected a link in the app; "auto" means nobody has reviewed it.

Start with project_summary, then search_elements / get_element, or get_calc on a calc key. To see the evidence, call \
get_page_image with a link's page and rects (rect to crop, highlight to outline). Elements can be named by GlobalId or mark. \
Tools default to the head revisions (what the app shows); pass model_revision / calc_revision (ids from list_revisions) for others. \
Nothing here changes the project: impact_of_change and move_column are what-if analyses only.`;

const RO = { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false } as const;

const revisionShape = {
  model_revision: z.number().int().optional().describe("Model revision id from list_revisions. Default: the head model revision."),
  calc_revision: z.number().int().optional().describe("Calc revision id from list_revisions. Default: the head calc package."),
};
const rect = z.array(z.number()).length(4);

function json(v: unknown): CallToolResult {
  return { content: [{ type: "text", text: JSON.stringify(v) }] };
}

function failure(e: unknown): CallToolResult {
  const err = e as Error;
  return { isError: true, content: [{ type: "text", text: `${err?.name ?? "Error"}: ${err?.message ?? String(e)}` }] };
}

export function createServer(source: ProjectSource): McpServer {
  const server = new McpServer({ name: SERVER_NAME, version: SERVER_VERSION }, { instructions: INSTRUCTIONS });

  const run = <A>(fn: (p: LoadedProject, a: A) => Promise<unknown>) =>
    async (a: A): Promise<CallToolResult> => {
      try {
        return json(await fn(await source.get(), a));
      } catch (e) {
        return failure(e);
      }
    };

  server.registerTool("project_summary", {
    title: "Project summary",
    description: "Overview of the project: name, revisions, element counts (by kind, storey and review status: confirmed / review / " +
      "unmapped), link counts by review and role, calc edges, load-path and connectivity edges, typical groups, findings, decisions, " +
      "and the calc list (key, title, software, element type, pages). Call this first.",
    inputSchema: revisionShape,
    annotations: RO,
  }, run((p, a: tools.RevisionArgs) => tools.projectSummary(p, a)));

  server.registerTool("search_elements", {
    title: "Search elements",
    description: "Find elements (filters combine with AND, case-insensitive substrings): mark (also matches name / GlobalId), kind " +
      "(Beam, Column, Connection, Footing, Slab, Wall, Brace, Pile, or an IFC type like IfcBeam), storey (\"Level 2\"), size (section, " +
      "spaces ignored: \"W18X35\", \"W18\"), grid (the model's grid parameter: \"B-C/2\", \"E/1\"), status (confirmed | review | unmapped). " +
      "Returns {count, returned, elements: [{global_id, mark, kind, storey, size, grid, status, calcs: [{calc, role, band, confidence, review}]}]}.",
    inputSchema: {
      mark: z.string().optional(), kind: z.string().optional(), storey: z.string().optional(), size: z.string().optional(),
      grid: z.string().optional(), status: z.enum(["confirmed", "review", "unmapped"]).optional(),
      limit: z.number().int().min(1).max(500).optional().describe("Max rows (default 50); count is always the full number of matches."),
      ...revisionShape,
    },
    annotations: RO,
  }, run((p, a: tools.SearchArgs) => tools.searchElements(p, a)));

  server.registerTool("get_element", {
    title: "Get element",
    description: "Everything known about one element (GlobalId or mark): its parameters and geometry (metres), review status, every " +
      "calc link (calc, page, confidence, band, role, tier, rule, matched text, evidence location + rects, weighted reasons, caveats, " +
      "provenance, review provenance), its typical groups and their group links, size-mismatch findings, load path neighbours " +
      "(bears_on: what it is supported by; carries: what it supports) and connectivity, and the decisions made on it.",
    inputSchema: { id: z.string().describe("GlobalId or mark, e.g. \"2B21\" or \"C5\"."), ...revisionShape },
    annotations: RO,
  }, run((p, a: tools.GetElementArgs) => tools.getElement(p, a)));

  server.registerTool("get_calc", {
    title: "Get calc",
    description: "One calc from the calc package (key from project_summary, or its exact title): title, software, element type, " +
      "pages, spans of page regions, title box, provenance; the elements it links to (with confidence, band, role, caveats, evidence, " +
      "provenance), its typical-group links, findings, and calc -> calc edges (feeds / fed_by, with the evidence text). " +
      "include_text returns the calc's own text from the PDF (its regions only).",
    inputSchema: {
      key: z.string(),
      include_text: z.boolean().optional(),
      max_chars: z.number().int().min(500).max(200000).optional().describe("Text limit with include_text (default 20000)."),
      ...revisionShape,
    },
    annotations: RO,
  }, run((p, a: tools.GetCalcArgs) => tools.getCalc(p, a)));

  server.registerTool("impact_of_change", {
    title: "Impact of a change",
    description: "What a change to, or the removal of, one element hits down the load path, and which calcs go stale - the app's " +
      "impact analysis. Returns the engine's impact (removed, hit: element -> wave, why, stale: calc -> reason, waves, provenance) " +
      "plus the hit elements with marks and the stale calcs with titles. Analysis only; nothing is changed.",
    inputSchema: {
      id: z.string().describe("GlobalId or mark of the element."),
      mode: z.enum(["change", "remove"]).optional().describe("Default change."),
      ...revisionShape,
    },
    annotations: RO,
  }, run((p, a: tools.ImpactArgs) => tools.impactOfChange(p, a)));

  server.registerTool("list_revisions", {
    title: "List revisions",
    description: "Model revisions (IFC / element graph) and calc revisions (PDF) in the project, oldest first, with which is head, " +
      "plus the size of the decision log. Use the ids with compare_revisions and the model_revision / calc_revision arguments.",
    inputSchema: {},
    annotations: RO,
  }, run((p, _a: unknown) => tools.listRevisions(p)));

  server.registerTool("compare_revisions", {
    title: "Compare model revisions",
    description: "Element-level diff of two MODEL revisions (the app's one revision diff): removed, added and changed elements " +
      "(per field: [before, after]) and load-path edges removed / added. Defaults: b = head model revision, a = the one before it.",
    inputSchema: { a: z.number().int().optional(), b: z.number().int().optional() },
    annotations: RO,
  }, run((p, a: tools.CompareArgs) => tools.compareRevisions(p, a)));

  server.registerTool("list_findings", {
    title: "List findings",
    description: "Size-mismatch findings: a calc's design line names an element's mark with a different size than the model. Each " +
      "has element, calc, model size, calc size, page, rects, snippet and provenance. Filter by calc key or element (GlobalId / mark).",
    inputSchema: {
      calc: z.string().optional(), element: z.string().optional(), limit: z.number().int().min(1).max(500).optional(), ...revisionShape,
    },
    annotations: RO,
  }, run((p, a: tools.FindingsArgs) => tools.listFindings(p, a)));

  server.registerTool("list_typical_groups", {
    title: "List typical groups",
    description: "Typical groups (elements of one kind, storey and size) and the calcs linked to a whole group by a size-only line " +
      "(\"Level 3 typical beams W18X35\"). Filter by kind, storey, size; linked_only keeps groups with a group link.",
    inputSchema: {
      kind: z.string().optional(), storey: z.string().optional(), size: z.string().optional(), linked_only: z.boolean().optional(),
      limit: z.number().int().min(1).max(500).optional(), ...revisionShape,
    },
    annotations: RO,
  }, run((p, a: tools.GroupsArgs) => tools.listTypicalGroups(p, a)));

  server.registerTool("get_page_image", {
    title: "Calc page image",
    description: "A page of the calc package PDF as a PNG, rendered locally. rect crops to [x0, y0, x1, y1] and highlight outlines " +
      "boxes, both in PDF points with the origin top-left - the frame of every rects / rect / title_box in the other results, so " +
      "copy them straight in. width is the image width in pixels (200-3000, default 1200).",
    inputSchema: {
      page: z.number().int().min(1),
      rect: rect.optional(),
      highlight: z.array(rect).optional(),
      width: z.number().int().min(200).max(3000).optional(),
      calc_revision: revisionShape.calc_revision,
    },
    annotations: RO,
  }, async (a: tools.PageImageArgs): Promise<CallToolResult> => {
    try {
      const { image, meta } = await tools.getPageImage(await source.get(), a);
      return {
        content: [
          { type: "image", data: Buffer.from(image.png).toString("base64"), mimeType: "image/png" },
          { type: "text", text: JSON.stringify(meta) },
        ],
      };
    } catch (e) {
      return failure(e);
    }
  });

  server.registerTool("move_column", {
    title: "Move a column (what-if)",
    description: "What happens if a column moves in plan by (dx, dy) metres, or is removed - read-only screening by the app's " +
      "move-impact engine on the model's geometry and load path: the elements on the path with reasons and chains, those whose " +
      "governing geometry changes > 5 % (before / after / ratio), member re-framing, clashes, and calcs linked to affected elements. " +
      "No calc values are read yet, so there are no utilisation estimates or health band. Nothing is changed.",
    inputSchema: {
      column: z.string().describe("GlobalId or mark of the column."),
      dx: z.number().optional().describe("Plan move along model x, metres."),
      dy: z.number().optional().describe("Plan move along model y, metres."),
      remove: z.boolean().optional(),
      ...revisionShape,
    },
    annotations: RO,
  }, run((p, a: tools.MoveArgs) => tools.moveColumn(p, a)));

  return server;
}

/** Tool names, in registration order (the README and a test list them). */
export const TOOL_NAMES = [
  "project_summary", "search_elements", "get_element", "get_calc", "impact_of_change", "list_revisions", "compare_revisions",
  "list_findings", "list_typical_groups", "get_page_image", "move_column",
] as const;
