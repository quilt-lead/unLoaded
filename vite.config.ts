import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Frontend only: no server. web-ifc.wasm and the samples are served from public/ (copied by
// scripts/copy-assets.mjs). The calc engine (@unloaded/calc-mapper) runs in a module Web Worker
// (src/engine/engine.worker.ts), so workers are built as ES modules.
export default defineConfig({
  plugins: [react()],
  // web-ifc locates its wasm at runtime; keep it out of dep prebundling.
  optimizeDeps: { exclude: ['web-ifc'] },
  server: { port: 5173, open: true },
  worker: { format: 'es' },
  // web-ifc is lazy-loaded as its own ~3 MB chunk; pdf.js and three are large too.
  build: { target: 'es2022', chunkSizeWarningLimit: 4000 },
});
