import { ArrowRight, Database, Globe, PenLine, Route, ScrollText, Swords } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { useChronicleList, useTags } from '@/hooks';
import { yearSpanText } from '@/lib/chronicle-page';
import { useDocumentMeta } from '@/lib/document-meta';
import type { ChronicleSummary } from '@/lib/schemas/chronicle';
import { ATLAS_PATH, chroniclePagePath } from '@/lib/site-links';
import { displayTags } from '@/lib/tags';

const PRIMARY =
  'inline-flex h-11 items-center gap-2 rounded-xl bg-primary px-5 text-[15px] font-medium text-primary-foreground shadow-sm transition-colors hover:bg-primary/85';
const SECONDARY =
  'inline-flex h-11 items-center gap-2 rounded-xl border bg-card px-5 text-[15px] font-medium shadow-xs transition-colors hover:bg-muted';

/** A wireframe globe with a few linked places: decoration for the hero. */
function GlobeMark({ className }: { className?: string }) {
  const dots = [
    { x: 118, y: 92, c: 'var(--g-polity)' },
    { x: 176, y: 128, c: 'var(--g-event)' },
    { x: 92, y: 158, c: 'var(--g-place)' },
    { x: 150, y: 196, c: 'var(--g-culture)' },
    { x: 206, y: 176, c: 'var(--g-economy)' },
  ];
  return (
    <svg viewBox="0 0 300 300" aria-hidden className={className}>
      <g fill="none" stroke="currentColor" strokeWidth="1" className="text-border">
        <circle cx="150" cy="150" r="120" />
        <ellipse cx="150" cy="150" rx="42" ry="120" />
        <ellipse cx="150" cy="150" rx="84" ry="120" />
        <line x1="150" y1="30" x2="150" y2="270" />
        <ellipse cx="150" cy="150" rx="120" ry="40" />
        <path d="M45 92 Q150 72 255 92" />
        <path d="M45 208 Q150 228 255 208" />
      </g>
      <path
        d="M118 92 Q160 96 176 128 T150 196 Q180 196 206 176"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeDasharray="4 5"
        className="text-foreground/40"
      />
      <path d="M92 158 Q100 120 118 92" fill="none" stroke="currentColor" strokeWidth="1.5" strokeDasharray="4 5" className="text-foreground/25" />
      {dots.map((d) => (
        <g key={`${d.x}-${d.y}`}>
          <circle cx={d.x} cy={d.y} r="11" fill={d.c} opacity="0.18" />
          <circle cx={d.x} cy={d.y} r="5" fill={d.c} />
        </g>
      ))}
    </svg>
  );
}

function Hero() {
  return (
    <section className="relative overflow-hidden border-b">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 [mask-image:radial-gradient(ellipse_at_top,black,transparent_70%)]"
        style={{
          backgroundImage: 'radial-gradient(var(--border) 1px, transparent 1px)',
          backgroundSize: '22px 22px',
        }}
      />
      <div className="relative mx-auto grid w-full max-w-6xl items-center gap-10 px-4 py-16 sm:px-6 md:grid-cols-[minmax(0,1fr)_300px] md:py-24">
        <div>
          <p className="text-[12px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
            An open atlas of world history
          </p>
          <h1 className="mt-4 text-balance font-heading text-[44px] font-semibold leading-[1.02] tracking-tight sm:text-[56px] md:text-[68px]">
            History Mapped
          </h1>
          {/* TODO(copy): user to refine */}
          <p className="mt-5 max-w-xl text-pretty text-[17px] leading-relaxed text-foreground/80 md:text-[19px]">
            Explore states, people, battles and ideas, each one linked to the others and placed on a map
            that moves through time.
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-3">
            <Link to={ATLAS_PATH} className={PRIMARY}>
              <Globe size={17} aria-hidden /> Open the globe
            </Link>
            <Link to="/browse" className={SECONDARY}>
              Browse <ArrowRight size={16} aria-hidden />
            </Link>
          </div>
        </div>
        <GlobeMark className="mx-auto hidden w-full max-w-[300px] md:block" />
      </div>
    </section>
  );
}

