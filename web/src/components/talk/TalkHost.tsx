import { createContext, useContext } from 'react';
import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { useLoginRedirect, useMe } from '@/hooks';
import { talkPath } from '@/lib/site-links';
import { TalkConversation } from './TalkConversation';
import type { TalkVariant } from './TalkConversation';

const TalkHostContext = createContext(false);

/** Mounted by the atlas shells: tells a TalkButton below it that the chat can
 *  open in place (docked window or sheet) instead of on the /talk page. */
export function TalkHostProvider({ children }: { children: ReactNode }) {
  return <TalkHostContext.Provider value>{children}</TalkHostContext.Provider>;
}

/** True when rendered inside an atlas shell. */
export function useTalkHost(): boolean {
  return useContext(TalkHostContext);
}

/**
 * The chat itself for the dock and the sheet. A guest gets a short note and a
 * sign-in link that comes back to this very atlas URL (read live: the atlas
 * updates the query without the router seeing it).
 */
export function TalkPane({ entityId, name, variant }: { entityId: string; name: string; variant: Exclude<TalkVariant, 'page'> }) {
  const { me, isLoading } = useMe();
  const login = useLoginRedirect();
  if (isLoading) return <div className="grid flex-1 place-items-center text-[13px] text-muted-foreground">Loading…</div>;
  if (!me) {
    const first = name.split(/[\s,]/)[0];
    const next = encodeURIComponent(`${window.location.pathname}${window.location.search}`);
    return (
      <div className="grid flex-1 place-items-center px-6 text-center">
        <div className="max-w-xs">
          <p className="font-heading text-[16px] font-semibold">Sign in to talk with {first}</p>
          <p className="mt-1.5 text-[13px] text-muted-foreground">
            Conversations are kept in your account. {first}&rsquo;s answers are an AI role-play built from the atlas.
          </p>
          <Link
            to={`/login?next=${next}`}
            onClick={(e) => {
              e.preventDefault();
              login();
            }}
            className="mt-4 inline-flex h-8 items-center rounded-lg bg-primary px-3 text-[12px] font-medium text-primary-foreground hover:bg-primary/85"
          >
            Sign in
          </Link>
          <p className="mt-3 text-[12px]">
            <Link to={talkPath()} className="text-muted-foreground underline-offset-2 hover:text-foreground hover:underline">
              All conversations
            </Link>
          </p>
        </div>
      </div>
    );
  }
  return <TalkConversation key={entityId} entityId={entityId} variant={variant} />;
}
