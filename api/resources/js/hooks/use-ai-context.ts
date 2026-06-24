import { usePage } from '@inertiajs/react';

export type AiContext = { type: 'entity' | 'chronicle'; id: string };

/**
 * Reads the `ai_context` prop injected by the server (Task 10) from Inertia
 * page props. Returns the context object or null if the current page has no
 * AI-editable context.
 */
export function useAiContext(): AiContext | null {
    const props = usePage().props as { ai_context?: AiContext };

    return props.ai_context ?? null;
}
