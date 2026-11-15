import { defineConfig } from 'vite';

export default defineConfig({
  server: { port: 5173, proxy: { '/api': 'http://127.0.0.1:8000' } },
  optimizeDeps: { exclude: ['web-ifc'] },
  build: { target: 'es2022', chunkSizeWarningLimit: 2000 },
});
