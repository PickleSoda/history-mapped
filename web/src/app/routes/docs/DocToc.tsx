import { useEffect, useState } from 'react';
import type { TocItem } from '@/lib/docs/docs';
import { cn } from '@/lib/utils';

/** The heading nearest the top of the viewport (scroll-spy over the TOC ids). */
function useActiveHeading(items: TocItem[]): string | null {
  const [active, setActive] = useState<string | null>(null);
  useEffect(() => {
    if (items.length === 0 || typeof IntersectionObserver === 'undefined') return;
    const visible = new Set<string>();
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) visible.add(entry.target.id);
          else visible.delete(entry.target.id);
        }
        const first = items.find((item) => visible.has(item.id));
        if (first) setActive(first.id);
      },
      // A heading counts once it is in the top quarter of the viewport.
      { rootMargin: '0px 0px -75% 0px' },
    );
    for (const item of items) {
      const element = document.getElementById(item.id);
      if (element) observer.observe(element);
    }
    return () => observer.disconnect();
  }, [items]);
  return active;
}

/** "On this page": the doc's H2 / H3 headings (desktop only). */
export function DocToc({ items }: { items: TocItem[] }) {
  const active = useActiveHeading(items);
  if (items.length === 0) return null;
  return (
    <nav aria-label="On this page" className="text-sm">
      <p className="mb-3 text-xs font-semibold tracking-wide text-muted-foreground uppercase">On this page</p>
      <ul className="space-y-1.5 border-l">
        {items.map((item) => (
          <li key={item.id}>
            <a
              href={`#${item.id}`}
              aria-current={active === item.id ? 'location' : undefined}
              className={cn(
                '-ml-px block border-l py-0.5 leading-snug text-muted-foreground transition-colors hover:text-foreground',
                item.depth === 3 ? 'pl-6' : 'pl-3',
                active === item.id ? 'border-foreground font-medium text-foreground' : 'border-transparent',
              )}
            >
              {item.text}
            </a>
          </li>
        ))}
      </ul>
    </nav>
  );
}
