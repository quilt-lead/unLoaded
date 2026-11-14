// Help ratchet - runs inside `npm run build` (locally and in CI). Fails the build when:
//  1. an id used in the UI is not in the help registry (src/help/registry.ts);
//  2. a registry entry is used nowhere (glossary terms and declared families excepted);
//  3. a JSX tag of a component in REQUIRE_INFO is written without an `info=` prop;
//  4. a source file under src/ (outside src/legacy) contains an em dash (house style: hyphens);
//  5. an entry has an empty title/short or a `terms` link to a non-term id.
// How ids are found (string literals only - ids must be literal so this script can see them):
//   <InfoTip id="x">   info="x"   info={"x"}   info: "x"   helpFamily("fam", ...) marks fam.* used.
// Item-level ids (Tabs items, Legend items, GraphView lanes) are `info: HelpId` in the TypeScript
// types, so a missing one is a type error in CI (tsc runs in CI only, see ci-typecheck.mjs).
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";

const ROOT = new URL("..", import.meta.url).pathname;
const SRC = join(ROOT, "src");
const REGISTRY = join(SRC, "help", "registry.ts");
/** per-feature entry files merged into HELP by registry.ts (e.g. entries/v2.ts); parsed as registry */
const ENTRY_DIR = join(SRC, "help", "entries");
const SKIP_DIRS = new Set([join(SRC, "legacy"), join(SRC, "types")]);
/** components whose every use must pass info= (their props also require it in TypeScript) */
export const REQUIRE_INFO = ["Panel", "StatPill", "Tabs", "Legend", "GraphView", "PdfPage", "PdfSplit", "EvidenceCompare", "Viewer3D"];

function walk(dir, out = []) {
  for (const f of readdirSync(dir)) {
    const p = join(dir, f);
    if (SKIP_DIRS.has(p)) continue;
    if (statSync(p).isDirectory()) walk(p, out);
    else if (/\.(tsx?|css)$/.test(f)) out.push(p);
  }
  return out;
}

// ---- registry
const reg = readFileSync(REGISTRY, "utf8");
const entries = new Map(); // id -> entry source
const entryFiles = new Map(); // id -> file it is declared in
const keyRe = /^ {2}"([a-z][a-z0-9-]*(?:\.[a-z0-9-]+)+)":\s*\{/gm;
const errors = [];
function parseEntries(text, start, file) {
  const body = text.slice(text.indexOf(start), text.indexOf("} as const satisfies"));
  const keys = [...body.matchAll(keyRe)];
  keys.forEach((m, i) => {
    if (entries.has(m[1])) errors.push(`registry ${m[1]}: declared twice (${entryFiles.get(m[1])} and ${file})`);
    entries.set(m[1], body.slice(m.index, i + 1 < keys.length ? keys[i + 1].index : body.length));
    entryFiles.set(m[1], file);
  });
}
parseEntries(reg, "export const HELP = {", "registry.ts");
const entryFileList = existsSync(ENTRY_DIR) ? readdirSync(ENTRY_DIR).filter((f) => f.endsWith(".ts")).map((f) => join(ENTRY_DIR, f)) : [];
for (const f of entryFileList) {
  const text = readFileSync(f, "utf8");
  const name = relative(SRC, f);
  if (!new RegExp(`\\.\\.\\.${(text.match(/export const (\w+)/) ?? [])[1]}\\b`).test(reg)) errors.push(`${name}: its export is not spread into HELP in registry.ts`);
  parseEntries(text, "= {", name);
}
const famBlock = reg.match(/export const HELP_FAMILIES[^=]*=\s*\[([^\]]*)\]/);
const families = famBlock ? [...famBlock[1].matchAll(/"([^"]+)"/g)].map((m) => m[1]) : [];

if (!entries.size) errors.push("registry: no entries parsed - did the HELP object format change?");
for (const [id, src] of entries) {
  if (!/title:\s*"[^"]+"/.test(src)) errors.push(`registry ${id}: empty or missing title`);
  if (!/short:\s*"[^"]+"/.test(src)) errors.push(`registry ${id}: empty or missing short`);
  const t = src.match(/terms:\s*\[([^\]]*)\]/);
  if (t) for (const m of t[1].matchAll(/"([^"]+)"/g)) if (!m[1].startsWith("term.") || !entries.has(m[1])) errors.push(`registry ${id}: terms link ${m[1]} is not a term entry`);
}

// ---- usage
const used = new Map(); // id -> first file:line
const usedFamilies = new Set();
const lineOf = (text, idx) => text.slice(0, idx).split("\n").length;
const USE_RES = [
  /<InfoTip\b[^>]*?\bid=\{?\s*["'`]([^"'`]+)["'`]/g,
  /\binfo=\{?\s*["'`]([^"'`]+)["'`]/g,
  /\binfo:\s*["'`]([^"'`]+)["'`]/g,
];

/** opening JSX tags of `name`, brace- and quote-aware, returns [index, tagText] */
function openingTags(text, name) {
  const out = [];
  const re = new RegExp(`<${name}(?=[\\s/>])`, "g");
  let m;
  while ((m = re.exec(text))) {
    let i = m.index + m[0].length, depth = 0, q = null;
    for (; i < text.length; i++) {
      const c = text[i];
      if (q) { if (c === q && text[i - 1] !== "\\") q = null; continue; }
      if (c === '"' || c === "'" || c === "`") q = c;
      else if (c === "{") depth++;
      else if (c === "}") depth--;
      else if (c === ">" && depth === 0) break;
    }
    out.push([m.index, text.slice(m.index, i + 1)]);
  }
  return out;
}

for (const f of walk(SRC)) {
  const text = readFileSync(f, "utf8");
  const rel = relative(ROOT, f);
  if (text.includes("—")) errors.push(`${rel}:${lineOf(text, text.indexOf("—"))}: em dash - use a hyphen`);
  if (f === REGISTRY || f.startsWith(ENTRY_DIR) || f.endsWith(".css")) continue;
  for (const re of USE_RES)
    for (const m of text.matchAll(re)) if (!used.has(m[1])) used.set(m[1], `${rel}:${lineOf(text, m.index)}`);
  for (const m of text.matchAll(/\bhelpFamily\(\s*["'`]([^"'`]+)["'`]/g)) usedFamilies.add(m[1]);
  if (/\.tsx$/.test(f))
    for (const name of REQUIRE_INFO)
      for (const [idx, tag] of openingTags(text, name))
        if (!/\binfo=/.test(tag) && !/\{\s*\.\.\./.test(tag)) errors.push(`${rel}:${lineOf(text, idx)}: <${name}> without info= (every ${name} carries an "i" mark)`);
}

for (const [id, where] of used) if (!entries.has(id)) errors.push(`${where}: help id "${id}" is not in src/help/registry.ts`);
for (const fam of usedFamilies) if (!families.includes(fam)) errors.push(`helpFamily("${fam}") used but "${fam}" is not declared in HELP_FAMILIES`);
for (const id of entries.keys()) {
  const src = entries.get(id);
  if (/kind:\s*"term"/.test(src)) continue;
  if (families.some((fam) => id.startsWith(fam + ".") && usedFamilies.has(fam))) continue;
  if (!used.has(id)) errors.push(`registry entry "${id}" is not used by any component - remove it or use it`);
}

if (errors.length) {
  console.error(`check-help: ${errors.length} problem(s)\n  ` + errors.join("\n  "));
  process.exit(1);
}
console.log(`check-help: ok - ${entries.size} registry entries, ${used.size} ids used, ${families.length} families`);
