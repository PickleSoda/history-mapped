import { ChevronDown, ChevronUp, X } from 'lucide-react';
import { useFullPage, useSelection, useTalkDock, useTalkConversation } from '@/hooks';
import { cn } from '@/lib/utils';
import { SpeakerAvatar } from './SpeakerAvatar';
import { TalkPane } from './TalkHost';

/**
 * Desktop chat window docked at the bottom right, like a messenger pop-up. It
 * sits left of the detail panel while one is showing, and above the full page
 * (`?full=1`), so the chat survives whatever else the atlas is doing. It stays
 * on the person it was opened for until closed.
 */
export function TalkDock() {
  const { talkWith, minimised, close, setMinimised } = useTalkDock();
  const { sel } = useSelection();
  const { full } = useFullPage();
  const { data } = useTalkConversation(talkWith?.id);
  if (!talkWith) return null;
  const panelOpen = sel != null && !full;
  const speaker = data?.entity ?? { name: talkWith.name, image: null };
  const iconBtn = 'grid size-8 flex-none place-items-center rounded-lg text-muted-foreground hover:bg-muted hover:text-foreground';
  return (
    <section
      aria-label={`Chat with ${talkWith.name}`}
      style={{ right: panelOpen ? 380 + 16 : 16 }}
      className={cn(
        'fixed bottom-0 z-[45] flex w-[360px] max-w-[calc(100vw-2rem)] flex-col overflow-hidden rounded-t-xl border border-b-0 bg-card shadow-xl',
        minimised ? 'h-auto' : 'h-[min(520px,calc(100dvh-5rem))]',
      )}
    >
      <header className="flex flex-none items-center gap-2 border-b bg-card px-2.5 py-2">
        <SpeakerAvatar speaker={speaker} className="size-8 text-[13px]" />
        <button
          type="button"
          onClick={() => setMinimised(!minimised)}
          className="min-w-0 flex-1 truncate text-left font-heading text-[14px] font-semibold"
          title={minimised ? 'Open the chat' : 'Minimise the chat'}
        >
          {talkWith.name}
        </button>
        <button
          type="button"
          onClick={() => setMinimised(!minimised)}
          aria-label={minimised ? 'Open the chat' : 'Minimise the chat'}
          className={iconBtn}
        >
          {minimised ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </button>
        <button type="button" onClick={close} aria-label="Close the chat" className={iconBtn}>
          <X size={16} />
        </button>
      </header>
      {/* Kept mounted while minimised so a half-typed message survives. */}
      <div className={cn('min-h-0 flex-1 flex-col', minimised ? 'hidden' : 'flex')}>
        <TalkPane entityId={talkWith.id} name={talkWith.name} variant="dock" />
      </div>
    </section>
  );
}
