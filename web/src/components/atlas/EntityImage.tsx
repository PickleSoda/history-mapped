import { useState } from 'react';
import { isEmblem, mediaHost, mediaKindLabel } from '@/lib/entity-format';
import type { MediaItem } from '@/lib/entity-format';
import { cn } from '@/lib/utils';

/** "Author · CC BY-SA 4.0 · Wikimedia Commons", each part linked where it can be. */
export function MediaCreditLine({ item, className }: { item: MediaItem; className?: string }) {
  const { credit } = item;
  const link = 'underline-offset-2 hover:text-foreground hover:underline';
  return (
    <span className={cn('text-[11px] text-muted-foreground', className)}>
      {credit?.author && <span>{credit.author}</span>}
      {credit?.license && (
        <>
          {credit.author && ' · '}
          {credit.licenseUrl ? (
            <a href={credit.licenseUrl} target="_blank" rel="noopener noreferrer license" className={link}>
              {credit.license}
            </a>
          ) : (
            credit.license
          )}
        </>
      )}
      {(credit?.author || credit?.license) && ' · '}
      <a href={credit?.pageUrl ?? item.url} target="_blank" rel="noopener noreferrer" className={link}>
        {mediaHost(credit, item.url)}
      </a>
    </span>
  );
}

/**
 * A linked (not copied) image with its credit. Emblems (flags, arms, seals,
 * logos) are shown whole and small; photos and maps fill up to `maxHeight`.
 * Renders nothing if the image fails to load.
 */
export function EntityImage({
  item,
  className,
  imgClassName,
  showCaption = true,
}: {
  item: MediaItem;
  className?: string;
  imgClassName?: string;
  showCaption?: boolean;
}) {
  const [failed, setFailed] = useState(false);
  if (failed) return null;
  const emblem = isEmblem(item.kind);
  const kind = mediaKindLabel(item.kind);
  const caption = showCaption ? item.caption : null;

  return (
    <figure className={cn('overflow-hidden rounded-xl border bg-muted/30', className)}>
      <a href={item.credit?.pageUrl ?? item.url} target="_blank" rel="noopener noreferrer" className="block">
        <img
          src={item.url}
          alt={item.caption ?? kind ?? ''}
          loading="lazy"
          decoding="async"
          onError={() => setFailed(true)}
          className={cn('mx-auto block w-auto max-w-full object-contain', emblem && 'p-3', imgClassName)}
        />
      </a>
      <figcaption className="flex flex-wrap items-baseline gap-x-2 border-t bg-card/60 px-3 py-1.5">
        {kind && <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">{kind}</span>}
        {caption && <span className="line-clamp-2 min-w-0 text-[12px] text-foreground/80">{caption}</span>}
        <MediaCreditLine item={item} className="ml-auto" />
      </figcaption>
    </figure>
  );
}
