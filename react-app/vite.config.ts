import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Vite configuration for the demo React app.  This config enables the
// React plugin for automatic JSX transform, integrates TypeScript,
// and instructs Vite to output ES modules.  Tailwind CSS is
// processed via PostCSS (see postcss.config.js) and imported in
// ``src/index.css``.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
  },
});