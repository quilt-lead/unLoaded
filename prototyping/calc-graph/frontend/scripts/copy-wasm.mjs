// Copy web-ifc's wasm into public/wasm so Vite serves it at /wasm/ (dev and build).
import { copyFileSync, mkdirSync, readdirSync } from 'node:fs';
const src = new URL('../node_modules/web-ifc/', import.meta.url);
const dst = new URL('../public/wasm/', import.meta.url);
mkdirSync(dst, { recursive: true });
for (const f of readdirSync(src)) if (f.endsWith('.wasm')) copyFileSync(new URL(f, src), new URL(f, dst));
console.log('web-ifc wasm copied to public/wasm');
