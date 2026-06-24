import { useEffect, useRef } from 'react';

/**
 * Cross-component signal that an AI proposal part was applied.
 *
 * The entity page mixes Inertia-prop-backed data (refreshed by
 * `router.reload()`) with panels that fetch and hold their own state
 * (geometry periods, relationships, timeline). Those self-fetching panels
 * key their initial load on a URL that never changes, so a prop reload does
 * not refresh them. After an apply we emit this event; each self-fetching
 * panel listens and re-fetches so the change shows immediately.
 */
export const AI_APPLIED_EVENT = 'ai:applied';

/** Notify listening panels that data changed and they should re-fetch. */
export function emitAiApplied(): void {
    if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent(AI_APPLIED_EVENT));
    }
}

/**
 * Subscribe a panel's re-fetch to apply events. The handler is held in a ref
 * so its identity need not be stable — the latest closure always runs.
 */
export function useAiApplied(handler: () => void): void {
    const handlerRef = useRef(handler);

    // Keep the ref pointed at the latest closure without re-subscribing.
    useEffect(() => {
        handlerRef.current = handler;
    });

    useEffect(() => {
        const listener = () => handlerRef.current();

        window.addEventListener(AI_APPLIED_EVENT, listener);

        return () => window.removeEventListener(AI_APPLIED_EVENT, listener);
    }, []);
}
