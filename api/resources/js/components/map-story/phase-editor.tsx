import { ChevronDown, ChevronRight, Crosshair, Plus } from 'lucide-react';
import { useState } from 'react';
import type { LngLat, StoryDoc } from '@/lib/map-story-doc';
import { useStoryEditor } from './editor-context';
import {
    CheckField,
    IconButton,
    NumberField,
    PointField,
    RemoveButton,
    SelectField,
    setKey,
    TextField,
} from './fields';

/** Rebuild `obj` with key `from` renamed to `to`, keeping its place. */
function renameEntry(obj: StoryDoc, from: string, to: string): StoryDoc {
    return Object.fromEntries(
        Object.entries(obj).map(([k, v]) => [k === from ? to : k, v]),
    );
}

/**
 * One phase of a step — the step itself or one of its beats: unit placements,
 * arrows (moves) and notes;
 * `change` edits it in a draft of the document.
 */
export function PhaseEditor({
    phase,
    change,
}: {
    phase: StoryDoc;
    change: (fn: (phase: StoryDoc) => void) => void;
}) {
    const { doc, vocab, pick } = useStoryEditor();
    const units: StoryDoc[] = Array.isArray(doc.units) ? doc.units : [];
    const sides: StoryDoc[] = Array.isArray(doc.sides) ? doc.sides : [];
    const unitOptions = units.map((u) => ({
        value: u.id as string,
        label: `${u.label} (${u.id})`,
    }));
    const sideOptions = sides.map((s) => ({
        value: s.id as string,
        label: s.name as string,
    }));
    const positions: StoryDoc =
        phase.positions && typeof phase.positions === 'object'
            ? phase.positions
            : {};
    const moves: StoryDoc[] = Array.isArray(phase.moves) ? phase.moves : [];
    const notes: StoryDoc[] = Array.isArray(phase.notes) ? phase.notes : [];
    const [open, setOpen] = useState<string | null>(null);
    const unplaced = units.filter((u) => !(u.id in positions));

    const place = (unit: string) => {
        // Until the pick lands it stays where it was (or, never placed, it has no point yet: an error).
        change((p) => {
            p.positions = { ...(p.positions ?? {}), [unit]: {} };
        });
        setOpen(unit);
        pick('point', (at) =>
            change(
                (p) =>
                    (p.positions[unit] = {
                        ...p.positions[unit],
                        at: at as LngLat,
                    }),
            ),
        );
    };

    return (
        <div className="space-y-3">
            <div className="space-y-1">
                <div className="flex items-center justify-between">
                    <h4 className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
                        Placements ({Object.keys(positions).length})
                    </h4>
                    <select
                        className="h-7 rounded-md border bg-background px-1 text-xs"
                        value=""
                        onChange={(e) =>
                            e.target.value && place(e.target.value)
                        }
                    >
                        <option value="">
                            + Place a unit (then click the preview)…
                        </option>
                        {unplaced.map((u) => (
                            <option key={u.id} value={u.id}>
                                {u.label} ({u.id})
                            </option>
                        ))}
                    </select>
                </div>
                {Object.entries(positions).map(
                    ([unitId, pl]: [string, StoryDoc]) => {
                        const unit = units.find((u) => u.id === unitId);
                        const isOpen = open === unitId;

                        return (
                            <div key={unitId} className="rounded border">
                                <div className="flex items-center gap-1 px-2 py-1 text-xs">
                                    <button
                                        type="button"
                                        className="flex min-w-0 flex-1 items-center gap-1 text-left"
                                        onClick={() =>
                                            setOpen(isOpen ? null : unitId)
                                        }
                                    >
                                        {isOpen ? (
                                            <ChevronDown className="size-3" />
                                        ) : (
                                            <ChevronRight className="size-3" />
                                        )}
                                        <span className="truncate font-medium">
                                            {unit?.label ?? unitId}
                                        </span>
                                        <span className="text-muted-foreground">
                                            {Array.isArray(pl.at)
                                                ? `@ ${pl.at.join(', ')}`
                                                : pl.with
                                                  ? `with ${pl.with}`
                                                  : 'stays'}
                                            {pl.state ? ` · ${pl.state}` : ''}
                                        </span>
                                    </button>
                                    <IconButton
                                        title="Pick its position on the preview"
                                        className="h-6"
                                        onClick={() =>
                                            pick('point', (at) =>
                                                change((p) => {
                                                    p.positions[unitId] = {
                                                        ...p.positions[unitId],
                                                        at: at as LngLat,
                                                    };
                                                    delete p.positions[unitId]
                                                        .with;
                                                }),
                                            )
                                        }
                                    >
                                        <Crosshair className="size-3" />
                                    </IconButton>
                                    <RemoveButton
                                        title="Remove this placement"
                                        onClick={() =>
                                            change(
                                                (p) =>
                                                    delete p.positions[unitId],
                                            )
                                        }
                                    />
                                </div>
                                {isOpen && (
                                    <div className="grid grid-cols-3 gap-2 border-t p-2">
                                        <SelectField
                                            label="Unit"
                                            value={unitId}
                                            options={unitOptions.filter(
                                                (o) =>
                                                    o.value === unitId ||
                                                    !(o.value in positions),
                                            )}
                                            empty={null}
                                            onChange={(v) =>
                                                v &&
                                                change(
                                                    (p) =>
                                                        (p.positions =
                                                            renameEntry(
                                                                p.positions,
                                                                unitId,
                                                                v,
                                                            )),
                                                )
                                            }
                                        />
                                        <PointField
                                            label="At"
                                            value={pl.at}
                                            className="col-span-2"
                                            onChange={(v) =>
                                                change((p) =>
                                                    setKey(
                                                        p.positions[unitId],
                                                        'at',
                                                        v,
                                                    ),
                                                )
                                            }
                                        />
                                        <SelectField
                                            label="State"
                                            value={pl.state}
                                            options={vocab.unit_states}
                                            onChange={(v) =>
                                                change((p) =>
                                                    setKey(
                                                        p.positions[unitId],
                                                        'state',
                                                        v,
                                                    ),
                                                )
                                            }
                                        />
                                        <NumberField
                                            label="Facing (°)"
                                            value={pl.facing}
                                            onChange={(v) =>
                                                change((p) =>
                                                    setKey(
                                                        p.positions[unitId],
                                                        'facing',
                                                        v,
                                                    ),
                                                )
                                            }
                                        />
                                        <SelectField
                                            label="Shape"
                                            value={pl.shape}
                                            options={vocab.shapes}
                                            onChange={(v) =>
                                                change((p) =>
                                                    setKey(
                                                        p.positions[unitId],
                                                        'shape',
                                                        v,
                                                    ),
                                                )
                                            }
                                        />
                                        <NumberField
                                            label="Width (m)"
                                            value={pl.width}
                                            onChange={(v) =>
                                                change((p) =>
                                                    setKey(
                                                        p.positions[unitId],
                                                        'width',
                                                        v,
                                                    ),
                                                )
                                            }
                                        />
                                        <NumberField
                                            label="Depth (m)"
                                            value={pl.depth}
                                            onChange={(v) =>
                                                change((p) =>
                                                    setKey(
                                                        p.positions[unitId],
                                                        'depth',
                                                        v,
                                                    ),
                                                )
                                            }
                                        />
                                        <TextField
                                            label="Label"
                                            value={pl.label}
                                            onChange={(v) =>
                                                change((p) =>
                                                    setKey(
                                                        p.positions[unitId],
                                                        'label',
                                                        v,
                                                    ),
                                                )
                                            }
                                        />
                                        <SelectField
                                            label="With (rides with)"
                                            value={pl.with}
                                            options={unitOptions.filter(
                                                (o) => o.value !== unitId,
                                            )}
                                            onChange={(v) =>
                                                change((p) =>
                                                    setKey(
                                                        p.positions[unitId],
                                                        'with',
                                                        v,
                                                    ),
                                                )
                                            }
                                        />
                                        <SelectField
                                            label="Into (merges)"
                                            value={pl.into}
                                            options={unitOptions.filter(
                                                (o) => o.value !== unitId,
                                            )}
                                            onChange={(v) =>
                                                change((p) =>
                                                    setKey(
                                                        p.positions[unitId],
                                                        'into',
                                                        v,
                                                    ),
                                                )
                                            }
                                        />
                                        {sideOptions.length > 0 && (
                                            <SelectField
                                                label="Captured by"
                                                value={pl.by}
                                                options={sideOptions}
                                                onChange={(v) =>
                                                    change((p) =>
                                                        setKey(
                                                            p.positions[unitId],
                                                            'by',
                                                            v,
                                                        ),
                                                    )
                                                }
                                            />
                                        )}
                                        <CheckField
                                            label="Conjectural"
                                            value={pl.conjectural}
                                            onChange={(v) =>
                                                change((p) =>
                                                    setKey(
                                                        p.positions[unitId],
                                                        'conjectural',
                                                        v,
                                                    ),
                                                )
                                            }
                                        />
                                    </div>
                                )}
                            </div>
                        );
                    },
                )}
            </div>

            <div className="space-y-1">
                <div className="flex items-center justify-between">
                    <h4 className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
                        Arrows ({moves.length})
                    </h4>
                    <IconButton
                        title="Add an arrow: click its points on the preview, double-click (or Enter) to finish"
                        className="h-7"
                        onClick={() =>
                            pick('path', (path) =>
                                change((p) => {
                                    const unit = units[0]?.id;
                                    p.moves = [
                                        ...(p.moves ?? []),
                                        unit
                                            ? {
                                                  unit,
                                                  type: vocab.military_kinds.includes(
                                                      doc.kind,
                                                  )
                                                      ? 'advance'
                                                      : 'march',
                                                  path,
                                              }
                                            : {
                                                  side: sides[0]?.id,
                                                  type: 'advance',
                                                  path,
                                              },
                                    ];
                                }),
                            )
                        }
                    >
                        <Plus className="size-3" /> Arrow
                    </IconButton>
                </div>
                {moves.map((m, k) => (
                    <div
                        key={k}
                        className="grid grid-cols-[1fr_1fr_1fr_auto] items-end gap-1 rounded border p-1.5"
                    >
                        <SelectField
                            label="Unit"
                            value={m.unit}
                            options={unitOptions}
                            empty="— (a side's arrow)"
                            onChange={(v) =>
                                change((p) => {
                                    setKey(p.moves[k], 'unit', v);

                                    if (v) {
                                        delete p.moves[k].side;
                                    }
                                })
                            }
                        />
                        {!m.unit && sideOptions.length > 0 ? (
                            <SelectField
                                label="Side"
                                value={m.side}
                                options={sideOptions}
                                onChange={(v) =>
                                    change((p) => setKey(p.moves[k], 'side', v))
                                }
                            />
                        ) : (
                            <SelectField
                                label="Target"
                                value={m.target}
                                options={unitOptions}
                                onChange={(v) =>
                                    change((p) =>
                                        setKey(p.moves[k], 'target', v),
                                    )
                                }
                            />
                        )}
                        <SelectField
                            label="Type"
                            value={m.type}
                            options={vocab.move_types}
                            empty={null}
                            onChange={(v) =>
                                change((p) => setKey(p.moves[k], 'type', v))
                            }
                        />
                        <RemoveButton
                            title="Remove this arrow"
                            onClick={() => change((p) => p.moves.splice(k, 1))}
                        />
                        <TextField
                            label="Label"
                            value={m.label}
                            onChange={(v) =>
                                change((p) => setKey(p.moves[k], 'label', v))
                            }
                        />
                        <div className="col-span-2 flex items-end gap-1 text-xs">
                            <span className="flex-1 pb-2 text-muted-foreground">
                                {Array.isArray(m.path)
                                    ? `${m.path.length} points`
                                    : 'no path'}
                            </span>
                            <IconButton
                                title="Redraw the path on the preview"
                                className="h-7"
                                onClick={() =>
                                    pick('path', (path) =>
                                        change((p) => (p.moves[k].path = path)),
                                    )
                                }
                            >
                                <Crosshair className="size-3" /> Redraw
                            </IconButton>
                            <CheckField
                                label="Arc"
                                value={m.arc}
                                onChange={(v) =>
                                    change((p) => setKey(p.moves[k], 'arc', v))
                                }
                            />
                            <CheckField
                                label="Conj."
                                value={m.conjectural}
                                onChange={(v) =>
                                    change((p) =>
                                        setKey(p.moves[k], 'conjectural', v),
                                    )
                                }
                            />
                        </div>
                    </div>
                ))}
            </div>

            <div className="space-y-1">
                <div className="flex items-center justify-between">
                    <h4 className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
                        Notes ({notes.length})
                    </h4>
                    <IconButton
                        title="Add a note: click where it goes on the preview"
                        className="h-7"
                        onClick={() =>
                            pick('point', (at) =>
                                change(
                                    (p) =>
                                        (p.notes = [
                                            ...(p.notes ?? []),
                                            { at, text: 'Note', kind: 'event' },
                                        ]),
                                ),
                            )
                        }
                    >
                        <Plus className="size-3" /> Note
                    </IconButton>
                </div>
                {notes.map((n, k) => (
                    <div
                        key={k}
                        className="grid grid-cols-[1fr_7rem_auto] items-end gap-1"
                    >
                        <TextField
                            label="Text"
                            value={n.text}
                            onChange={(v) =>
                                change((p) => (p.notes[k].text = v ?? ''))
                            }
                        />
                        <SelectField
                            label="Kind"
                            value={n.kind}
                            options={vocab.note_kinds}
                            onChange={(v) =>
                                change((p) => setKey(p.notes[k], 'kind', v))
                            }
                        />
                        <span className="flex">
                            <IconButton
                                title="Move it: click on the preview"
                                className="h-6 border-0 px-1"
                                onClick={() =>
                                    pick('point', (at) =>
                                        change((p) => (p.notes[k].at = at)),
                                    )
                                }
                            >
                                <Crosshair className="size-3" />
                            </IconButton>
                            <RemoveButton
                                title="Remove this note"
                                onClick={() =>
                                    change((p) => p.notes.splice(k, 1))
                                }
                            />
                        </span>
                    </div>
                ))}
            </div>
        </div>
    );
}
