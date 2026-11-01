/** Pulsing bars while a page chunk or its markdown loads. */
export function DocSkeleton() {
  return (
    <div role="status" aria-label="Loading page" className="space-y-4 motion-safe:animate-pulse">
      <div className="h-9 w-2/3 rounded-md bg-muted" />
      <div className="h-4 w-full rounded bg-muted" />
      <div className="h-4 w-11/12 rounded bg-muted" />
      <div className="h-4 w-4/5 rounded bg-muted" />
    </div>
  );
}
