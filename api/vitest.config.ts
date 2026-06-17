import { fileURLToPath, URL } from 'node:url';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';

// Dedicated test config, kept separate from vite.config.ts on purpose.
//
// vite.config.ts loads the Laravel + Wayfinder plugins for the asset pipeline.
// The Laravel plugin aborts when it detects CI ("you should not run the Vite
// HMR server in CI environments"), which breaks `vitest` since it resolves the
// Vite config on startup. Tests don't need the asset pipeline — only JSX
// transform and the `@` -> resources/js alias the Laravel plugin would provide.
//
// Test environment is set per-file via `// @vitest-environment jsdom`, and the
// vitest globals (describe/it/expect/vi) are imported explicitly, so no extra
// `test` config is required here.
export default defineConfig({
    plugins: [react()],
    resolve: {
        alias: {
            '@': fileURLToPath(new URL('./resources/js', import.meta.url)),
        },
    },
});
