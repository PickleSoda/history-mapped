import { ScrollText } from 'lucide-react';
import { useChronicleList } from '@/hooks';
import { formatYear } from '@/lib/format';
import type { ChronicleSummary } from '@/lib/schemas/chronicle';

function rangeLabel(c: ChronicleSummary): string | null {
  const s = c.start_year != null ? formatYear(c.start_year) : null;
  const e = c.end_year != null ? formatYear(c.end_year) : null;
  if (s && e) return `${s} – ${e}`;
  return s ?? e ?? null;
}

function ChronicleRow({ c }: { c: ChronicleSummary }) {
  return (
    <div className="rounded-lg border bg-card px-3 py-2.5">
      <div className="flex items-start gap-2">
        <ScrollText size={15} className="mt-0.5 flex-none text-muted-foreground" />
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium">{c.title}</p>
          <div className="mt-1 flex items-center gap-2 text-[11px] text-muted-foreground">
            {rangeLabel(c) && <span className="font-mono">{rangeLabel(c)}</span>}
            {c.entry_count != null && (
              <>
                {rangeLabel(c) && <span className="opacity-50">·</span>}
                <span>{c.entry_count} steps</span>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

/** Chronicles tab — paginated listing (GET /chronicles). Selection/tour wiring
 *  is deferred; for now this is a browsable catalog. */
export function ChronicleList() {
  const { data, isLoading, isError } = useChronicleList();

  return (
    <div className="flex flex-col p-3">
      <div className="flex items-center justify-between px-1 pb-2">
        <span className="text-xs font-medium text-muted-foreground">Chronicles</span>
        {data && (
          <span className="font-mono text-[11px] text-muted-foreground">
            {data.meta.total}
          </span>
        )}
      </div>

      {isLoading && <p className="px-1 py-2 text-sm text-muted-foreground">Loading…</p>}
      {isError && (
        <p className="px-1 py-2 text-sm text-destructive">Could not load chronicles.</p>
      )}
      {data && data.data.length === 0 && (
        <p className="px-1 py-2 text-sm text-muted-foreground">No chronicles yet.</p>
      )}

      <div className="space-y-1.5">
        {data?.data.map((c) => (
          <ChronicleRow key={c.chronicle_id} c={c} />
        ))}
      </div>
    </div>
  );
}
