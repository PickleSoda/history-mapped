import {
    ChevronDown,
    ChevronRight,
    Crosshair,
    Map as MapIcon,
    Plus,
} from 'lucide-react';
import { useState } from 'react';
import {
    featuresKey,
    freeId,
    issuesFor,
    renameFeature,
} from '@/lib/map-story-doc';
import type { StoryDoc } from '@/lib/map-story-doc';
import { useStoryEditor } from './editor-context';
import { EntityRefField } from './entity-ref-field';
import {
    CheckField,
    IconButton,
    IdField,
    ListField,
    NumberField,
    Section,
    SelectField,
    setKey,
    TextField,
} from './fields';
import { GeometryDialog } from './geometry-dialog';

function geometrySummary(kind: 'at' | 'line' | 'area', value: unknown): string {
    if (!Array.isArray(value) || value.length === 0) {
        return 'none yet';
    }

    if (kind === 'at') {
        return (value as number[]).join(', ');
    }

    if (kind === 'line') {
        return `${value.length} points`;
    }

    return Array.isArray(value[0]?.[0])
        ? `${value.length} rings`
        : `${value.length} points`;
}

/** The persistent features (`features`, or the older `terrain`): kind, geometry, links and the flags. */
export function FeaturesTab() {
    const { doc, edit, replace, vocab, errors, pick } = useStoryEditor();
    const key = featuresKey(doc);
    const features: StoryDoc[] = Array.isArray(doc[key]) ? doc[key] : [];
    const ids = features.map((f) => f.id as string);
    const sides: StoryDoc[] = Array.isArray(doc.sides) ? doc.sides : [];
    const [open, setOpen] = useState<string | null>(null);
    const [drawing, setDrawing] = useState<number | null>(null);
    const v3 = (doc.schema ?? 1) >= 3;
    const kinds = Object.keys(vocab.feature_kinds);
    const drawn = drawing !== null ? features[drawing] : null;
    const drawnKind = drawn ? vocab.feature_kinds[drawn.kind] : null;

    const add = (kind: string) =>
        edit((d) => {
            const id = freeId(kind, ids);
            const geometry = vocab.feature_kinds[kind];
            d[key] = [
                ...features,
                {
                    id,
                    kind,
                    label: 'New feature',
                    ...(kind === 'route' ? { route_kind: 'trade' } : {}),
                    ...(kind === 'region' ? { region_kind: 'extent' } : {}),
                },
            ];
            setOpen(id);

            if (geometry === 'at') {
                pick('point', (p) =>
                    edit((dd) => (dd[key][features.length].at = p)),
                );
            } else if (geometry === 'line') {
                pick('path', (p) =>
                    edit((dd) => (dd[key][features.length].line = p)),
                );
            } else {
                setDrawing(features.length);
            }
        });

    return (
        <div className="space-y-3">
            <Section
                title={`Features (${features.length})${key === 'terrain' ? ' — stored as terrain' : ''}`}
                actions={
                    <select
                        className="h-8 rounded-md border bg-background px-2 text-xs"
                        value=""
                        onChange={(e) => e.target.value && add(e.target.value)}
                    >
                        <option value="">+ Add a feature…</option>
                        {kinds.map((k) => (
                            <option key={k} value={k}>
                                {k.replace(/_/g, ' ')} ({vocab.feature_kinds[k]}
                                )
                            </option>
                        ))}
                    </select>
                }
            >
                <p className="text-xs text-muted-foreground">
                    Fixed through the story: terrain, places, routes, regions. A
                    step can change each one under Steps → features.
                </p>
                {features.map((f, i) => {
                    const geometry = vocab.feature_kinds[f.kind] ?? 'at';
                    const issues = issuesFor(
                        errors,
                        (t) => t.tab === 'features' && t.index === i,
                    );

                    return (
                        <div key={i} className="rounded-md border">
                            <button
                                type="button"
                                className="flex w-full items-center gap-2 px-2 py-1.5 text-left text-sm"
                                onClick={() =>
                                    setOpen(open === f.id ? null : f.id)
                                }
                            >
                                {open === f.id ? (
                                    <ChevronDown className="size-3.5" />
                                ) : (
                                    <ChevronRight className="size-3.5" />
                                )}
                                <span className="font-medium">{f.label}</span>
                                <span className="text-xs text-muted-foreground">
                                    {String(f.kind).replace(/_/g, ' ')}
                                </span>
                                <span className="font-mono text-xs text-muted-foreground">
                                    {f.id}
                                </span>
                                {issues.length > 0 && (
                                    <span className="ml-auto text-xs text-destructive">
                                        {issues.length} error(s)
                                    </span>
                                )}
                            </button>
                            {open === f.id && (
                                <div className="grid grid-cols-2 gap-2 border-t p-2">
                                    <IdField
                                        value={f.id}
                                        taken={ids}
                                        onRename={(to) => {
                                            replace(
                                                renameFeature(doc, f.id, to),
                                            );
                                            setOpen(to);
                                        }}
                                    />
                                    <SelectField
                                        label="Kind"
                                        value={f.kind}
                                        options={kinds.filter(
                                            (k) =>
                                                vocab.feature_kinds[k] ===
                                                geometry,
                                        )}
                                        empty={null}
                                        onChange={(v) =>
                                            edit((d) => {
                                                const ft = d[key][i];
                                                ft.kind = v;
                                                setKey(
                                                    ft,
                                                    'route_kind',
                                                    v === 'route'
                                                        ? (ft.route_kind ??
                                                              'trade')
                                                        : undefined,
                                                );
                                                setKey(
                                                    ft,
                                                    'region_kind',
                                                    v === 'region'
                                                        ? (ft.region_kind ??
                                                              'extent')
                                                        : undefined,
                                                );
                                            })
                                        }
                                    />
                                    <TextField
                                        label="Label"
                                        value={f.label}
                                        className="col-span-2"
                                        onChange={(v) =>
                                            edit((d) =>
                                                setKey(d[key][i], 'label', v),
                                            )
                                        }
                                    />
                                    <div className="col-span-2 flex items-end gap-1">
                                        <div className="min-w-0 flex-1 text-xs">
                                            <span className="font-medium text-muted-foreground">
                                                Geometry ({geometry}):{' '}
                                            </span>
                                            <span className="font-mono">
                                                {geometrySummary(
                                                    geometry,
                                                    f[geometry],
                                                )}
                                            </span>
                                        </div>
                                        {geometry !== 'area' && (
                                            <IconButton
                                                title="Pick on the preview"
                                                onClick={() =>
                                                    pick(
                                                        geometry === 'at'
                                                            ? 'point'
                                                            : 'path',
                                                        (p) =>
                                                            edit(
                                                                (d) =>
                                                                    (d[key][i][
                                                                        geometry
                                                                    ] = p),
                                                            ),
                                                    )
                                                }
                                            >
                                                <Crosshair className="size-3.5" />{' '}
                                                Pick
                                            </IconButton>
                                        )}
                                        <IconButton
                                            title="Draw on the map editor"
                                            onClick={() => setDrawing(i)}
                                        >
                                            <MapIcon className="size-3.5" />{' '}
                                            Draw
                                        </IconButton>
                                    </div>
                                    {f.kind === 'route' && (
                                        <SelectField
                                            label="Route kind"
                                            value={f.route_kind}
                                            options={vocab.route_kinds}
                                            empty={null}
                                            onChange={(v) =>
                                                edit((d) =>
                                                    setKey(
                                                        d[key][i],
                                                        'route_kind',
                                                        v,
                                                    ),
                                                )
                                            }
                                        />
                                    )}
                                    {f.kind === 'region' && (
                                        <SelectField
                                            label="Region kind"
                                            value={f.region_kind}
                                            options={vocab.region_kinds}
                                            empty={null}
                                            onChange={(v) =>
                                                edit((d) =>
                                                    setKey(
                                                        d[key][i],
                                                        'region_kind',
                                                        v,
                                                    ),
                                                )
                                            }
                                        />
                                    )}
                                    {sides.length > 0 && (
                                        <SelectField
                                            label="Side (its colour)"
                                            value={f.side}
                                            options={sides.map((s) => ({
                                                value: s.id,
                                                label: s.name,
                                            }))}
                                            onChange={(v) =>
                                                edit((d) =>
                                                    setKey(
                                                        d[key][i],
                                                        'side',
                                                        v,
                                                    ),
                                                )
                                            }
                                        />
                                    )}
                                    {v3 && (
                                        <>
                                            <EntityRefField
                                                label="Entity (a city, a polity…)"
                                                className="col-span-2"
                                                value={f.entity}
                                                onChange={(v) =>
                                                    edit((d) =>
                                                        setKey(
                                                            d[key][i],
                                                            'entity',
                                                            v,
                                                        ),
                                                    )
                                                }
                                            />
                                            {[
                                                'route',
                                                'port',
                                                'market',
                                                'city',
                                            ].includes(f.kind) && (
                                                <ListField
                                                    label="Goods"
                                                    value={f.goods}
                                                    className="col-span-2"
                                                    onChange={(v) =>
                                                        edit((d) =>
                                                            setKey(
                                                                d[key][i],
                                                                'goods',
                                                                v,
                                                            ),
                                                        )
                                                    }
                                                />
                                            )}
                                            <NumberField
                                                label="Value (number ≥ 0)"
                                                value={f.value_n}
                                                onChange={(v) =>
                                                    edit((d) =>
                                                        setKey(
                                                            d[key][i],
                                                            'value_n',
                                                            v,
                                                        ),
                                                    )
                                                }
                                            />
                                            <TextField
                                                label="Value label"
                                                value={f.value_label}
                                                onChange={(v) =>
                                                    edit((d) =>
                                                        setKey(
                                                            d[key][i],
                                                            'value_label',
                                                            v,
                                                        ),
                                                    )
                                                }
                                            />
                                            <NumberField
                                                label="Intensity (0–1)"
                                                value={f.intensity}
                                                onChange={(v) =>
                                                    edit((d) =>
                                                        setKey(
                                                            d[key][i],
                                                            'intensity',
                                                            v,
                                                        ),
                                                    )
                                                }
                                            />
                                        </>
                                    )}
                                    <div className="col-span-2 flex flex-wrap gap-3">
                                        <CheckField
                                            label="Conjectural"
                                            value={f.conjectural}
                                            onChange={(v) =>
                                                edit((d) =>
                                                    setKey(
                                                        d[key][i],
                                                        'conjectural',
                                                        v,
                                                    ),
                                                )
                                            }
                                        />
                                        {v3 && (
                                            <CheckField
                                                label="Bidirectional"
                                                value={f.bidirectional}
                                                onChange={(v) =>
                                                    edit((d) =>
                                                        setKey(
                                                            d[key][i],
                                                            'bidirectional',
                                                            v,
                                                        ),
                                                    )
                                                }
                                            />
                                        )}
                                        {v3 && (
                                            <label className="flex items-center gap-1.5 text-xs">
                                                <input
                                                    type="checkbox"
                                                    checked={f.active !== false}
                                                    onChange={(e) =>
                                                        edit((d) =>
                                                            setKey(
                                                                d[key][i],
                                                                'active',
                                                                e.target.checked
                                                                    ? undefined
                                                                    : false,
                                                            ),
                                                        )
                                                    }
                                                />
                                                Active from the start
                                            </label>
                                        )}
                                    </div>
                                    <div className="col-span-2 flex justify-between">
                                        <p className="text-xs text-destructive">
                                            {issues.join(' · ')}
                                        </p>
                                        <IconButton
                                            title="Remove this feature and its per-step state"
                                            className="text-destructive"
                                            onClick={() =>
                                                edit((d) => {
                                                    d[key].splice(i, 1);

                                                    for (const step of d.steps ??
                                                        []) {
                                                        delete step.features?.[
                                                            f.id
                                                        ];
                                                        delete step
                                                            .terrain_state?.[
                                                            f.id
                                                        ];
                                                    }
                                                })
                                            }
                                        >
                                            Remove feature
                                        </IconButton>
                                    </div>
                                </div>
                            )}
                        </div>
                    );
                })}
                {features.length === 0 && (
                    <IconButton
                        title="Add a place"
                        onClick={() => add(v3 ? 'city' : 'town')}
                    >
                        <Plus className="size-3.5" /> Add the first feature
                    </IconButton>
                )}
            </Section>
            {drawn && drawnKind && (
                <GeometryDialog
                    open
                    title={`${drawn.label} — ${drawnKind}`}
                    kind={drawnKind}
                    value={drawn[drawnKind]}
                    onClose={() => setDrawing(null)}
                    onSave={(value) =>
                        edit((d) => (d[key][drawing!][drawnKind] = value))
                    }
                />
            )}
        </div>
    );
}
