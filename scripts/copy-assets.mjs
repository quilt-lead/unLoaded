// Copies runtime assets into public/ (generated, git-ignored):
//   public/wasm/web-ifc.wasm  - web-ifc runtime used by @unloaded/ifc-parser in the browser
// Sample IFC / JSON models live in data/ and are imported manually from there.
// Runs on postinstall / predev / prebuild. Never fails the install.
import { copyFileSync, existsSync, mkdirSync, statSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const require = createRequire(join(repoRoot, "packages/ifc-parser/package.json"));

let wasm;
try {
  wasm = join(dirname(require.resolve("web-ifc/package.json")), "web-ifc.wasm");
} catch {
  wasm = join(repoRoot, "node_modules/web-ifc/web-ifc.wasm");
}

const copies = [
  [wasm, "public/wasm/web-ifc.wasm"],
];

for (const [from, rel] of copies) {
  const to = join(repoRoot, rel);
  if (!existsSync(from)) {
    console.warn(`[assets] missing source: ${from}`);
    continue;
  }
  mkdirSync(dirname(to), { recursive: true });
  if (existsSync(to) && statSync(to).size === statSync(from).size && statSync(to).mtimeMs >= statSync(from).mtimeMs) continue;
  copyFileSync(from, to);
  console.log(`[assets] ${rel}`);
}
