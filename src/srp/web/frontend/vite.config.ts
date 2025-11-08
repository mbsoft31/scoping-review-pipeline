import { defineConfig } from 'vite';

// Vite configuration for the SRP frontend.  This builds the TypeScript
// sources under `src/` and outputs bundled JavaScript to the
// `static/dist` directory of the Python web application.  The
// `outDir` is relative to this config file; two directories up
// places the build output in `src/srp/web/static/dist`.

export default defineConfig({
  root: __dirname + '/src',
  build: {
    outDir: '../../static/dist',
    emptyOutDir: true,
    rollupOptions: {
      input: {
        main: __dirname + '/src/main.ts',
      },
    },
  },
});