function SectionHeading({ eyebrow, title, children }: { eyebrow: string; title: string; children?: ReactNode }) {
  return (
    <div className="max-w-2xl">
      <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">{eyebrow}</p>
      <h2 className="mt-2 text-balance font-heading text-[28px] font-semibold leading-tight tracking-tight md:text-[34px]">
        {title}
      </h2>
      {children && <p className="mt-3 text-[15px] leading-relaxed text-muted-foreground">{children}</p>}
    </div>
  );
}

function Why() {
  return (
    <section className="mx-auto w-full max-w-6xl px-4 py-16 sm:px-6 md:py-20">
      <SectionHeading eyebrow="Why" title="History happens all at once" />
      {/* TODO(copy): user to refine */}
      <div className="mt-8 grid gap-6 text-[15px] leading-[1.75] text-foreground/85 md:grid-cols-3 md:gap-10">
        <p>
          History is usually told one story at a time: a book on Rome, a documentary on the Mongols, an
          article on a single battle. The connections between them, who traded with whom, which war ended
          which empire, what else was happening in the same decade, are left for the reader to assemble.
        </p>
        <p>
          History Mapped puts those stories on one map and one timeline. Every polity, person, event, place
          and idea is an entity with dates, a location and typed relationships to the others, so you can
          walk from a battle to the empires that fought it and on to the routes they fought over, and see
          where everything stood in any given year.
        </p>
        <p>
          It is built in the open, from open data. Each entity shows its sources, how confident the dating
          is and how far it has been checked, so you can see how much is known and how it was put
          together. If something is wrong or missing, you can suggest a fix.
        </p>
      </div>
    </section>
  );
}

const STEPS: { icon: LucideIcon; color: string; title: string; body: string }[] = [
  {
    icon: Database,
    color: 'var(--g-place)',
    title: 'Open data underneath',
    body: 'Entities, dates and coordinates come from Wikidata; historical borders and places come from OpenHistoricalMap, the time-aware sibling of OpenStreetMap.',
  },
  {
    icon: PenLine,
    color: 'var(--g-culture)',
    title: 'An editorial layer',
    body: 'Summaries, significance and typed relationships are written and reviewed on top of the data, with sources and a confidence level on every entity.',
  },
  {
    icon: Route,
    color: 'var(--g-polity)',
    title: 'Chronicles',
    body: 'Guided tours through a period or a theme. Each step is a change on the map, a war, a treaty, a succession, told in a few sentences and linked to everything it touches.',
  },
  {
    icon: Swords,
    color: 'var(--g-event)',
    title: 'Battle maps on a time-aware map',
    body: 'Battles and campaigns replayed move by move on the terrain, over a map whose borders redraw themselves for whatever year you choose.',
  },
];

