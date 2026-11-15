/**
 * Build a *.calcgraph.json project file without the browser app, in exactly the app's format
 * (scripts/makeProjectFile.ts): for trying the MCP server on the synthetic package, or on any element
 * graph + calc PDF. The order of the --model / --calcs flags is the revision order; the LAST model is
 * the head, as in the app. Each PDF is a revision of a calc document: "d1" unless a --doc <id> comes
 * before it (it applies to every --calcs after it), so the last PDF of each document is its head.
 *
 *   node packages/mcp-server/scripts/make-project-file.ts --out sample.calcgraph.json --name "Sample" \
 *     --model rev1.graph.json --calcs calc_package.pdf [--model rev2.graph.json] [--doc d2 --calcs supplement.pdf] \
 *     [--decisions decisions.json]
 *
 * --model takes a serialized element graph (build one from an IFC with
 * tools/calcgraph-reference/scripts/build_graph.mjs). --decisions: a JSON list of
 * {globalId, calcKey, action: confirm|reject|manual|undo, actor?, note?} (the project file's own log format).
 */
import { readFileSync, writeFileSync } from "node:fs";
import { basename } from "node:path";
import { parseArgs } from "node:util";
import { makeProjectFile, type InputDecision, type InputRevision } from "./makeProjectFile.ts";

const { values, tokens } = parseArgs({
  tokens: true,
  options: {
    out: { type: "string" }, name: { type: "string" }, model: { type: "string", multiple: true },
    calcs: { type: "string", multiple: true }, doc: { type: "string", multiple: true }, decisions: { type: "string" }, at: { type: "string" },
  },
});
if (!values.out || !values.model?.length) {
  console.error("usage: make-project-file.ts --out p.calcgraph.json --model g.json [--calcs c.pdf] [--model g2.json] [--doc d2 --calcs s.pdf] [--name N] [--decisions d.json]");
  process.exit(2);
}
const revisions: InputRevision[] = [];
let docId: string | undefined;
for (const t of tokens ?? []) {
  if (t.kind !== "option" || !t.value) continue;
  if (t.name === "doc") docId = t.value;
  else if (t.name === "model") revisions.push({ kind: "model", name: basename(t.value), bytes: new Uint8Array(readFileSync(t.value)) });
  else if (t.name === "calcs") revisions.push({ kind: "calcs", name: basename(t.value), bytes: new Uint8Array(readFileSync(t.value)), ...(docId ? { docId } : {}) });
}
const file = await makeProjectFile({
  name: values.name ?? "Untitled project",
  revisions,
  decisions: values.decisions ? (JSON.parse(readFileSync(values.decisions, "utf8")) as InputDecision[]) : [],
  ...(values.at ? { at: values.at } : {}),
});
writeFileSync(values.out, JSON.stringify(file));
const n = (k: string) => file.revisions.filter((r) => r.kind === k).length;
console.error(`${values.out}: ${file.revisions.length} revisions (${n("model")} model, ${n("calcs")} calcs in ${file.documents.length} document(s)), ${file.decisions.length} decisions`);
