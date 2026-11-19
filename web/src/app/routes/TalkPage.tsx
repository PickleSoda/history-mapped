import { MessageCircle } from 'lucide-react';
import { Suspense } from 'react';
import { Outlet, useParams } from 'react-router-dom';
import { TalkConversation } from '@/components/talk/TalkConversation';
import { TalkSidebar } from '@/components/talk/TalkSidebar';
import { useDocumentMeta } from '@/hooks';
import { cn } from '@/lib/utils';
import { AccountHeader, PageFallback, RequireUser } from './AccountLayout';

/** Chrome of the chat: the account header over a full-height pane (no page scroll). */
export function TalkLayout() {
  return (
    <div className="flex h-dvh flex-col bg-background text-foreground">
      <AccountHeader />
      <main className="min-h-0 flex-1">
        <Suspense fallback={<PageFallback />}>
          <Outlet />
        </Suspense>
      </main>
    </div>
  );
}

/**
 * `/talk` and `/talk/:entityId`. Wide screens show the list of people on the
 * left and the conversation on the right; a phone shows one at a time (the
 * list at `/talk`, the chat at `/talk/:entityId`).
 */
export function TalkPage() {
  const { entityId } = useParams();
  useDocumentMeta({ title: 'Talk with people', description: 'Talk with historical figures, in character, from what the atlas knows of them.' });

  return (
    <RequireUser>
      <div className="mx-auto grid h-full w-full max-w-[1240px] md:grid-cols-[320px_minmax(0,1fr)] md:border-x">
        <aside className={cn('min-h-0 border-r bg-card/40', entityId ? 'hidden md:block' : 'block')}>
          <TalkSidebar activeId={entityId} />
        </aside>
        <section className={cn('min-h-0 flex-col', entityId ? 'flex' : 'hidden md:flex')}>
          {entityId ? (
            <TalkConversation key={entityId} entityId={entityId} />
          ) : (
            <div className="grid flex-1 place-items-center px-6 text-center text-muted-foreground">
              <div className="max-w-xs">
                <MessageCircle size={28} className="mx-auto mb-3" />
                <p className="font-heading text-[18px] font-semibold text-foreground">Pick someone to talk with</p>
                <p className="mt-1 text-[13px]">
                  Choose a person on the left, or open one in the atlas and press <b>Talk</b>. Their answers are an AI role-play built
                  from the atlas, not real quotations.
                </p>
              </div>
            </div>
          )}
        </section>
      </div>
    </RequireUser>
  );
}
