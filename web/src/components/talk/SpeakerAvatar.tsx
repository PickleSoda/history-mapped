import { useState } from 'react';
import type { Speaker } from '@/lib/schemas/talk';
import { initial } from '@/lib/talk';
import { cn } from '@/lib/utils';

/** Round portrait of the person (a linked Wikimedia image), or their initial. */
export function SpeakerAvatar({ speaker, className }: { speaker: Pick<Speaker, 'name' | 'image'>; className?: string }) {
  const [failed, setFailed] = useState(false);
  const url = speaker.image?.url;
  return (
    <span
      aria-hidden
      className={cn(
        'grid size-10 flex-none place-items-center overflow-hidden rounded-full bg-muted font-heading text-[15px] font-semibold text-muted-foreground',
        className,
      )}
    >
      {url && !failed ? (
        <img
          src={url}
          alt=""
          loading="lazy"
          decoding="async"
          referrerPolicy="no-referrer"
          onError={() => setFailed(true)}
          className="size-full object-cover object-top"
        />
      ) : (
        initial(speaker.name)
      )}
    </span>
  );
}
