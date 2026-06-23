import { List, PanelLeftClose, ScrollText } from 'lucide-react';
import { useState } from 'react';
import { cn } from '@/lib/utils';
import { BrowseTab } from './BrowseTab';
import { ChronicleList } from './ChronicleList';
import { NavBreadcrumb } from './NavBreadcrumb';

type Tab = 'entities' | 'chronicles';

function TabButton({
  active,
  onClick,
  icon: Icon,
  children,
}: {
  active: boolean;
  onClick: () => void;
  icon: typeof List;
  children: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'inline-flex flex-1 items-center justify-center gap-1.5 rounded-md py-1.5 text-xs font-medium transition-colors',
        active
          ? 'bg-card text-foreground shadow-sm'
          : 'text-muted-foreground hover:text-foreground',
      )}
    >
      <Icon size={14} /> {children}
    </button>
  );
}

function RailIcon({
  active,
  onClick,
  icon: Icon,
  label,
}: {
  active: boolean;
  onClick: () => void;
  icon: typeof List;
  label: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={label}
      aria-label={label}
      className={cn(
        'grid size-9 place-items-center rounded-lg transition-colors',
        active
          ? 'bg-muted text-foreground'
          : 'text-muted-foreground hover:bg-muted hover:text-foreground',
      )}
    >
      <Icon size={18} />
    </button>
  );
}

/**
 * Left sidebar: two tabs (Entities / Chronicles) when expanded; a slim rail with
 * the two tab icons when collapsed. Collapsing shrinks (never disappears) — and
 * clicking a rail icon expands straight into that tab.
 */
export function LeftSidebar() {
  const [collapsed, setCollapsed] = useState(false);
  const [tab, setTab] = useState<Tab>('entities');

  const openTab = (t: Tab) => {
    setTab(t);
    setCollapsed(false);
  };

  return (
    <aside
      className={cn(
        'flex h-full flex-none flex-col border-r bg-card transition-[width] duration-200',
        collapsed ? 'w-[52px]' : 'w-[340px] max-w-[85vw]',
      )}
    >
      {collapsed ? (
        <div className="flex flex-col items-center gap-1.5 py-2.5">
          <RailIcon
            active={tab === 'entities'}
            onClick={() => openTab('entities')}
            icon={List}
            label="Entities"
          />
          <RailIcon
            active={tab === 'chronicles'}
            onClick={() => openTab('chronicles')}
            icon={ScrollText}
            label="Chronicles"
          />
        </div>
      ) : (
        <>
          <NavBreadcrumb className="flex-none" />
          <div className="flex items-center gap-2 border-b px-3 py-2">
            <div className="flex flex-1 gap-0.5 rounded-lg bg-muted p-0.5">
              <TabButton
                active={tab === 'entities'}
                onClick={() => setTab('entities')}
                icon={List}
              >
                Entities
              </TabButton>
              <TabButton
                active={tab === 'chronicles'}
                onClick={() => setTab('chronicles')}
                icon={ScrollText}
              >
                Chronicles
              </TabButton>
            </div>
            <button
              type="button"
              onClick={() => setCollapsed(true)}
              className="grid size-8 flex-none place-items-center rounded-md text-muted-foreground hover:bg-muted"
              aria-label="Collapse sidebar"
            >
              <PanelLeftClose size={16} />
            </button>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto">
            {tab === 'entities' ? <BrowseTab /> : <ChronicleList />}
          </div>
        </>
      )}
    </aside>
  );
}
