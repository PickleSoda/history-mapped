import js from '@eslint/js';
import importPlugin from 'eslint-plugin-import';
import react from 'eslint-plugin-react';
import reactHooks from 'eslint-plugin-react-hooks';
import globals from 'globals';
import typescript from 'typescript-eslint';

/** @type {import('eslint').Linter.Config[]} */
export default [
  js.configs.recommended,
  reactHooks.configs.flat['recommended-latest'],
  ...typescript.configs.recommended,
  {
    ...react.configs.flat.recommended,
    ...react.configs.flat['jsx-runtime'], // React 17+ automatic runtime
    languageOptions: {
      globals: {
        ...globals.browser,
      },
    },
    settings: {
      react: {
        version: 'detect',
      },
    },
    rules: {
      'react/react-in-jsx-scope': 'off',
      'react/prop-types': 'off',
      // Resetting a transient index from an effect is a benign, common pattern;
      // keep it visible as a warning rather than failing the build.
      'react-hooks/set-state-in-effect': 'warn',
    },
  },
  {
    plugins: {
      import: importPlugin,
    },
    settings: {
      // Classify the `@/` alias as "internal" by path, not by module resolution,
      // so import-order stays deterministic regardless of resolver state.
      'import/internal-regex': '^@/',
      'import/resolver': {
        typescript: {
          alwaysTryTypes: true,
          project: './tsconfig.app.json',
        },
        node: true,
      },
    },
    rules: {
      '@typescript-eslint/no-explicit-any': 'off',
      '@typescript-eslint/consistent-type-imports': [
        'error',
        {
          prefer: 'type-imports',
          fixStyle: 'separate-type-imports',
        },
      ],
      'import/order': [
        'error',
        {
          groups: [
            'builtin',
            'external',
            'internal',
            'parent',
            'sibling',
            'index',
          ],
          alphabetize: {
            order: 'asc',
            caseInsensitive: true,
          },
        },
      ],
      'import/consistent-type-specifier-style': ['error', 'prefer-top-level'],
    },
  },
  {
    ignores: ['dist', 'node_modules', 'public', 'vite.config.ts'],
  },
];
