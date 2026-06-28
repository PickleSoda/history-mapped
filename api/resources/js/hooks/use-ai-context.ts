import { usePage } from '@inertiajs/react';

export type AiContext = {
    type: 'entity' | 'chronicle';
    id: string | null;
    mode: 'edit' | 'create';
};

/**
 * Reads the `ai_context` prop injected by the server (Task 10) from Inertia
 * page props. Returns a validated context object, or null if the current page
 * has no AI-editable context (or the prop is malformed / an unknown type).
 *
 * Create-mode pages emit `{type, id: null, mode: 'create'}`. Edit/detail pages
 * emit `{type, id: string}` without a mode field; mode defaults to `'edit'`.
 */
export function useAiContext(): AiContext | null {
    const ctx = (
        usePage().props as {
            ai_context?: { type?: unknown; id?: unknown; mode?: unknown };
        }
    ).ai_context;

    if (!ctx || (ctx.type !== 'entity' && ctx.type !== 'chronicle')) {
        return null;
    }

    const mode = ctx.mode === 'create' ? 'create' : 'edit';

    if (mode === 'edit' && typeof ctx.id !== 'string') {
        return null;
    }

    return {
        type: ctx.type,
        id: typeof ctx.id === 'string' ? ctx.id : null,
        mode,
    };
}
