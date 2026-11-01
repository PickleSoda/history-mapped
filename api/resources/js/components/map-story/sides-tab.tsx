import { ChevronDown, ChevronRight, Plus } from 'lucide-react';
import { useState } from 'react';
import { freeId, issuesFor, renameSide, renameUnit } from '@/lib/map-story-doc';
import type { StoryDoc } from '@/lib/map-story-doc';
import { useStoryEditor } from './editor-context';
import { EntityRefField } from './entity-ref-field';
import {
    IconButton,
    IdField,
    RemoveButton,
    Section,
    SelectField,
    setKey,
    TextField,
} from './fields';

/** The sides (with commanders and contingents) and the units. */
export function SidesTab() {
    const { doc, edit, replace, vocab, errors } = useStoryEditor();
    const sides: StoryDoc[] = Array.isArray(doc.sides) ? doc.sides : [];
    const units: StoryDoc[] = Array.isArray(doc.units) ? doc.units : [];
    const sideIds = sides.map((s) => s.id as string);
    const unitIds = units.map((u) => u.id as string);
    const [open, setOpen] = useState<string | null>(null);
    const sideIssues = (i?: number) =>
        issuesFor(
            errors,
            (t) => t.tab === 'sides' && t.list === 'sides' && t.index === i,
        );
    const unitIssues = (i?: number) =>
        issuesFor(
            errors,
            (t) => t.tab === 'sides' && t.list === 'units' && t.index === i,
        );
    const military = vocab.military_kinds.includes(doc.kind);

    return (
        <div className="space-y-3">
            <Section
                title={`Sides (${sides.length})`}
                actions={
                    <IconButton
                        title="Add a side"
                        onClick={() =>
                            edit((d) => {
                                const id = freeId('side', sideIds);
                                d.sides = [
                                    ...sides,
                                    { id, name: 'New side', color: '#555555' },
                                ];
                                setOpen(`side:${id}`);
                            })
                        }
                    >
                        <Plus className="size-3.5" /> Side
                    </IconButton>
                }
            >
                {!military && sides.length === 0 && (
                    <p className="text-xs text-muted-foreground">
                        No sides: fine for a{' '}
                        {String(doc.kind).replace(/_/g, ' ')}. Units then need
                        no side.
                    </p>
                )}
                {sideIssues(undefined).length > 0 && (
                    <p className="text-xs text-destructive">
                        {sideIssues(undefined).join(' · ')}
                    </p>
                )}
                {sides.map((side, i) => {
                    const key = `side:${side.id}`;
                    const issues = sideIssues(i);

                    return (
                        <div key={i} className="rounded-md border">
                            <button
                                type="button"
                                className="flex w-full items-center gap-2 px-2 py-1.5 text-left text-sm"
                                onClick={() =>
                                    setOpen(open === key ? null : key)
                                }
                            >
                                {open === key ? (
                                    <ChevronDown className="size-3.5" />
                                ) : (
                                    <ChevronRight className="size-3.5" />
                                )}
                                <span
                                    className="size-3 rounded-sm"
                                    style={{ background: side.color }}
                                />
                                <span className="font-medium">{side.name}</span>
                                <span className="font-mono text-xs text-muted-foreground">
                                    {side.id}
                                </span>
                                {issues.length > 0 && (
                                    <span className="ml-auto text-xs text-destructive">
                                        {issues.length} error(s)
                                    </span>
                                )}
                            </button>
                            {open === key && (
                                <div className="grid grid-cols-2 gap-2 border-t p-2">
                                    <IdField
                                        value={side.id}
                                        taken={sideIds}
                                        onRename={(to) => {
                                            replace(
                                                renameSide(doc, side.id, to),
                                            );
                                            setOpen(`side:${to}`);
                                        }}
                                    />
                                    <div className="flex items-end gap-1">
                                        <TextField
                                            label="Name"
                                            value={side.name}
                                            className="flex-1"
                                            onChange={(v) =>
                                                edit(
                                                    (d) =>
                                                        (d.sides[i].name =
                                                            v ?? ''),
                                                )
                                            }
                                        />
                                        <input
                                            type="color"
                                            title="Colour"
                                            className="h-8 w-10 rounded border"
                                            value={
                                                /^#[0-9a-f]{6}$/i.test(
                                                    side.color ?? '',
                                                )
                                                    ? side.color
                                                    : '#555555'
                                            }
                                            onChange={(e) =>
                                                edit(
                                                    (d) =>
                                                        (d.sides[i].color =
                                                            e.target.value),
                                                )
                                            }
                                        />
                                    </div>
                                    <EntityRefField
                                        label="Polity"
                                        className="col-span-2"
                                        value={side.polity}
                                        onChange={(v) =>
                                            edit((d) =>
                                                setKey(d.sides[i], 'polity', v),
                                            )
                                        }
                                    />
                                    <TextField
                                        label="Strength"
                                        value={side.strength}
                                        onChange={(v) =>
                                            edit((d) =>
                                                setKey(
                                                    d.sides[i],
                                                    'strength',
                                                    v,
                                                ),
                                            )
                                        }
                                    />
                                    <TextField
                                        label="Losses"
                                        value={side.losses}
                                        onChange={(v) =>
                                            edit((d) =>
                                                setKey(d.sides[i], 'losses', v),
                                            )
                                        }
                                    />
                                    <SubList
                                        title="Commanders"
                                        items={side.commanders}
                                        blank={{ name: '' }}
                                        onChange={(next) =>
                                            edit((d) =>
                                                setKey(
                                                    d.sides[i],
                                                    'commanders',
                                                    next.length
                                                        ? next
                                                        : undefined,
                                                ),
                                            )
                                        }
                                        render={(c, set) => (
                                            <>
                                                <EntityRefField
                                                    label="Commander"
                                                    value={c}
                                                    className="flex-1"
                                                    onChange={(v) =>
                                                        set({
                                                            ...(v ?? {}),
                                                            ...(c.role
                                                                ? {
                                                                      role: c.role,
                                                                  }
                                                                : {}),
                                                        })
                                                    }
                                                />
                                                <TextField
                                                    label="Role"
                                                    value={c.role}
                                                    className="w-32"
                                                    onChange={(v) =>
                                                        set({ ...c, role: v })
                                                    }
                                                />
                                            </>
                                        )}
                                    />
                                    <SubList
                                        title="Contingents"
                                        items={side.contingents}
                                        blank={{
                                            id: freeId(
                                                'contingent',
                                                (side.contingents ?? []).map(
                                                    (c: StoryDoc) => c.id,
                                                ),
                                            ),
                                            name: '',
                                        }}
                                        onChange={(next) =>
                                            edit((d) =>
                                                setKey(
                                                    d.sides[i],
                                                    'contingents',
                                                    next.length
                                                        ? next
                                                        : undefined,
                                                ),
                                            )
                                        }
                                        render={(c, set) => (
                                            <>
                                                <TextField
                                                    label="Id"
                                                    value={c.id}
                                                    className="w-32"
                                                    onChange={(v) =>
                                                        set({
                                                            ...c,
                                                            id: v ?? '',
                                                        })
                                                    }
                                                />
                                                <TextField
                                                    label="Name"
                                                    value={c.name}
                                                    className="flex-1"
                                                    onChange={(v) =>
                                                        set({
                                                            ...c,
                                                            name: v ?? '',
                                                        })
                                                    }
                                                />
                                            </>
                                        )}
                                    />
                                    <div className="col-span-2 flex justify-between">
                                        <IssuesLine messages={issues} />
                                        <IconButton
                                            title="Remove this side"
                                            className="text-destructive"
                                            onClick={() =>
                                                edit((d) =>
                                                    d.sides.splice(i, 1),
                                                )
                                            }
                                        >
                                            Remove side
                                        </IconButton>
                                    </div>
                                </div>
                            )}
                        </div>
                    );
                })}
            </Section>

            <Section
                title={`Units (${units.length})`}
                actions={
                    <IconButton
                        title="Add a unit"
                        onClick={() =>
                            edit((d) => {
                                const side = sideIds[0];
                                const id = freeId(
                                    side ? `${side}-unit` : 'unit',
                                    unitIds,
                                );
                                const unit: StoryDoc = {
                                    id,
                                    ...(side ? { side } : {}),
                                    kind: military ? 'infantry' : 'group',
                                    label: 'New unit',
                                };
                                d.units = [...units, unit];
                                setOpen(`unit:${id}`);
                            })
                        }
                    >
                        <Plus className="size-3.5" /> Unit
                    </IconButton>
                }
            >
                {unitIssues(undefined).length > 0 && (
                    <p className="text-xs text-destructive">
                        {unitIssues(undefined).join(' · ')}
                    </p>
                )}
                {units.map((unit, i) => {
                    const key = `unit:${unit.id}`;
                    const issues = unitIssues(i);
                    const side = sides.find((s) => s.id === unit.side);
                    const contingents: StoryDoc[] = side?.contingents ?? [];

                    return (
                        <div key={i} className="rounded-md border">
                            <button
                                type="button"
                                className="flex w-full items-center gap-2 px-2 py-1.5 text-left text-sm"
                                onClick={() =>
                                    setOpen(open === key ? null : key)
                                }
                            >
                                {open === key ? (
                                    <ChevronDown className="size-3.5" />
                                ) : (
                                    <ChevronRight className="size-3.5" />
                                )}
                                <span
                                    className="size-3 rounded-full"
                                    style={{
                                        background: side?.color ?? '#888',
                                    }}
                                />
                                <span className="font-medium">
                                    {unit.label}
                                </span>
                                <span className="text-xs text-muted-foreground">
                                    {String(unit.kind ?? '').replace(/_/g, ' ')}
                                </span>
                                <span className="font-mono text-xs text-muted-foreground">
                                    {unit.id}
                                </span>
                                {issues.length > 0 && (
                                    <span className="ml-auto text-xs text-destructive">
                                        {issues.length} error(s)
                                    </span>
                                )}
                            </button>
                            {open === key && (
                                <div className="grid grid-cols-2 gap-2 border-t p-2">
                                    <IdField
                                        value={unit.id}
                                        taken={unitIds}
                                        onRename={(to) => {
                                            replace(
                                                renameUnit(doc, unit.id, to),
                                            );
                                            setOpen(`unit:${to}`);
                                        }}
                                    />
                                    <TextField
                                        label="Label"
                                        value={unit.label}
                                        onChange={(v) =>
                                            edit(
                                                (d) =>
                                                    (d.units[i].label =
                                                        v ?? ''),
                                            )
                                        }
                                    />
                                    <SelectField
                                        label="Side"
                                        value={unit.side}
                                        options={sides.map((s) => ({
                                            value: s.id,
                                            label: s.name,
                                        }))}
                                        empty={
                                            sides.length === 0 ? 'none' : '—'
                                        }
                                        onChange={(v) =>
                                            edit((d) =>
                                                setKey(d.units[i], 'side', v),
                                            )
                                        }
                                    />
                                    <SelectField
                                        label="Kind"
                                        value={unit.kind}
                                        options={vocab.unit_kinds}
                                        empty={null}
                                        onChange={(v) =>
                                            edit((d) =>
                                                setKey(d.units[i], 'kind', v),
                                            )
                                        }
                                    />
                                    {contingents.length > 0 && (
                                        <SelectField
                                            label="Contingent"
                                            value={unit.contingent}
                                            options={contingents.map((c) => ({
                                                value: c.id,
                                                label: c.name || c.id,
                                            }))}
                                            onChange={(v) =>
                                                edit((d) =>
                                                    setKey(
                                                        d.units[i],
                                                        'contingent',
                                                        v,
                                                    ),
                                                )
                                            }
                                        />
                                    )}
                                    <EntityRefField
                                        label="Wikidata (a person or a named unit)"
                                        needsName={false}
                                        value={
                                            unit.wikidata
                                                ? { wikidata: unit.wikidata }
                                                : undefined
                                        }
                                        onChange={(v) =>
                                            edit((d) =>
                                                setKey(
                                                    d.units[i],
                                                    'wikidata',
                                                    v?.wikidata,
                                                ),
                                            )
                                        }
                                    />
                                    <TextField
                                        label="Strength"
                                        value={unit.strength}
                                        onChange={(v) =>
                                            edit((d) =>
                                                setKey(
                                                    d.units[i],
                                                    'strength',
                                                    v,
                                                ),
                                            )
                                        }
                                    />
                                    <TextField
                                        label="Commander"
                                        value={unit.commander}
                                        onChange={(v) =>
                                            edit((d) =>
                                                setKey(
                                                    d.units[i],
                                                    'commander',
                                                    v,
                                                ),
                                            )
                                        }
                                    />
                                    <TextField
                                        label="Note"
                                        value={unit.note}
                                        rows={2}
                                        className="col-span-2"
                                        onChange={(v) =>
                                            edit((d) =>
                                                setKey(d.units[i], 'note', v),
                                            )
                                        }
                                    />
                                    <div className="col-span-2 flex justify-between">
                                        <IssuesLine messages={issues} />
                                        <IconButton
                                            title="Remove this unit (its placements and arrows stay until you remove them)"
                                            className="text-destructive"
                                            onClick={() =>
                                                edit((d) =>
                                                    d.units.splice(i, 1),
                                                )
                                            }
                                        >
                                            Remove unit
                                        </IconButton>
                                    </div>
                                </div>
                            )}
                        </div>
                    );
                })}
            </Section>
        </div>
    );
}

