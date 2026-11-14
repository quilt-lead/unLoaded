import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// The React app is index.html (client-side routes, served by FastAPI with an SPA fallback).
// The vanilla pages stay reachable at /legacy/ and /legacy/set.html until the R2 port reaches parity.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { '/api': 'http://127.0.0.1:8000' } },
  optimizeDeps: { exclude: ['web-ifc'] },
  build: {
    target: 'es2022',
    chunkSizeWarningLimit: 2000,
    rollupOptions: {
      input: { app: 'index.html', legacy: 'legacy/index.html', legacySet: 'legacy/set.html' },
    },
  },
});
