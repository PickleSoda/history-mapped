import { Link } from 'react-router-dom';
import { useTalkList } from '@/hooks';
import { talkPath } from '@/lib/site-links';
import { ago, lifeText } from '@/lib/talk';
import { cn } from '@/lib/utils';
import { SpeakerAvatar } from './SpeakerAvatar';

/**
 * The people already talked with, most recent first. On a phone this is the
 * whole `/talk` screen; on a wide screen it is the left column.
 */
export function TalkSidebar({ activeId }: { activeId?: string }) {
  const { data, isLoading, isError } = useTalkList();

  return (
    <nav aria-label="People you have talked with" className="flex h-full min-h-0 flex-col">
      <h1 className="px-4 pb-2 pt-4 font-heading text-[20px] font-semibold tracking-tight">Talk with people</h1>
      <div className="min-h-0 flex-1 overflow-y-auto px-2 pb-4">
        {isLoading && <p className="px-2 py-3 text-[13px] text-muted-foreground">Loading…</p>}
        {isError && <p className="px-2 py-3 text-[13px] text-destructive">Could not load your conversations.</p>}
        {data && data.data.length === 0 && (
          <div className="px-2 py-3 text-[13px] text-muted-foreground">
            <p>You have not talked with anyone yet.</p>
            <p className="mt-2">
              Open a person who lived long ago (a ruler, a general, a thinker) and choose <b>Talk</b>, or{' '}
              <Link to="/browse" className="underline underline-offset-2 hover:text-foreground">
                browse the atlas
              </Link>
              .
            </p>
          </div>
        )}
        <ul className="space-y-0.5">
          {data?.data.map((row) => {
            const active = row.entity.id === activeId;
            const life = lifeText(row.entity);
            return (
              <li key={row.id}>
                <Link
                  to={talkPath(row.entity.id)}
                  aria-current={active ? 'page' : undefined}
                  className={cn(
                    'flex items-center gap-3 rounded-lg px-2 py-2 transition-colors',
                    active ? 'bg-muted' : 'hover:bg-muted/60',
                  )}
                >
                  <SpeakerAvatar speaker={row.entity} className="size-11" />
                  <span className="min-w-0 flex-1">
                    <span className="flex items-baseline gap-2">
                      <span className="min-w-0 flex-1 truncate text-[13.5px] font-medium">{row.entity.name}</span>
                      <span className="flex-none font-mono text-[10px] text-muted-foreground">
                        {ago(row.last_message_at)}
                      </span>
                    </span>
                    {life && <span className="block truncate font-mono text-[10.5px] text-muted-foreground">{life}</span>}
                    {row.last_message && (
                      <span className="mt-0.5 block truncate text-[12px] text-muted-foreground">
                        {row.last_message.role === 'user' && 'You: '}
                        {row.last_message.snippet}
                      </span>
                    )}
                  </span>
                </Link>
              </li>
            );
          })}
        </ul>
      </div>
    </nav>
  );
}
