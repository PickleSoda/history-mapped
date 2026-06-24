import * as React from 'react';
import { useAiPanel } from '@/components/ai/ai-panel-context';
import { SidebarInset } from '@/components/ui/sidebar';
import { cn } from '@/lib/utils';
import type { AppVariant } from '@/types';

type Props = React.ComponentProps<'main'> & {
    variant?: AppVariant;
};

export function AppContent({
    variant = 'sidebar',
    children,
    className,
    ...props
}: Props) {
    // When the AI panel is docked open, push the content left (md+ only) so the
    // two sit side-by-side rather than the panel covering the page. Safe-default
    // hook → no effect in layouts without an AiPanelProvider (e.g. header).
    const { open: aiOpen } = useAiPanel();

    if (variant === 'sidebar') {
        return (
            <SidebarInset
                className={cn(
                    'transition-[margin] duration-200 ease-in-out',
                    aiOpen && 'md:mr-110',
                    className,
                )}
                {...props}
            >
                {children}
            </SidebarInset>
        );
    }

    return (
        <main
            className={cn(
                'mx-auto flex h-full w-full max-w-7xl flex-1 flex-col gap-4 rounded-xl',
                className,
            )}
            {...props}
        >
            {children}
        </main>
    );
}
