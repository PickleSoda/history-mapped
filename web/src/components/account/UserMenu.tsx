import { Menu } from '@base-ui/react/menu';
import { Bookmark, LayoutDashboard, LogIn, LogOut, PencilLine } from 'lucide-react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuthActions, useLoginRedirect, useMe } from '@/hooks';
import type { Me } from '@/lib/schemas/auth';
import { cn } from '@/lib/utils';
import { MENU_ITEM, POPUP } from './styles';

/** The user's initial on a round chip. */
export function Avatar({ me, className }: { me: Me; className?: string }) {
  return (
    <span
      aria-hidden
      className={cn(
        'grid size-8 place-items-center rounded-full bg-foreground font-heading text-[14px] font-semibold text-background',
        className,
      )}
    >
      {(me.name.trim()[0] ?? me.email[0] ?? '?').toUpperCase()}
    </span>
  );
}

/** Account links shared by the desktop menu and the mobile tools menu. */
export function accountLinks(me: Me) {
  return [
    { to: '/saved', label: 'Saved', icon: Bookmark },
    { to: '/contributions', label: 'My contributions', icon: PencilLine },
    ...(me.can.access_admin && me.admin_url
      ? [{ href: me.admin_url, label: 'Admin panel', icon: LayoutDashboard }]
      : []),
  ] as const;
}

/**
 * Top-bar account control: "Sign in" for guests; for a signed-in user, their
 * initial opening a menu (saved, contributions, admin, sign out).
 */
export function UserMenu() {
  const { me, isLoading } = useMe();
  const toLogin = useLoginRedirect();
  const { signOut } = useAuthActions();
  const navigate = useNavigate();
  const { pathname } = useLocation();

  if (isLoading) return <span aria-hidden className="size-8 rounded-full bg-muted" />;

  if (!me) {
    return (
      <button
        type="button"
        onClick={toLogin}
        className="inline-flex h-8 items-center gap-1.5 rounded-lg border bg-card px-2.5 text-[12px] font-medium text-foreground transition-colors hover:bg-muted"
      >
        <LogIn size={14} /> Sign in
      </button>
    );
  }

  return (
    <Menu.Root>
      <Menu.Trigger
        aria-label={`Account: ${me.name}`}
        className="rounded-full outline-none ring-offset-2 ring-offset-card transition-shadow focus-visible:ring-2 focus-visible:ring-ring data-[popup-open]:ring-2 data-[popup-open]:ring-border"
      >
        <Avatar me={me} />
      </Menu.Trigger>
      <Menu.Portal>
        <Menu.Positioner sideOffset={8} align="end" className="z-50">
          <Menu.Popup className={cn(POPUP, 'w-56')}>
            <div className="px-2 pb-2 pt-1.5">
              <p className="truncate text-[13px] font-medium">{me.name}</p>
              <p className="truncate text-[11px] text-muted-foreground">{me.email}</p>
            </div>
            <Menu.Separator className="-mx-1.5 my-1 h-px bg-border" />
            {accountLinks(me).map((l) =>
              'to' in l ? (
                <Menu.LinkItem key={l.label} render={<Link to={l.to} />} className={MENU_ITEM}>
                  <l.icon size={15} className="text-muted-foreground" /> {l.label}
                </Menu.LinkItem>
              ) : (
                <Menu.LinkItem key={l.label} href={l.href} className={MENU_ITEM}>
                  <l.icon size={15} className="text-muted-foreground" /> {l.label}
                </Menu.LinkItem>
              ),
            )}
            <Menu.Separator className="-mx-1.5 my-1 h-px bg-border" />
            <Menu.Item
              className={MENU_ITEM}
              // Leave the account pages (they need a user); the atlas stays put.
              onClick={() =>
                signOut.mutate(undefined, { onSuccess: () => pathname !== '/' && navigate('/') })
              }
            >
              <LogOut size={15} className="text-muted-foreground" /> Sign out
            </Menu.Item>
          </Menu.Popup>
        </Menu.Positioner>
      </Menu.Portal>
    </Menu.Root>
  );
}
