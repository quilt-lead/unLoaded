import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// web-ifc.wasm is served from public/wasm/ (copied by scripts/copy-assets.mjs)
// and passed to parseIfc as `wasmPath` (see src/loaders/parsers.ts).
export default defineConfig({
  plugins: [react()],
  // web-ifc locates its wasm at runtime; keep it out of dep prebundling.
  optimizeDeps: { exclude: ['web-ifc'] },
  server: { port: 5173, open: true },
  // web-ifc is lazy-loaded as its own ~3 MB chunk, only when an .ifc is opened.
  build: { chunkSizeWarningLimit: 4000 },
});
