import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// The calc engine (backend/, FastAPI) serves /api on :8000; the dev server proxies to it
// (override with CALCGRAPH_API). web-ifc.wasm is served from public/wasm/ (copied by
// scripts/copy-assets.mjs) and used by both the IFC parser (src/loaders/parsers.ts) and the
// 3D viewer (src/components/three/ifcViewer.ts).
export default defineConfig({
  plugins: [react()],
  // web-ifc locates its wasm at runtime; keep it out of dep prebundling.
  optimizeDeps: { exclude: ['web-ifc'] },
  server: {
    port: 5173,
    open: true,
    proxy: { '/api': process.env.CALCGRAPH_API ?? 'http://127.0.0.1:8000' },
  },
  // web-ifc is lazy-loaded as its own ~3 MB chunk; pdf.js and three are large too.
  build: { target: 'es2022', chunkSizeWarningLimit: 4000 },
});
