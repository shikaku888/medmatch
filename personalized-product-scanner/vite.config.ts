import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import {defineConfig} from 'vite';

export default defineConfig(() => {
  return {
    // SCANNER_BASE=/scanner/ bakes absolute asset URLs for hosting inside the
    // MedMatch FastAPI static dir; standalone dev keeps the default '/'.
    base: process.env.SCANNER_BASE || '/',
    build: {
      outDir: process.env.SCANNER_OUT || 'dist',
      chunkSizeWarningLimit: 1600,
    },
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, '.'),
      },
    },
    server: {
      // Keep the React dev server pointed at the single FastAPI runtime.
      proxy: {
        '/api': {
          target: process.env.API_PROXY_TARGET || 'http://127.0.0.1:8765',
          changeOrigin: true,
        },
      },
      // HMR is disabled in AI Studio via DISABLE_HMR env var.
      // Do not modifyâfile watching is disabled to prevent flickering during agent edits.
      hmr: process.env.DISABLE_HMR !== 'true',
      // Disable file watching when DISABLE_HMR is true to save CPU during agent edits.
      watch: process.env.DISABLE_HMR === 'true' ? null : {ignored: ['**/data_storage.json']},
    },
  };
});
