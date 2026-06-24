import { Sparkles } from 'lucide-react';
import { useAiPanel } from '@/components/ai/ai-panel-context';
import { Breadcrumbs } from '@/components/breadcrumbs';
import { Button } from '@/components/ui/button';
import { SidebarTrigger } from '@/components/ui/sidebar';
import type { BreadcrumbItem as BreadcrumbItemType } from '@/types';

export function AppSidebarHeader({
    breadcrumbs = [],
}: {
    breadcrumbs?: BreadcrumbItemType[];
}) {
    const { setOpen: setAiOpen } = useAiPanel();

    return (
        <header className="flex h-16 shrink-0 items-center gap-2 border-b border-sidebar-border/50 px-6 transition-[width,height] ease-linear group-has-data-[collapsible=icon]/sidebar-wrapper:h-12 md:px-4">
            <div className="flex items-center gap-2">
                <SidebarTrigger className="-ml-1" />
                <Breadcrumbs breadcrumbs={breadcrumbs} />
            </div>

            {/* Opposite the breadcrumb — opens the AI assistant panel. */}
            <Button
                variant="outline"
                size="sm"
                className="ml-auto gap-2"
                onClick={() => setAiOpen(true)}
                title="Open AI assistant"
            >
                <Sparkles className="size-4 shrink-0 text-primary" />
                <span className="hidden sm:inline">Ask AI</span>
            </Button>
        </header>
    );
}
