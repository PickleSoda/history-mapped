import { ChevronLeft } from 'lucide-react';
import { useState } from 'react';
import { BrowseTab } from '@/components/atlas/BrowseTab';
import { ChronicleList } from '@/components/atlas/ChronicleList';
import {
  ChroniclePlayerContent,
} from '@/components/atlas/ChroniclePlayer';
import { DetailPanelContent } from '@/components/atlas/DetailPanel';
import { useChronicleNav, useSelection, useSheetContent } from '@/hooks';
import { cn } from '@/lib/utils';

type Tab = 'entities' | 'chronicles';

/** Detail in the sheet: a back-to-results bar over the shared detail body. */
function SheetDetail() {
  const { clear } = useSelection();
  return (
    <div className="flex h-full flex-col">
      <div className="flex flex-none items-center px-2 py-1.5">
        <button
          type="button"
          onClick={clear}
          className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-[13px] text-muted-foreground hover:bg-muted hover:text-foreground"
        >
          <ChevronLeft size={15} /> Results
        </button>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain">
        <DetailPanelContent />
      </div>
    </div>
  );
}

/** Chronicle tour in the sheet: an exit-tour bar over the shared chronicle body.
 *  (Desktop puts "Exit tour" in the ChroniclePlayer aside wrapper, which the
 *  sheet doesn't mount — without this bar there is no way out on mobile.) */
function SheetChronicle() {
  const { exit } = useChronicleNav();
  return (
    <div className="flex h-full flex-col">
      <div className="flex flex-none items-center px-2 py-1.5">
        <button
          type="button"
          onClick={exit}
          className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-[13px] text-muted-foreground hover:bg-muted hover:text-foreground"
        >
          <ChevronLeft size={15} /> Exit tour
        </button>
      </div>
      <div className="min-h-0 flex-1">
        <ChroniclePlayerContent />
      </div>
    </div>
  );
}

/** List in the sheet: two tabs over the existing browse / chronicle lists. */
function SheetList() {
  const [tab, setTab] = useState<Tab>('entities');
  return (
    <div className="flex h-full flex-col">
      <div className="flex flex-none gap-0.5 rounded-lg bg-muted p-0.5">
        {(['entities', 'chronicles'] as const).map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className={cn(
              'flex-1 rounded-md py-1.5 text-xs font-medium capitalize transition-colors',
              tab === t ? 'bg-card text-foreground shadow-sm' : 'text-muted-foreground',
            )}
          >
            {t}
          </button>
        ))}
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain">
        {tab === 'entities' ? <BrowseTab /> : <ChronicleList />}
      </div>
    </div>
  );
}

/** Sheet body: chronicle tour, entity detail, or the list. */
export function SheetContent() {
  const kind = useSheetContent();
  if (kind === 'chronicle') return <SheetChronicle />;
  if (kind === 'detail') return <SheetDetail />;
  return <SheetList />;
}
