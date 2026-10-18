import {
  Check,
  Compass,
  Globe,
  Layers,
  LogIn,
  LogOut,
  MapPin,
  Search,
  SlidersHorizontal,
} from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { accountLinks } from '@/components/account/UserMenu';
import { BASEMAP_IDS } from '@/components/atlas/LayersMenu';
import { ThemeToggle } from '@/components/atlas/ThemeToggle';
import {
  useAuthActions,
  useBasemap,
  useCommandPalette,
  useLoginRedirect,
  useMe,
  useView,
} from '@/hooks';
import { BASEMAPS } from '@/lib/map-config';
import { cn } from '@/lib/utils';

const TOOL_ROW =
  'mt-1 flex w-full items-center gap-2 rounded-md px-2 py-2 text-[13px] text-muted-foreground hover:bg-muted';

/** Mobile header: brand mark · search pill (opens ⌘K palette) · tools menu
 *  (view, layers, and the account links). */
export function MobileTopBar() {
  const { setOpen } = useCommandPalette();
  const { view, setView } = useView();
  const { basemap, setBasemap } = useBasemap();
  const [tools, setTools] = useState(false);
  const { me } = useMe();
  const toLogin = useLoginRedirect();
  const { signOut } = useAuthActions();

  return (
    <header className="relative flex h-[52px] flex-none items-center gap-2 border-b bg-card px-3">
      <span className="grid size-8 flex-none place-items-center rounded-lg bg-primary text-primary-foreground">
        <Compass size={16} />
      </span>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="flex h-9 flex-1 items-center gap-2 rounded-lg border bg-muted/50 px-3 text-[13px] text-muted-foreground"
      >
        <Search size={15} />
        <span className="flex-1 text-left">Search History Mapped…</span>
      </button>
      <ThemeToggle className="flex-none border bg-card" />
      <button
        type="button"
        onClick={() => setTools((v) => !v)}
        aria-label="Tools"
        aria-expanded={tools}
        className="grid size-9 flex-none place-items-center rounded-lg border bg-card text-muted-foreground"
      >
        <SlidersHorizontal size={16} />
      </button>

      {tools && (
        <div className="absolute right-3 top-[54px] z-30 w-52 rounded-xl border bg-popover p-1.5 shadow-lg">
          <div className="flex gap-0.5 rounded-lg bg-muted p-0.5">
            {([['map', 'Map', MapPin], ['globe', 'Globe', Globe]] as const).map(
              ([v, label, Icon]) => (
                <button
                  key={v}
                  type="button"
                  onClick={() => {
                    setView(v);
                    setTools(false);
                  }}
                  className={cn(
                    'inline-flex flex-1 items-center justify-center gap-1.5 rounded-md py-1.5 text-xs font-medium',
                    view === v ? 'bg-card text-foreground shadow-sm' : 'text-muted-foreground',
                  )}
                >
                  <Icon size={14} /> {label}
                </button>
              ),
            )}
          </div>
          <p className="flex items-center gap-2 px-2 pb-0.5 pt-2.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
            <Layers size={13} /> Basemap
          </p>
          {BASEMAP_IDS.map((id) => (
            <button
              key={id}
              type="button"
              aria-pressed={basemap === id}
              onClick={() => {
                setBasemap(id);
                setTools(false);
              }}
              className={cn(TOOL_ROW, 'mt-0', basemap === id && 'text-foreground')}
            >
              <Check size={15} className={cn(basemap !== id && 'invisible')} />
              {BASEMAPS[id].label}
            </button>
          ))}

          <div className="-mx-1.5 my-1 h-px bg-border" />
          {me ? (
            <>
              <p className="truncate px-2 pt-1 text-[12px] font-medium">{me.name}</p>
              {accountLinks(me).map((l) =>
                'to' in l ? (
                  <Link key={l.label} to={l.to} className={TOOL_ROW} onClick={() => setTools(false)}>
                    <l.icon size={15} /> {l.label}
                  </Link>
                ) : (
                  <a key={l.label} href={l.href} className={TOOL_ROW}>
                    <l.icon size={15} /> {l.label}
                  </a>
                ),
              )}
              <button
                type="button"
                className={TOOL_ROW}
                onClick={() => signOut.mutate(undefined, { onSuccess: () => setTools(false) })}
              >
                <LogOut size={15} /> Sign out
              </button>
            </>
          ) : (
            <button type="button" className={TOOL_ROW} onClick={toLogin}>
              <LogIn size={15} /> Sign in
            </button>
          )}
        </div>
      )}
    </header>
  );
}
