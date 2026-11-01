/**
 * Skeleton placeholder for a public-site route. Each track replaces the pages
 * that import it (spec 2026-11-01 public site, D1); it is deleted when none do.
 */
export function PagePlaceholder({ title, note }: { title: string; note?: string }) {
  return (
    <section className="mx-auto w-full max-w-3xl px-4 py-16">
      <h1 className="font-heading text-3xl">{title}</h1>
      {note && <p className="mt-2 text-sm text-muted-foreground">{note}</p>}
    </section>
  );
}
