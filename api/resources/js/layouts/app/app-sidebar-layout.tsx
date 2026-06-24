import { AiPanelProvider } from '@/components/ai/ai-panel-context';
import { AiSidebar } from '@/components/ai/ai-sidebar';
import { AppContent } from '@/components/app-content';
import { AppShell } from '@/components/app-shell';
import { AppSidebar } from '@/components/app-sidebar';
import { AppSidebarHeader } from '@/components/app-sidebar-header';
import type { AppLayoutProps } from '@/types';

export default function AppSidebarLayout({
    children,
    breadcrumbs = [],
}: AppLayoutProps) {
    return (
        <AppShell variant="sidebar">
            {/* AiPanelProvider shares the open flag between the nav trigger, the
                content inset (push), and the docked panel below. */}
            <AiPanelProvider>
                <AppSidebar />
                <AppContent variant="sidebar" className="overflow-x-hidden">
                    <AppSidebarHeader breadcrumbs={breadcrumbs} />
                    {children}
                </AppContent>
                <AiSidebar />
            </AiPanelProvider>
        </AppShell>
    );
}
