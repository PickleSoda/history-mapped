import { Link } from '@inertiajs/react';
import {
    BookOpen,
    CalendarDays,
    Clock,
    FolderGit2,
    Globe,
    LayoutGrid,
    Library,
    Ruler,
    ScrollText,
    TreePine,
    Languages,
    BookMarked,
    MapPin,
} from 'lucide-react';
import AppLogo from '@/components/app-logo';
import { NavFooter } from '@/components/nav-footer';
import { NavMain } from '@/components/nav-main';
import { NavUser } from '@/components/nav-user';
import {
    Sidebar,
    SidebarContent,
    SidebarFooter,
    SidebarHeader,
    SidebarMenu,
    SidebarMenuButton,
    SidebarMenuItem,
} from '@/components/ui/sidebar';
import { dashboard } from '@/routes';
import { index as calendarSystemsIndex } from '@/routes/reference/calendar-systems';
import { index as eraDateLookupIndex } from '@/routes/reference/era-date-lookup';
import { index as geographicRegionsIndex } from '@/routes/reference/geographic-regions';
import { index as historicalPeriodsIndex } from '@/routes/reference/historical-periods';
import { index as historiographicalSchoolsIndex } from '@/routes/reference/historiographical-schools';
import { index as languageFamiliesIndex } from '@/routes/reference/language-families';
import { index as measurementUnitsIndex } from '@/routes/reference/measurement-units';
import { index as religiousTraditionsIndex } from '@/routes/reference/religious-traditions';
import { index as sourceTypeDefinitionsIndex } from '@/routes/reference/source-type-definitions';
import { index as writingSystemsIndex } from '@/routes/reference/writing-systems';
import type { NavItem } from '@/types';

const mainNavItems: NavItem[] = [
    {
        title: 'Dashboard',
        href: dashboard(),
        icon: LayoutGrid,
    },
    {
        title: 'Entities',
        href: '/entities',
        icon: Globe,
    },
];

const referenceNavItems: NavItem[] = [
    {
        title: 'Geographic Regions',
        href: geographicRegionsIndex.url(),
        icon: MapPin,
    },
    {
        title: 'Historical Periods',
        href: historicalPeriodsIndex.url(),
        icon: Clock,
    },
    {
        title: 'Historiographical Schools',
        href: historiographicalSchoolsIndex.url(),
        icon: Library,
    },
    {
        title: 'Calendar Systems',
        href: calendarSystemsIndex.url(),
        icon: CalendarDays,
    },
    {
        title: 'Era Date Lookup',
        href: eraDateLookupIndex.url(),
        icon: ScrollText,
    },
    {
        title: 'Writing Systems',
        href: writingSystemsIndex.url(),
        icon: BookMarked,
    },
    {
        title: 'Religious Traditions',
        href: religiousTraditionsIndex.url(),
        icon: TreePine,
    },
    {
        title: 'Measurement Units',
        href: measurementUnitsIndex.url(),
        icon: Ruler,
    },
    {
        title: 'Language Families',
        href: languageFamiliesIndex.url(),
        icon: Languages,
    },
    {
        title: 'Source Type Definitions',
        href: sourceTypeDefinitionsIndex.url(),
        icon: BookOpen,
    },
];

const footerNavItems: NavItem[] = [
    {
        title: 'Repository',
        href: 'https://github.com/laravel/react-starter-kit',
        icon: FolderGit2,
    },
    {
        title: 'Documentation',
        href: 'https://laravel.com/docs/starter-kits#react',
        icon: BookOpen,
    },
];

export function AppSidebar() {
    return (
        <Sidebar collapsible="icon" variant="inset">
            <SidebarHeader>
                <SidebarMenu>
                    <SidebarMenuItem>
                        <SidebarMenuButton size="lg" asChild>
                            <Link href={dashboard()} prefetch>
                                <AppLogo />
                            </Link>
                        </SidebarMenuButton>
                    </SidebarMenuItem>
                </SidebarMenu>
            </SidebarHeader>

            <SidebarContent>
                <NavMain items={mainNavItems} />
                <NavMain items={referenceNavItems} label="Reference Data" />
            </SidebarContent>

            <SidebarFooter>
                <NavFooter items={footerNavItems} className="mt-auto" />
                <NavUser />
            </SidebarFooter>
        </Sidebar>
    );
}
