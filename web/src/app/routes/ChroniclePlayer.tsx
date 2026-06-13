import { useParams } from 'react-router-dom';
import { useChronicle, useChronicleNav } from '@/hooks';

/**
 * Chronicle player (placeholder wiring). While a chronicle is active the active
 * step's {time, bbox} drive the map — that derivation lands in the chronicles
 * pass. This proves the route + data + step nav are connected.
 */
export function ChroniclePlayer() {
  const { cid } = useParams();
  const { step, next, prev, exit } = useChronicleNav();
  const { data, isLoading } = useChronicle(cid ?? null);

  return (
    <div className="p-4">
      <h2 className="text-sm font-semibold text-neutral-500">
        {data?.title ?? cid}
      </h2>
      {isLoading && <p className="mt-3 text-sm text-neutral-400">Loading…</p>}
      {data && (
        <>
          <p className="mt-1 text-xs text-neutral-400">
            Step {step + 1} / {data.entries.length}
          </p>
          <p className="mt-3 text-sm">{data.entries[step]?.narrative_text}</p>
          <div className="mt-4 flex gap-2">
            <button type="button" onClick={prev} className="text-sm underline">
              Prev
            </button>
            <button type="button" onClick={next} className="text-sm underline">
              Next
            </button>
            <button type="button" onClick={exit} className="text-sm underline">
              Exit
            </button>
          </div>
        </>
      )}
    </div>
  );
}