function IssuesLine({ messages }: { messages: string[] }) {
    return <p className="text-xs text-destructive">{messages.join(' · ')}</p>;
}

/** A small editable list of objects inside a side (commanders, contingents). */
function SubList({
    title,
    items,
    blank,
    onChange,
    render,
}: {
    title: string;
    items: unknown;
    blank: StoryDoc;
    onChange: (next: StoryDoc[]) => void;
    render: (item: StoryDoc, set: (next: StoryDoc) => void) => React.ReactNode;
}) {
    const list: StoryDoc[] = Array.isArray(items) ? items : [];

    return (
        <div className="col-span-2 space-y-1">
            <div className="flex items-center justify-between text-xs font-medium text-muted-foreground">
                {title}
                <IconButton
                    title={`Add to ${title.toLowerCase()}`}
                    className="h-6"
                    onClick={() => onChange([...list, blank])}
                >
                    <Plus className="size-3" />
                </IconButton>
            </div>
            {list.map((item, k) => (
                <div key={k} className="flex items-end gap-1">
                    {render(item, (next) => {
                        const copy = [...list];
                        const clean: StoryDoc = {};

                        for (const [key, v] of Object.entries(next)) {
                            if (v !== undefined && v !== '') {
                                clean[key] = v;
                            }
                        }

                        copy[k] = clean;
                        onChange(copy);
                    })}
                    <RemoveButton
                        title="Remove"
                        onClick={() => onChange(list.filter((_, j) => j !== k))}
                    />
                </div>
            ))}
        </div>
    );
}
