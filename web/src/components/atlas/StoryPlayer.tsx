import { ChevronLeft, ChevronRight, Info, Pause, Play, Swords } from 'lucide-react';
import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { storyKindLabel } from '@/components/atlas/StoryCard';
import { useMapStory, useSelection, useStoryNav } from '@/hooks';
import { contingentColors } from '@/lib/map-story/colors';
import type { MapStoryDocument, StoryLinked, StorySide, StoryStep } from '@/lib/schemas/map-story';
import { cn } from '@/lib/utils';

/** A name that opens its atlas entity when the story links one. */
function EntityName({ item, className }: { item: StoryLinked; className?: string }) {
  const { select } = useSelection();
  if (!item.entity_id) return <span className={className}>{item.name}</span>;
  return (
    <button
      type="button"
      onClick={() => select(item.entity_id as string)}
      className={cn('underline decoration-dotted underline-offset-2 hover:decoration-solid', className)}
    >
      {item.name}
    </button>
  );
}

/** One line per side: colour, name, commanders (strength and losses fold away below),
 *  then its contingents' colours when it has any. */
function SideRow({ side }: { side: StorySide }) {
  const contingents = contingentColors(side);
  return (
    <div>
      <div className="flex items-baseline gap-2 text-[12px] leading-snug">
        <span
          className="size-2.5 flex-none translate-y-[1px] rounded-sm ring-1 ring-black/20"
          style={{ backgroundColor: side.color }}
        />
        <div className="min-w-0 truncate">
          <span className="font-semibold">
            {side.polity?.entity_id ? <EntityName item={{ ...side.polity, name: side.name }} /> : side.name}
          </span>
          {side.commanders.length > 0 && (
            <span className="text-muted-foreground">
              {' · '}
              {side.commanders.map((c, i) => (
                <span key={c.name}>
                  {i > 0 && ', '}
                  <EntityName item={c} className="text-foreground/80" />
                </span>
              ))}
            </span>
          )}
        </div>
      </div>
      {side.contingents.length > 0 && (
        <div className="ml-[18px] flex flex-wrap gap-x-2.5 gap-y-0.5 text-[11px] text-muted-foreground">
          {side.contingents.map((c) => (
            <span key={c.id} className="inline-flex items-center gap-1">
              <span className="size-2 rounded-sm ring-1 ring-black/20" style={{ backgroundColor: contingents.get(c.id) }} />
              {c.name}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

/** Each side's strength and losses. */
function Forces({ sides }: { sides: StorySide[] }) {
  if (!sides.some((s) => s.strength || s.losses)) return null;
  return (
    <Fold title="Forces and losses">
      {sides.map((s) => (
        <div key={s.id}>
          <div className="flex items-center gap-1.5 font-semibold text-foreground">
            <span className="size-2.5 rounded-sm" style={{ backgroundColor: s.color }} />
            {s.name}
          </div>
          {s.strength && <div>Strength: {s.strength}</div>}
          {s.losses && <div>Losses: {s.losses}</div>}
        </div>
      ))}
    </Fold>
  );
}

/** Background / reconstruction notes, folded away by default. */
function Fold({ title, children }: { title: string; children: ReactNode }) {
  return (
    <details className="group mt-4 rounded-lg border bg-muted/30 px-3 py-2 text-[12px]">
      <summary className="flex cursor-pointer list-none items-center gap-1.5 font-medium text-muted-foreground">
        <Info size={13} /> {title}
        <ChevronRight size={13} className="ml-auto transition-transform group-open:rotate-90" />
      </summary>
      <div className="mt-2 space-y-2 leading-relaxed text-foreground/80">{children}</div>
    </details>
  );
}

/** Whether anything in the story is marked as reconstructed rather than attested. */
function usesConjectural(doc: MapStoryDocument): boolean {
  if (doc.terrain.some((t) => t.conjectural)) return true;
  return doc.steps.some((s) =>
    [s, ...s.beats].some(
      (p) =>
        Object.values(p.positions).some((pl) => pl.conjectural) ||
        p.moves.some((m) => m.conjectural) ||
        p.notes.some((n) => n.conjectural),
    ),
  );
}

function Reconstruction({ doc }: { doc: MapStoryDocument }) {
  return (
    <Fold title="About this reconstruction">
      {doc.uncertainty && <p>{doc.uncertainty}</p>}
      <p className="text-muted-foreground">
        Pale blue water and grey place names are today's, for orientation; the
        bolder rivers, hills and woods are the historical terrain.
        {usesConjectural(doc) && ' Dashed = conjectural: reconstructed rather than attested.'}
      </p>
      {doc.alt_sites.length > 0 && (
        <div>
          <p className="font-medium">Other proposed sites (grey ? pins)</p>
          <ul className="list-disc space-y-0.5 pl-4">
            {doc.alt_sites.map((a) => (
              <li key={a.label}>
                {a.label}
                {a.note && <span className="text-muted-foreground"> — {a.note}</span>}
              </li>
            ))}
          </ul>
        </div>
      )}
      {doc.sources.length > 0 && (
        <ul className="list-disc space-y-0.5 pl-4">
          {doc.sources.map((s) => (
            <li key={s.title}>
              {s.url ? (
                <a href={s.url} target="_blank" rel="noreferrer" className="underline underline-offset-2">
                  {s.title}
                </a>
              ) : (
                s.title
              )}
            </li>
          ))}
        </ul>
      )}
    </Fold>
  );
}

/** How long autoplay lingers on a step: long enough to read it (and play its beats). */
function dwellMs(step: StoryStep): number {
  return Math.min(22000, Math.max(6000, step.narrative.length * 45)) + step.beats.length * 1200;
}

/** Chrome-less battle-map body — shared by the desktop aside and the mobile sheet. */
export function StoryPlayerContent() {
  const { story, step, goto, next, prev } = useStoryNav();
  const { data, isLoading, isError } = useMapStory(story);
  const [playing, setPlaying] = useState(false);

  const doc = data?.document;
  const total = doc?.steps.length ?? 0;
  const index = Math.min(Math.max(step, 0), Math.max(total - 1, 0));
  const current = doc?.steps[index];
  const atEnd = index >= total - 1;

  // Autoplay: advance after the step has had time to be read; stop on the last.
  useEffect(() => {
    if (!playing || !current || atEnd) return;
    const timer = setTimeout(() => {
      next();
      if (index + 1 >= total - 1) setPlaying(false);
    }, dwellMs(current));
    return () => clearTimeout(timer);
  }, [playing, current, atEnd, next, index, total]);

  // ← / → step through the battle (not while typing).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      if (t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName))) return;
      if (e.key === 'ArrowRight' && !atEnd) next();
      if (e.key === 'ArrowLeft' && index > 0) prev();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [atEnd, index, next, prev]);

  return (
    <div className="flex h-full flex-col">
      {isLoading && <p className="p-4 text-sm text-muted-foreground">Loading…</p>}
      {isError && <p className="p-4 text-sm text-destructive">Could not load the battle map.</p>}

      {doc && current && (
        <>
          <div className="px-4 pt-4">
            <h2 className="font-heading text-lg font-semibold leading-tight">{doc.title}</h2>
            <p className="mt-0.5 font-mono text-[11px] text-muted-foreground">{doc.date_label}</p>
            <div className="mt-2.5 space-y-1">
              {doc.sides.map((s) => (
                <SideRow key={s.id} side={s} />
              ))}
            </div>
            <div className="mt-3 flex items-center gap-2">
              <span className="font-mono text-[11px] text-muted-foreground">
                {index + 1} / {total}
              </span>
              <div className="flex flex-1 flex-wrap gap-1">
                {doc.steps.map((s, i) => (
                  <button
                    key={s.id}
                    type="button"
                    onClick={() => goto(i)}
                    title={s.title}
                    aria-label={`Step ${i + 1}: ${s.title}`}
                    className={cn(
                      'h-1.5 rounded-full transition-all',
                      i === index ? 'w-4 bg-foreground' : i < index ? 'w-1.5 bg-foreground/50' : 'w-1.5 bg-border',
                    )}
                  />
                ))}
              </div>
            </div>
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
            {current.time && (
              <p className="mb-1 font-mono text-[11px] uppercase tracking-wide text-muted-foreground">
                {current.time}
              </p>
            )}
            <h3 className="font-heading text-[15px] font-semibold leading-snug">{current.title}</h3>
            <p className="mt-2 whitespace-pre-line break-words text-[13px] leading-relaxed text-foreground/90">
              {current.narrative}
            </p>
            {current.beats.some((b) => b.label) && (
              <ol className="mt-2 space-y-0.5 border-l-2 border-border pl-3 text-[12px] leading-snug text-muted-foreground">
                {current.beats
                  .filter((b) => b.label)
                  .map((b, i) => (
                    <li key={i}>
                      <span className="font-mono text-[10px] text-muted-foreground/70">{i + 1}.</span> {b.label}
                    </li>
                  ))}
              </ol>
            )}
            {index === 0 && doc.intro && <Fold title="Background">{<p>{doc.intro}</p>}</Fold>}
            {atEnd && doc.outcome && (
              <div className="mt-4 rounded-lg border bg-muted/40 p-3 text-[12px]">
                <span className="font-semibold">Outcome. </span>
                {doc.outcome}
              </div>
            )}
            <Forces sides={doc.sides} />
            <Reconstruction doc={doc} />
          </div>

          <div className="flex gap-2 border-t p-3">
            <button
              type="button"
              onClick={prev}
              disabled={index <= 0}
              className="inline-flex items-center gap-1 rounded-lg border bg-card px-3 py-2 text-[13px] font-medium hover:bg-muted disabled:opacity-40"
            >
              <ChevronLeft size={15} /> Prev
            </button>
            <button
              type="button"
              onClick={() => (atEnd ? goto(0) : setPlaying((p) => !p))}
              aria-label={playing ? 'Pause' : atEnd ? 'Replay from the start' : 'Play'}
              title={playing ? 'Pause' : atEnd ? 'Replay from the start' : 'Play through the battle'}
              className="grid w-10 place-items-center rounded-lg border bg-card hover:bg-muted"
            >
              {playing ? <Pause size={15} /> : <Play size={15} />}
            </button>
            <button
              type="button"
              onClick={next}
              disabled={atEnd}
              className="inline-flex flex-1 items-center justify-center gap-1 rounded-lg bg-primary px-3 py-2 text-[13px] font-medium text-primary-foreground hover:opacity-90 disabled:opacity-40"
            >
              Next <ChevronRight size={15} />
            </button>
          </div>
        </>
      )}
    </div>
  );
}

/** Desktop left aside while a battle map plays (?story=). */
export function StoryPlayer() {
  const { exit, story } = useStoryNav();
  const { data } = useMapStory(story);
  const { select } = useSelection();
  const entityId = data?.document.entity.entity_id ?? data?.entity_id ?? null;
  const label = storyKindLabel(data?.kind ?? 'battle');
  return (
    <aside className="flex h-full w-[380px] max-w-[90vw] flex-none flex-col border-r bg-card">
      <div className="flex items-center justify-between border-b px-3 py-2">
        <button
          type="button"
          onClick={exit}
          className="inline-flex items-center gap-1 rounded-md px-1.5 py-1 text-[13px] text-muted-foreground hover:bg-muted hover:text-foreground"
        >
          <ChevronLeft size={15} /> Exit {label.toLowerCase()}
        </button>
        <div className="flex items-center gap-1.5">
          <span className="inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] text-muted-foreground">
            <Swords size={12} /> {label}
          </span>
          {entityId && (
            <button
              type="button"
              onClick={() => select(entityId)}
              className="rounded-md px-2 py-1 text-[12px] font-medium text-primary hover:bg-muted"
              title="Open the battle's details"
            >
              Details
            </button>
          )}
        </div>
      </div>
      <div className="min-h-0 flex-1">
        <StoryPlayerContent />
      </div>
    </aside>
  );
}