function HowItWorks() {
  return (
    <section className="border-y bg-card/40">
      <div className="mx-auto w-full max-w-6xl px-4 py-16 sm:px-6 md:py-20">
        <SectionHeading eyebrow="How it works" title="Open data, an editorial layer, and a map that moves">
          {/* TODO(copy): user to refine */}
          Four layers, from the raw facts to the stories told with them.
        </SectionHeading>
        <ol className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {STEPS.map((s, i) => (
            <li key={s.title} className="flex flex-col rounded-xl border bg-card p-5 shadow-xs">
              <div className="flex items-center justify-between">
                <span
                  className="grid size-10 place-items-center rounded-lg"
                  style={{ background: `color-mix(in oklch, ${s.color} 14%, transparent)`, color: s.color }}
                >
                  <s.icon size={19} aria-hidden />
                </span>
                <span className="font-heading text-[26px] font-semibold tabular-nums text-muted-foreground/30">
                  {i + 1}
                </span>
              </div>
              <h3 className="mt-4 font-heading text-[17px] font-semibold tracking-tight">{s.title}</h3>
              <p className="mt-2 text-[13.5px] leading-relaxed text-muted-foreground">{s.body}</p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}

function ChronicleCard({ chronicle }: { chronicle: ChronicleSummary }) {
  const { index } = useTags();
  const span = yearSpanText(chronicle.start_year, chronicle.end_year);
  const tags = displayTags(chronicle.tags, index)
    .filter((t) => t.facet !== 'topic')
    .slice(0, 3);
  return (
    <Link
      to={chroniclePagePath(chronicle.slug)}
      className="group flex h-full flex-col rounded-xl border bg-card p-5 shadow-xs transition-colors hover:bg-muted/40"
    >
      <span className="inline-flex w-fit items-center gap-1 rounded-full bg-foreground px-2 py-0.5 text-[11px] font-medium text-background">
        <ScrollText size={12} aria-hidden /> Chronicle
      </span>
      <h3 className="mt-3 line-clamp-3 font-heading text-[18px] font-semibold leading-snug tracking-tight group-hover:underline group-hover:underline-offset-4">
        {chronicle.title}
      </h3>
      <p className="mt-auto flex flex-wrap gap-x-3 gap-y-1 pt-4 font-mono text-[11.5px] text-muted-foreground">
        {span && <span>{span}</span>}
        {chronicle.entry_count != null && <span>{chronicle.entry_count} steps</span>}
      </p>
      {tags.length > 0 && (
        <p className="mt-1.5 truncate text-[12px] text-muted-foreground">{tags.map((t) => t.name).join(' · ')}</p>
      )}
    </Link>
  );
}

function StartHere() {
  const { data, isLoading, isError } = useChronicleList({ sort: 'impact' });
  const chronicles = data?.pages[0]?.data.slice(0, 3) ?? [];
  // TODO(track D): featured curated sets and battle maps via useCollections / useMapStoryList
  return (
    <section className="mx-auto w-full max-w-6xl px-4 py-16 sm:px-6 md:py-20">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <SectionHeading eyebrow="Start here" title="Three chronicles to begin with" />
        <Link
          to="/browse"
          className="inline-flex items-center gap-1.5 text-[14px] font-medium underline-offset-4 hover:underline"
        >
          Browse everything <ArrowRight size={15} aria-hidden />
        </Link>
      </div>
      <ul className="mt-8 grid gap-4 md:grid-cols-3">
        {isLoading &&
          [0, 1, 2].map((i) => (
            <li key={i} aria-hidden className="h-48 animate-pulse rounded-xl border bg-muted/50 motion-reduce:animate-none" />
          ))}
        {chronicles.map((c) => (
          <li key={c.chronicle_id}>
            <ChronicleCard chronicle={c} />
          </li>
        ))}
      </ul>
      {isError && (
        <p className="mt-2 text-[14px] text-muted-foreground">
          The chronicles could not be loaded right now.{' '}
          <Link to="/browse" className="underline underline-offset-4">
            Browse instead
          </Link>
          .
        </p>
      )}
    </section>
  );
}

function ClosingBand() {
  return (
    <section className="border-t">
      <div className="mx-auto flex w-full max-w-6xl flex-col items-start gap-5 px-4 py-14 sm:px-6 md:flex-row md:items-center md:justify-between">
        <div>
          <h2 className="font-heading text-[24px] font-semibold tracking-tight md:text-[28px]">
            The globe is one click away
          </h2>
          <p className="mt-1.5 text-[15px] text-muted-foreground">
            Scrub through time, open any place, and follow its connections.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <Link to={ATLAS_PATH} className={PRIMARY}>
            <Globe size={17} aria-hidden /> Open the globe
          </Link>
          <Link to="/docs" className={SECONDARY}>
            Read the docs
          </Link>
        </div>
      </div>
    </section>
  );
}

/** Landing page, `/` (spec D6): what the project is, how it works, where to start. */
export function LandingPage() {
  useDocumentMeta({
    title: null,
    description:
      'History Mapped is an open, interactive atlas of world history: states, people, battles and ideas, linked to one another on a map that moves through time.',
  });
  return (
    <>
      <Hero />
      <Why />
      <HowItWorks />
      <StartHere />
      <ClosingBand />
    </>
  );
}
