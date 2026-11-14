import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// The backend (backend/, FastAPI) serves /api on :8000; the dev server proxies to it.
// web-ifc ships wasm that Vite must not pre-bundle; scripts/copy-wasm.mjs puts it in public/wasm.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    open: true,
    proxy: { '/api': process.env.CALCGRAPH_API ?? 'http://127.0.0.1:8000' },
  },
  optimizeDeps: { exclude: ['web-ifc'] },
  build: { target: 'es2022', chunkSizeWarningLimit: 2000 },
});
