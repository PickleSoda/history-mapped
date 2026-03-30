import { useCallback, useEffect, useRef, useState } from 'react';
import { show as showEntity } from '@/actions/App/Http/Api/V1/Controllers/EntityController';
import {
    destroy as destroyEntityGeoRef,
    index as listEntityGeoRefs,
    store as storeEntityGeoRef,
} from '@/actions/App/Http/Api/V1/Controllers/EntityGeoRefController';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import type { GeoJsonLike } from '@/lib/geojson';
import type { EntityGeoRef } from '@/types/entity';

type EntityGeoRefEditorProps = {
    entityId: string;
    onHydratedGeometryChange: (
        geojson: GeoJsonLike,
        territoryGeojson: GeoJsonLike,
    ) => void;
};

type EntityShowPayload = {
    id: string;
    geom?: GeoJsonLike;
    territory_geom?: GeoJsonLike;
};

export default function EntityGeoRefEditor({
    entityId,
    onHydratedGeometryChange,
}: EntityGeoRefEditorProps) {
    const csrfRef = useRef<string>('');
    const [refs, setRefs] = useState<EntityGeoRef[]>([]);
    const [externalType, setExternalType] = useState<'relation' | 'way' | 'node'>('relation');
    const [externalId, setExternalId] = useState('');
    const [loading, setLoading] = useState(true);
    const [attaching, setAttaching] = useState(false);
    const [deletingId, setDeletingId] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const meta = document.querySelector<HTMLMetaElement>('meta[name="csrf-token"]');
        csrfRef.current = meta?.content ?? '';
    }, []);

    const reload = useCallback(async () => {
        setLoading(true);
        setError(null);

        try {
            const response = await fetch(listEntityGeoRefs(entityId).url, {
                headers: {
                    Accept: 'application/json',
                    'X-CSRF-TOKEN': csrfRef.current,
                },
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const payload = (await response.json()) as { data?: EntityGeoRef[] };
            setRefs(payload.data ?? []);
        } catch (caught) {
            console.error(caught);
            setError('Failed to load OHM references.');
        } finally {
            setLoading(false);
        }
    }, [entityId]);

    useEffect(() => {
        void reload();
    }, [reload]);

    async function refreshEntityGeometry(): Promise<void> {
        const response = await fetch(
            showEntity(entityId, { query: { include_territory: true } }).url,
            {
                headers: {
                    Accept: 'application/json',
                    'X-CSRF-TOKEN': csrfRef.current,
                },
            },
        );

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const payload = (await response.json()) as EntityShowPayload;
        onHydratedGeometryChange(payload.geom ?? null, payload.territory_geom ?? null);
    }

    async function handleAttach(): Promise<void> {
        if (externalId.trim() === '') {
            return;
        }

        setAttaching(true);
        setError(null);

        try {
            const response = await fetch(storeEntityGeoRef(entityId).url, {
                method: 'POST',
                headers: {
                    Accept: 'application/json',
                    'Content-Type': 'application/json',
                    'X-CSRF-TOKEN': csrfRef.current,
                },
                body: JSON.stringify({
                    provider: 'ohm',
                    external_type: externalType,
                    external_id: externalId.trim(),
                    match_role: 'candidate',
                    retrieval_method: 'rest',
                }),
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            await refreshEntityGeometry();
            await reload();
            setExternalId('');
        } catch (caught) {
            console.error(caught);
            setError('Failed to attach OHM reference.');
        } finally {
            setAttaching(false);
        }
    }

    async function handleDelete(geoRefId: string): Promise<void> {
        setDeletingId(geoRefId);
        setError(null);

        try {
            const response = await fetch(
                destroyEntityGeoRef({ entity: entityId, ref: geoRefId }).url,
                {
                    method: 'DELETE',
                    headers: {
                        Accept: 'application/json',
                        'X-CSRF-TOKEN': csrfRef.current,
                    },
                },
            );

            if (!response.ok && response.status !== 204) {
                throw new Error(`HTTP ${response.status}`);
            }

            await reload();
        } catch (caught) {
            console.error(caught);
            setError('Failed to delete OHM reference.');
        } finally {
            setDeletingId(null);
        }
    }

    return (
        <div className="space-y-4">
            <div>
                <h3 className="text-sm font-semibold">OHM References</h3>
                <p className="mt-0.5 text-xs text-muted-foreground">
                    Attach existing OpenHistoricalMap objects to preserve provenance and hydrate local geometry.
                </p>
            </div>

            {error && (
                <Alert variant="destructive">
                    <AlertDescription>{error}</AlertDescription>
                </Alert>
            )}

            <div className="grid gap-3 rounded-md border border-dashed p-3 md:grid-cols-[10rem_1fr_auto] md:items-end">
                <div className="space-y-1">
                    <Label htmlFor="entity-geo-ref-type" className="text-xs">
                        OHM object type
                    </Label>
                    <select
                        id="entity-geo-ref-type"
                        className="h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm"
                        value={externalType}
                        onChange={(event) =>
                            setExternalType(event.target.value as 'relation' | 'way' | 'node')
                        }
                    >
                        <option value="relation">Relation</option>
                        <option value="way">Way</option>
                        <option value="node">Node</option>
                    </select>
                </div>
                <div className="space-y-1">
                    <Label htmlFor="entity-geo-ref-id" className="text-xs">
                        OHM object id
                    </Label>
                    <Input
                        id="entity-geo-ref-id"
                        value={externalId}
                        onChange={(event) => setExternalId(event.target.value)}
                        placeholder="1880"
                        inputMode="numeric"
                    />
                </div>
                <Button
                    type="button"
                    onClick={() => void handleAttach()}
                    disabled={attaching || externalId.trim() === ''}
                >
                    {attaching ? 'Attaching…' : 'Attach OHM reference'}
                </Button>
            </div>

            {loading ? (
                <div className="text-sm text-muted-foreground">Loading OHM references…</div>
            ) : refs.length === 0 ? (
                <div className="rounded-md border border-dashed px-4 py-5 text-sm text-muted-foreground">
                    No OHM references attached yet.
                </div>
            ) : (
                <div className="divide-y rounded-md border">
                    {refs.map((geoRef) => (
                        <div
                            key={geoRef.geo_ref_id}
                            className="flex items-center justify-between gap-3 px-4 py-3"
                        >
                            <div className="min-w-0 flex-1">
                                <div className="flex items-center gap-2">
                                    <span className="truncate text-sm font-medium">
                                        {displayGeoRefLabel(geoRef)}
                                    </span>
                                    {geoRef.is_active && <Badge variant="outline">Active</Badge>}
                                </div>
                                <p className="mt-0.5 text-xs text-muted-foreground">
                                    {geoRef.external_type}:{geoRef.external_id}
                                </p>
                            </div>
                            <Button
                                type="button"
                                size="sm"
                                variant="outline"
                                onClick={() => void handleDelete(geoRef.geo_ref_id)}
                                disabled={deletingId === geoRef.geo_ref_id}
                            >
                                {deletingId === geoRef.geo_ref_id ? 'Removing…' : 'Remove'}
                            </Button>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}

function displayGeoRefLabel(geoRef: EntityGeoRef): string {
    const displayName = geoRef.source_meta?.display_name;

    return typeof displayName === 'string' && displayName.trim() !== ''
        ? displayName
        : `${geoRef.external_type}:${geoRef.external_id}`;
}