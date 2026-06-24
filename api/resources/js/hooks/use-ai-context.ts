import { usePage } from '@inertiajs/react';

export type AiContext = { type: 'entity' | 'chronicle'; id: string };

/**
 * Reads the `ai_context` prop injected by the server (Task 10) from Inertia
 * page props. Returns a validated context object, or null if the current page
 * has no AI-editable context (or the prop is malformed / an unknown type).
 */
export function useAiContext(): AiContext | null {
    const ctx = (
        usePage().props as { ai_context?: { type?: unknown; id?: unknown } }
    ).ai_context;

    if (
        !ctx ||
        typeof ctx.id !== 'string' ||
        (ctx.type !== 'entity' && ctx.type !== 'chronicle')
    ) {
        return null;
    }

    return { type: ctx.type, id: ctx.id };
}
