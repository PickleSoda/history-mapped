import { lazy, Suspense, useState } from 'react';
import { Button } from '@/components/ui/button';
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog';
import { fromGeoJson, toGeoJson } from '@/lib/map-story-doc';

const MapEditor = lazy(() => import('@/components/map-editor'));

const HINTS = {
    at: 'Draw one point (the draw tools are at the top right). Delete the old one first if you draw a new one.',
    line: 'Draw one line; double-click to finish it. Select it to drag its vertices.',
    area: 'Draw one or more polygons (each one ring; holes are dropped). Select one to drag its vertices.',
} as const;

/**
 * Draw or redraw a feature's `at` / `line` / `area` on the admin's map editor
 * (MapLibre + Draw), zoomed to what is there now.
 */
export function GeometryDialog({
    open,
    title,
    kind,
    value,
    onClose,
    onSave,
}: {
    open: boolean;
    title: string;
    kind: 'at' | 'line' | 'area';
    value: unknown;
    onClose: () => void;
    onSave: (value: unknown) => void;
}) {
    const [geo, setGeo] = useState<Record<string, unknown> | null>(null);
    const initial = toGeoJson(kind, value);
    const next = geo === null ? null : fromGeoJson(kind, geo);

    return (
        <Dialog
            open={open}
            onOpenChange={(o) => {
                if (!o) {
                    setGeo(null);
                    onClose();
                }
            }}
        >
            <DialogContent className="max-w-4xl">
                <DialogHeader>
                    <DialogTitle>{title}</DialogTitle>
                    <DialogDescription>{HINTS[kind]}</DialogDescription>
                </DialogHeader>
                {open && (
                    <Suspense
                        fallback={
                            <div className="h-[480px] animate-pulse rounded-lg bg-muted" />
                        }
                    >
                        <MapEditor
                            only={kind === 'area' ? 'territory' : 'location'}
                            fitToGeometry={initial !== null}
                            geojson={kind === 'area' ? null : initial}
                            territoryGeojson={kind === 'area' ? initial : null}
                            onChange={(location, territory) =>
                                setGeo(kind === 'area' ? territory : location)
                            }
                        />
                    </Suspense>
                )}
                <DialogFooter>
                    <span className="mr-auto self-center text-xs text-muted-foreground">
                        {geo === null
                            ? 'No change yet'
                            : next === null
                              ? `No ${kind === 'at' ? 'point' : kind} drawn`
                              : 'Changed'}
                    </span>
                    <Button
                        variant="outline"
                        onClick={() => {
                            setGeo(null);
                            onClose();
                        }}
                    >
                        Cancel
                    </Button>
                    <Button
                        disabled={next === null}
                        onClick={() => {
                            onSave(next);
                            setGeo(null);
                            onClose();
                        }}
                    >
                        Use this {kind === 'at' ? 'point' : kind}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
