import { MessageCircle } from 'lucide-react';
import { Link } from 'react-router-dom';
import { talkPath } from '@/lib/site-links';
import { cn } from '@/lib/utils';

/**
 * "Talk" on a person who can be talked to (`can_talk` on the entity). It is a
 * plain link: the chat page sends a signed-out visitor to sign in and back.
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
  return (
    <Link
      to={talkPath(entityId)}
      title={`Talk with ${name}: an AI role-play based on atlas data`}
      className={cn(
        'inline-flex h-8 items-center gap-1.5 rounded-lg bg-primary px-3 text-[12px] font-medium text-primary-foreground transition-colors hover:bg-primary/85',
        className,
      )}
    >
      <MessageCircle size={14} /> Talk with {name.split(/[\s,]/)[0]}
    </Link>
  );
}
