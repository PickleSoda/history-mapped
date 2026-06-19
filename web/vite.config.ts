import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath, URL } from 'node:url';
import { defineConfig, transformWithEsbuild, type Plugin } from 'vite';

/**
 * @timescope/react alpha ships JSX in its bundled ESM .js output.
 * Rollup's commonjs scanner chokes on the raw `<div` before the react plugin
 * can transpile it. This micro-plugin runs first (enforce:'pre') and strips JSX
 * via Vite's built-in esbuild transform so rollup sees plain JS.
 */
function timescopeJsxPlugin(): Plugin {
  return {
    name: 'timescope-jsx',
    enforce: 'pre',
    async transform(code, id) {
      if (!id.includes('@timescope/react')) return null;
      return transformWithEsbuild(code, id, {
        loader: 'jsx',
        jsx: 'automatic',
        target: 'es2022',
      });
    },
  };
}

export default defineConfig({
  plugins: [timescopeJsxPlugin(), react(), tailwindcss()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  optimizeDeps: {
    include: ['@timescope/react', 'timescope', '@kikuchan/decimal'],
    esbuildOptions: {
      loader: { '.js': 'jsx' },
    },
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
    hmr: {
      host: 'localhost',
      port: 5173,
    },
    watch: {
      usePolling: true,
    },
  },
});
