import { createContext, useContext, useState } from 'react';
import type { ReactNode } from 'react';

/**
 * Shared open-state for the right-docked AI panel.
 *
 * The panel is non-blocking: when open it docks on the right and the main
 * content is inset (pushed left) rather than covered by a modal overlay — so
 * the operator can keep reading the entity/chronicle while chatting. The
 * provider wraps the nav (which has the "Ask AI" trigger), the main content
 * (which insets), and the panel itself, so all three share one open flag.
 *
 * Keep AI_PANEL_WIDTH in sync with the panel width and the content inset class
 * (`md:mr-[440px]`) in app-content.tsx and ai-sidebar.tsx.
 */
export const AI_PANEL_WIDTH = 440;

type AiPanelContextValue = {
    open: boolean;
    setOpen: (open: boolean) => void;
};

const AiPanelContext = createContext<AiPanelContextValue>({
    open: false,
    setOpen: () => {},
});

export function AiPanelProvider({ children }: { children: ReactNode }) {
    const [open, setOpen] = useState(false);

    return (
        <AiPanelContext.Provider value={{ open, setOpen }}>
            {children}
        </AiPanelContext.Provider>
    );
}

/** Safe to call without a provider — returns a closed, no-op default. */
export function useAiPanel(): AiPanelContextValue {
    return useContext(AiPanelContext);
}
