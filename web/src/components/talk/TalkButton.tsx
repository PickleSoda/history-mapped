import { MessageCircle } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useTalkDock } from '@/hooks';
import { talkPath } from '@/lib/site-links';
import { cn } from '@/lib/utils';
import { useTalkHost } from './TalkHost';

const look =
  'inline-flex h-8 items-center gap-1.5 rounded-lg bg-primary px-3 text-[12px] font-medium text-primary-foreground transition-colors hover:bg-primary/85';

/**
 * "Talk" on a person who can be talked to (`can_talk` on the entity). Inside
 * the atlas shells it opens the chat in place (docked window / sheet); on any
 * other page it is a link to the chat page, which sends a guest to sign in.
 */
export function TalkButton({
  entityId,
  name,
  className,
}: {
  entityId: string;
  name: string;
  className?: string;
}) {
  const inAtlas = useTalkHost();
  const { open } = useTalkDock();
  const title = `Talk with ${name}: an AI role-play based on atlas data`;
  const label = (
    <>
      <MessageCircle size={14} /> Talk with {name.split(/[\s,]/)[0]}
    </>
  );
  if (!inAtlas) {
    return (
      <Link to={talkPath(entityId)} title={title} className={cn(look, className)}>
        {label}
      </Link>
    );
  }
  return (
    <button type="button" title={title} onClick={() => open({ id: entityId, name })} className={cn(look, className)}>
      {label}
    </button>
  );
}
