import { useEntitiesInView, useSelection } from '@/hooks';

/**
 * "Notable here" list (spec §6). Reads the SAME viewport query as the map — one
 * fetch feeds both. Rows will be memoized + virtualized in the UI pass; this is
 * the wired-up scaffold proving the data path end to end.
 */
export function BrowsePanel() {
  const { data, isLoading, isError } = useEntitiesInView();
  const { select } = useSelection();

  return (
    <div className="p-4">
      <h2 className="text-sm font-semibold text-neutral-500">Notable here</h2>

      {isLoading && <p className="mt-3 text-sm text-neutral-400">Loading…</p>}
      {isError && (
        <p className="mt-3 text-sm text-red-500">Could not load entities.</p>
      )}

      {data && (
        <>
          <p className="mt-1 text-xs text-neutral-400">{data.total} in view</p>
          <ul className="mt-3 space-y-1">
            {data.items.map((e) => (
              <li key={e.id}>
                <button
                  type="button"
                  onClick={() => select(e.id)}
                  className="w-full rounded px-2 py-1.5 text-left text-sm hover:bg-neutral-100"
                >
                  <span className="font-medium">{e.name}</span>
                  <span className="ml-2 text-xs uppercase text-neutral-400">
                    {e.group}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
