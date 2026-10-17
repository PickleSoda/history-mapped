import type { DiffChunk } from '@/lib/text-diff';
import { cn } from '@/lib/utils';

/** Inline word diff: removals struck through in red, additions in green. */
export function DiffText({ chunks, className }: { chunks: readonly DiffChunk[]; className?: string }) {
  return (
    <p className={cn('whitespace-pre-wrap break-words text-[13px] leading-relaxed', className)}>
      {chunks.map(([op, text], i) =>
        op === '=' ? (
          <span key={i}>{text}</span>
        ) : op === '-' ? (
          <del
            key={i}
            className="rounded-sm bg-red-500/15 text-red-800 decoration-red-700/60 dark:text-red-300 dark:decoration-red-300/60"
          >
            {text}
          </del>
        ) : (
          <ins
            key={i}
            className="rounded-sm bg-emerald-500/15 text-emerald-800 no-underline dark:text-emerald-300"
          >
            {text}
          </ins>
        ),
      )}
    </p>
  );
}

/** "+3 −2 words" — the size of a change at a glance. */
export function DiffStats({ added, removed }: { added: number; removed: number }) {
  return (
    <span className="inline-flex items-center gap-1.5 font-mono text-[11px]">
      <span className="text-emerald-700 dark:text-emerald-400">+{added}</span>
      <span className="text-red-700 dark:text-red-400">−{removed}</span>
      <span className="text-muted-foreground">words</span>
    </span>
  );
}
