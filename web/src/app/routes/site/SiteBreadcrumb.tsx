import { ChevronRight } from 'lucide-react';
import { Fragment } from 'react';
import { Link } from 'react-router-dom';

export interface Crumb {
  label: string;
  /** Omitted for the current page (the last crumb). */
  to?: string;
}

/** "Browse › Battle of Cannae": where a standalone page sits on the site. */
export function SiteBreadcrumb({ items }: { items: Crumb[] }) {
  return (
    <nav aria-label="Breadcrumb" className="min-w-0">
      <ol className="flex min-w-0 items-center gap-1 text-[12px] text-muted-foreground">
        {items.map((c, i) => (
          <Fragment key={`${i}-${c.label}`}>
            {i > 0 && (
              <li aria-hidden className="flex-none">
                <ChevronRight size={13} className="opacity-60" />
              </li>
            )}
            <li className={c.to ? 'flex-none' : 'min-w-0 truncate'}>
              {c.to ? (
                <Link to={c.to} className="underline-offset-4 hover:text-foreground hover:underline">
                  {c.label}
                </Link>
              ) : (
                <span aria-current="page" className="text-foreground/80">
                  {c.label}
                </span>
              )}
            </li>
          </Fragment>
        ))}
      </ol>
    </nav>
  );
}
