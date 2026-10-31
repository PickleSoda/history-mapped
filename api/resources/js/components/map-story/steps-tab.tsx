import {
    ArrowDown,
    ArrowUp,
    Copy,
    Map as MapIcon,
    Plus,
    Trash2,
    Video,
} from 'lucide-react';
import { useState } from 'react';
import {
    featuresKey,
    freeId,
    issuesFor,
    phasesOf,
    stepStateKey,
} from '@/lib/map-story-doc';
import type { StoryDoc } from '@/lib/map-story-doc';
import { useStoryEditor } from './editor-context';
import { EntityRefField } from './entity-ref-field';
import {
    CheckField,
    IconButton,
    IdField,
    NumberField,
    RemoveButton,
    Section,
    SelectField,
    setKey,
    TextField,
} from './fields';
import { GeometryDialog } from './geometry-dialog';
import { PhaseEditor } from './phase-editor';

const MONTHS = [
    'Jan',
    'Feb',
    'Mar',
    'Apr',
    'May',
    'Jun',
    'Jul',
    'Aug',
    'Sep',
    'Oct',
    'Nov',
    'Dec',
];

/** A date spec {year, month?, day?}: three small inputs. */
function DateSpec({
    label,
    value,
    onChange,
}: {
    label: string;
    value: StoryDoc | undefined;
    onChange: (value: StoryDoc | undefined) => void;
}) {
    const set = (key: 'year' | 'month' | 'day', v: number | undefined) => {
        const next: StoryDoc = { ...(value ?? {}) };
        setKey(next, key, v);

        if (key === 'month' && v === undefined) {
            delete next.day;
        }

        onChange(
            next.year === undefined && Object.keys(next).length === 0
                ? undefined
                : next,
        );
    };

    return (
        <div className="grid grid-cols-[1fr_5rem_4rem] items-end gap-1">
            <NumberField
                label={label}
                value={value?.year}
                step="1"
                placeholder="year"
                onChange={(v) => set('year', v)}
            />
            <SelectField
                label="Month"
                value={value?.month ? String(value.month) : undefined}
                options={MONTHS.map((m, i) => ({
                    value: String(i + 1),
                    label: m,
                }))}
                onChange={(v) => set('month', v ? Number(v) : undefined)}
            />
            <NumberField
                label="Day"
                value={value?.day}
                step="1"
                onChange={(v) => set('day', v)}
            />
        </div>
    );
}

/**
 * The steps: a strip to pick, add, reorder and remove them (in step with the
 * preview), and the picked step's text, date, entry, conditions, focus,
 * camera, placements / arrows / notes, beats, feature state and entities.
 */
export function StepsTab() {
    const {
        doc,
        edit,
        vocab,
        errors,
        warnings,
        entries,
        step: index,
        setStep,
        requestCamera,
    } = useStoryEditor();
    const steps: StoryDoc[] = Array.isArray(doc.steps) ? doc.steps : [];
    const step = steps[index];
    const v3 = (doc.schema ?? 1) >= 3;
    const v2 = (doc.schema ?? 1) >= 2;
    const ids = steps.map((s) => s.id as string);
    const units: StoryDoc[] = Array.isArray(doc.units) ? doc.units : [];
    const sides: StoryDoc[] = Array.isArray(doc.sides) ? doc.sides : [];
    const features: StoryDoc[] = Array.isArray(doc[featuresKey(doc)])
        ? doc[featuresKey(doc)]
        : [];
    const at = (i: number) => (fn: (s: StoryDoc) => void) =>
        edit((d) => fn(d.steps[i]));
    const issuesOf = (s: StoryDoc) =>
        issuesFor(errors, (t) => t.tab === 'steps' && t.step === s.id);
    const warningsOf = (s: StoryDoc) =>
        issuesFor(warnings, (t) => t.tab === 'steps' && t.step === s.id);

    const add = (copy: boolean) =>
        edit((d) => {
            const id = freeId(`s${steps.length + 1}`, ids);
            const base: StoryDoc =
                copy && step
                    ? {
                          ...JSON.parse(JSON.stringify(step)),
                          id,
                          title: `${step.title} (copy)`,
                      }
                    : {
                          id,
                          title: 'New step',
                          narrative: 'To be written.',
                          positions: {},
                          moves: [],
                          notes: [],
                      };
            d.steps.splice(index + 1, 0, base);
            setStep(index + 1);
        });

    const move = (from: number, to: number) =>
        edit((d) => {
            const [s] = d.steps.splice(from, 1);
            d.steps.splice(to, 0, s);
            setStep(to);
        });

    return (
        <div className="space-y-3">
            <Section
                title={`Steps (${steps.length})`}
                actions={
                    <>
                        <IconButton
                            title="Add a step after this one"
                            onClick={() => add(false)}
                        >
                            <Plus className="size-3.5" /> Step
                        </IconButton>
                        <IconButton
                            title="Duplicate this step"
                            disabled={!step}
                            onClick={() => add(true)}
                        >
                            <Copy className="size-3.5" />
                        </IconButton>
                        <IconButton
                            title="Move earlier"
                            disabled={index === 0}
                            onClick={() => move(index, index - 1)}
                        >
                            <ArrowUp className="size-3.5" />
                        </IconButton>
                        <IconButton
                            title="Move later"
                            disabled={index >= steps.length - 1}
                            onClick={() => move(index, index + 1)}
                        >
                            <ArrowDown className="size-3.5" />
                        </IconButton>
                        <IconButton
                            title="Remove this step"
                            disabled={steps.length <= 1}
                            className="text-destructive"
                            onClick={() =>
                                edit((d) => {
                                    d.steps.splice(index, 1);
                                    setStep(Math.max(0, index - 1));
                                })
                            }
                        >
                            <Trash2 className="size-3.5" />
                        </IconButton>
                    </>
                }
            >
                <input
                    type="range"
                    min={0}
                    max={Math.max(0, steps.length - 1)}
                    value={index}
                    className="w-full"
                    aria-label="Step"
                    onChange={(e) => setStep(Number(e.target.value))}
                />
                <ol className="flex flex-wrap gap-1">
                    {steps.map((s, i) => {
                        const bad = issuesOf(s).length > 0;

                        return (
                            <li key={`${s.id}-${i}`}>
                                <button
                                    type="button"
                                    title={s.title}
                                    onClick={() => setStep(i)}
                                    className={`rounded border px-1.5 py-0.5 font-mono text-xs ${i === index ? 'border-primary bg-primary text-primary-foreground' : bad ? 'border-destructive text-destructive' : 'hover:bg-muted'}`}
                                >
                                    {i + 1}
                                </button>
                            </li>
                        );
                    })}
                </ol>
            </Section>

            {step && (
                <>
                    <Section title={`Step ${index + 1}: ${step.title ?? ''}`}>
                        {issuesOf(step).length > 0 && (
                            <ul className="list-disc pl-4 text-xs text-destructive">
                                {issuesOf(step).map((m) => (
                                    <li key={m}>{m}</li>
                                ))}
                            </ul>
                        )}
                        {warningsOf(step).length > 0 && (
                            <ul className="list-disc pl-4 text-xs text-amber-600">
                                {warningsOf(step).map((m) => (
                                    <li key={m}>{m}</li>
                                ))}
                            </ul>
                        )}
                        <div className="grid grid-cols-3 gap-2">
                            <IdField
                                value={step.id}
                                taken={ids}
                                onRename={(to) => at(index)((s) => (s.id = to))}
                            />
                            <TextField
                                label="Title"
                                value={step.title}
                                className="col-span-2"
                                limits={vocab.text_limits['step.title']}
                                onChange={(v) =>
                                    at(index)((s) => (s.title = v ?? ''))
                                }
                            />
                            <TextField
                                label="Time (shown as written)"
                                value={step.time}
                                onChange={(v) =>
                                    at(index)((s) => setKey(s, 'time', v))
                                }
                            />
                            {v2 && (
                                <SelectField
                                    label="Light"
                                    value={step.light}
                                    options={vocab.lights}
                                    onChange={(v) =>
                                        at(index)((s) => setKey(s, 'light', v))
                                    }
                                />
                            )}
                            {v3 && doc.chronicle && (
                                <SelectField
                                    label="Chronicle entry"
                                    value={
                                        typeof step.entry === 'number'
                                            ? String(step.entry)
                                            : undefined
                                    }
                                    options={entries.map((e) => ({
                                        value: String(e.sequence_order),
                                        label: `#${e.sequence_order}${e.start_year != null ? ` (${e.start_year})` : ''} ${e.text ?? ''}`.slice(
                                            0,
                                            70,
                                        ),
                                    }))}
                                    onChange={(v) =>
                                        at(index)((s) =>
                                            setKey(
                                                s,
                                                'entry',
                                                v === undefined
                                                    ? undefined
                                                    : Number(v),
                                            ),
                                        )
                                    }
                                />
                            )}
                        </div>
                        <TextField
                            label="Narrative"
                            rows={7}
                            value={step.narrative}
                            limits={vocab.text_limits['step.narrative']}
                            onChange={(v) =>
                                at(index)((s) => (s.narrative = v ?? ''))
                            }
                        />
                        {v3 && (
                            <div className="grid grid-cols-2 gap-2">
                                <DateSpec
                                    label={`Date${doc.ambient ? ' (required: ambient)' : ''}`}
                                    value={step.date}
                                    onChange={(v) =>
                                        at(index)((s) => {
                                            if (v === undefined) {
                                                delete s.date;
                                            } else {
                                                s.date = {
                                                    ...v,
                                                    ...(s.date?.end
                                                        ? { end: s.date.end }
                                                        : {}),
                                                };
                                            }
                                        })
                                    }
                                />
                                <DateSpec
                                    label="Until (optional)"
                                    value={step.date?.end}
                                    onChange={(v) =>
                                        at(index)(
                                            (s) =>
                                                s.date &&
                                                setKey(s.date, 'end', v),
                                        )
                                    }
                                />
                            </div>
                        )}
                        {v2 && (
                            <div className="grid grid-cols-4 gap-2">
                                <NumberField
                                    label="Wind from (°)"
                                    value={step.wind?.from}
                                    onChange={(v) =>
                                        at(index)((s) =>
                                            setKey(
                                                s,
                                                'wind',
                                                v === undefined
                                                    ? undefined
                                                    : {
                                                          ...(s.wind ?? {}),
                                                          from: v,
                                                      },
                                            ),
                                        )
                                    }
                                />
                                <SelectField
                                    label="Wind strength"
                                    value={step.wind?.strength}
                                    options={vocab.wind_strengths}
                                    onChange={(v) =>
                                        at(index)(
                                            (s) =>
                                                s.wind &&
                                                setKey(s.wind, 'strength', v),
                                        )
                                    }
                                />
                                <NumberField
                                    label="Sun from (°)"
                                    value={step.sun?.from}
                                    onChange={(v) =>
                                        at(index)((s) =>
                                            setKey(
                                                s,
                                                'sun',
                                                v === undefined
                                                    ? undefined
                                                    : {
                                                          ...(s.sun ?? {}),
                                                          from: v,
                                                      },
                                            ),
                                        )
                                    }
                                />
                                <TextField
                                    label="Sun label"
                                    value={step.sun?.label}
                                    onChange={(v) =>
                                        at(index)(
                                            (s) =>
                                                s.sun &&
                                                setKey(s.sun, 'label', v),
                                        )
                                    }
                                />
                            </div>
                        )}
                        <div className="space-y-1">
                            <span className="text-xs font-medium text-muted-foreground">
                                Focus (units the camera and highlight follow)
                            </span>
                            <div className="flex flex-wrap gap-x-3 gap-y-1">
                                {units.map((u) => (
                                    <CheckField
                                        key={u.id}
                                        label={u.label}
                                        value={
                                            Array.isArray(step.focus) &&
                                            step.focus.includes(u.id)
                                        }
                                        onChange={(on) =>
                                            at(index)((s) => {
                                                const next = (
                                                    Array.isArray(s.focus)
                                                        ? s.focus
                                                        : []
                                                ).filter(
                                                    (x: string) => x !== u.id,
                                                );
                                                setKey(
                                                    s,
                                                    'focus',
                                                    on
                                                        ? [...next, u.id]
                                                        : next.length
                                                          ? next
                                                          : undefined,
                                                );
                                            })
                                        }
                                    />
                                ))}
                            </div>
                        </div>
                        <div className="flex items-center gap-2 text-xs">
                            <span className="text-muted-foreground">
                                Camera:{' '}
                                {step.camera
                                    ? `${step.camera.center?.join(', ')} · zoom ${step.camera.zoom}${step.camera.bearing ? ` · bearing ${step.camera.bearing}` : ''}`
                                    : 'framed on what the step draws'}
                            </span>
                            <IconButton
                                title="Use the preview's current view for this step"
                                className="h-7"
                                onClick={() =>
                                    requestCamera((c) =>
                                        at(index)(
                                            (s) =>
                                                (s.camera = {
                                                    center: c.center,
                                                    zoom: c.zoom,
                                                    ...(c.bearing
                                                        ? { bearing: c.bearing }
                                                        : {}),
                                                }),
                                        ),
                                    )
                                }
                            >
                                <Video className="size-3" /> Use current preview
                                view
                            </IconButton>
                            {step.camera && (
                                <RemoveButton
                                    title="Clear the camera"
                                    onClick={() =>
                                        at(index)((s) => delete s.camera)
                                    }
                                />
                            )}
                        </div>
                    </Section>

                    <Section title="On the map">
                        <PhaseEditor
                            phase={step}
                            change={(fn) => at(index)(fn)}
                        />
                    </Section>

                    {v2 && (
                        <Section
                            title={`Beats (${(step.beats ?? []).length} / ${vocab.max_beats})`}
                            actions={
                                <IconButton
                                    title="Add a beat: a sub-moment of this step with its own placements and arrows"
                                    disabled={
                                        (step.beats ?? []).length >=
                                        vocab.max_beats
                                    }
                                    onClick={() =>
                                        at(index)(
                                            (s) =>
                                                (s.beats = [
                                                    ...(s.beats ?? []),
                                                    {
                                                        label: 'Then',
                                                        positions: {},
                                                        moves: [],
                                                    },
                                                ]),
                                        )
                                    }
                                >
                                    <Plus className="size-3.5" /> Beat
                                </IconButton>
                            }
                        >
                            {phasesOf(step)
                                .slice(1)
                                .map((beat, k) => (
                                    <div
                                        key={k}
                                        className="space-y-2 rounded-md border p-2"
                                    >
                                        <div className="flex items-end gap-1">
                                            <TextField
                                                label={`Beat ${k + 1} label`}
                                                value={beat.label}
                                                className="flex-1"
                                                onChange={(v) =>
                                                    at(index)(
                                                        (s) =>
                                                            (s.beats[k].label =
                                                                v ?? ''),
                                                    )
                                                }
                                            />
                                            <RemoveButton
                                                title="Remove this beat"
                                                onClick={() =>
                                                    at(index)((s) => {
                                                        s.beats.splice(k, 1);

                                                        if (
                                                            s.beats.length === 0
                                                        ) {
                                                            delete s.beats;
                                                        }
                                                    })
                                                }
                                            />
                                        </div>
                                        <PhaseEditor
                                            phase={beat}
                                            change={(fn) =>
                                                at(index)((s) => fn(s.beats[k]))
                                            }
                                        />
                                    </div>
                                ))}
                        </Section>
                    )}

                    {(v2 || features.length > 0) && features.length > 0 && (
                        <FeatureStateSection
                            step={step}
                            features={features}
                            sides={sides}
                            change={(fn) => at(index)((s) => fn(s))}
                            stateKey={stepStateKey(doc, step)}
                            v3={v3}
                        />
                    )}

                    {v3 && (
                        <Section
                            title={`People, places and polities (${(step.entities ?? []).length})`}
                            actions={
                                <IconButton
                                    title="Link an entity to this step"
                                    onClick={() =>
                                        at(index)(
                                            (s) =>
                                                (s.entities = [
                                                    ...(s.entities ?? []),
                                                    { name: '' },
                                                ]),
                                        )
                                    }
                                >
                                    <Plus className="size-3.5" /> Entity
                                </IconButton>
                            }
                        >
                            {(step.entities ?? []).map(
                                (e: StoryDoc, k: number) => (
                                    <div
                                        key={k}
                                        className="grid grid-cols-[1fr_10rem_auto_auto] items-end gap-1"
                                    >
                                        <EntityRefField
                                            label="Entity"
                                            value={e}
                                            onChange={(v) =>
                                                at(index)((s) => {
                                                    s.entities[k] = {
                                                        ...(v ?? { name: '' }),
                                                        ...(e.role
                                                            ? { role: e.role }
                                                            : {}),
                                                        ...(e.show !== undefined
                                                            ? { show: e.show }
                                                            : {}),
                                                    };
                                                })
                                            }
                                        />
                                        <TextField
                                            label="Role"
                                            value={e.role}
                                            onChange={(v) =>
                                                at(index)((s) =>
                                                    setKey(
                                                        s.entities[k],
                                                        'role',
                                                        v,
                                                    ),
                                                )
                                            }
                                        />
                                        <CheckField
                                            label="Show"
                                            value={e.show}
                                            className="pb-2"
                                            onChange={(v) =>
                                                at(index)((s) =>
                                                    setKey(
                                                        s.entities[k],
                                                        'show',
                                                        v,
                                                    ),
                                                )
                                            }
                                        />
                                        <RemoveButton
                                            title="Unlink"
                                            onClick={() =>
                                                at(index)((s) => {
                                                    s.entities.splice(k, 1);

                                                    if (
                                                        s.entities.length === 0
                                                    ) {
                                                        delete s.entities;
                                                    }
                                                })
                                            }
                                        />
                                    </div>
                                ),
                            )}
                        </Section>
                    )}
                </>
            )}
        </div>
    );
}

/** What each feature looks like in this step (carried forward key by key). */
function FeatureStateSection({
    step,
    features,
    sides,
    change,
    stateKey,
    v3,
}: {
    step: StoryDoc;
    features: StoryDoc[];
    sides: StoryDoc[];
    change: (fn: (step: StoryDoc) => void) => void;
    stateKey: 'features' | 'terrain_state';
    v3: boolean;
}) {
    const { vocab, pick } = useStoryEditor();
    const [drawing, setDrawing] = useState<string | null>(null);
    const states: StoryDoc =
        step[stateKey] && typeof step[stateKey] === 'object'
            ? step[stateKey]
            : {};
    const unset = features.filter((f) => !(f.id in states));

    const set = (id: string, key: string, value: unknown) =>
        change((s) => {
            s[stateKey] = s[stateKey] ?? {};
            s[stateKey][id] = { ...(s[stateKey][id] ?? {}) };
            setKey(
                s[stateKey][id],
                key,
                value,
                key === 'value_n' || key === 'intensity',
            );
        });

    return (
        <Section
            title={`Features in this step (${Object.keys(states).length})`}
            actions={
                <select
                    className="h-7 rounded-md border bg-background px-1 text-xs"
                    value=""
                    onChange={(e) =>
                        e.target.value &&
                        change(
                            (s) =>
                                (s[stateKey] = {
                                    ...(s[stateKey] ?? {}),
                                    [e.target.value]: {},
                                }),
                        )
                    }
                >
                    <option value="">+ Change a feature…</option>
                    {unset.map((f) => (
                        <option key={f.id} value={f.id}>
                            {f.label} ({f.id})
                        </option>
                    ))}
                </select>
            }
        >
            <p className="text-xs text-muted-foreground">
                Each value carries forward to later steps until one changes it.
            </p>
            {Object.entries(states).map(([id, st]: [string, StoryDoc]) => {
                const feature = features.find((f) => f.id === id);
                const geometry = feature
                    ? vocab.feature_kinds[feature.kind]
                    : undefined;

                return (
                    <div key={id} className="space-y-1 rounded border p-1.5">
                        <div className="flex items-center justify-between text-xs">
                            <span className="font-medium">
                                {feature?.label ?? id}{' '}
                                <span className="font-mono text-muted-foreground">
                                    {id}
                                </span>
                            </span>
                            <RemoveButton
                                title="Stop changing it here"
                                onClick={() =>
                                    change((s) => {
                                        delete s[stateKey][id];
                                    })
                                }
                            />
                        </div>
                        <div className="grid grid-cols-3 gap-1">
                            <SelectField
                                label="State"
                                value={st.state}
                                options={vocab.feature_states}
                                onChange={(v) => set(id, 'state', v)}
                            />
                            {sides.length > 0 && (
                                <SelectField
                                    label="Held by"
                                    value={st.held_by}
                                    options={sides.map((s) => ({
                                        value: s.id,
                                        label: s.name,
                                    }))}
                                    onChange={(v) => set(id, 'held_by', v)}
                                />
                            )}
                            <TextField
                                label="Label"
                                value={st.label}
                                onChange={(v) => set(id, 'label', v)}
                            />
                            {v3 && (
                                <>
                                    <SelectField
                                        label="Active"
                                        value={
                                            st.active === undefined
                                                ? undefined
                                                : String(st.active)
                                        }
                                        options={[
                                            { value: 'true', label: 'shown' },
                                            { value: 'false', label: 'hidden' },
                                        ]}
                                        empty="(carried)"
                                        onChange={(v) =>
                                            set(
                                                id,
                                                'active',
                                                v === undefined
                                                    ? undefined
                                                    : v === 'true',
                                            )
                                        }
                                    />
                                    <NumberField
                                        label="Value"
                                        value={st.value_n}
                                        onChange={(v) => set(id, 'value_n', v)}
                                    />
                                    <TextField
                                        label="Value label"
                                        value={st.value_label}
                                        onChange={(v) =>
                                            set(id, 'value_label', v)
                                        }
                                    />
                                    <NumberField
                                        label="Intensity (0–1)"
                                        value={st.intensity}
                                        onChange={(v) =>
                                            set(id, 'intensity', v)
                                        }
                                    />
                                    {geometry && geometry !== 'area' && (
                                        <div className="col-span-2 flex items-end gap-1 text-xs">
                                            <span className="flex-1 pb-2 text-muted-foreground">
                                                {st[geometry]
                                                    ? `${geometry} changed here`
                                                    : `${geometry}: as before`}
                                            </span>
                                            <IconButton
                                                title={`Pick a new ${geometry} on the preview`}
                                                className="h-7"
                                                onClick={() =>
                                                    pick(
                                                        geometry === 'at'
                                                            ? 'point'
                                                            : 'path',
                                                        (p) =>
                                                            set(
                                                                id,
                                                                geometry,
                                                                p,
                                                            ),
                                                    )
                                                }
                                            >
                                                Pick {geometry}
                                            </IconButton>
                                            {st[geometry] && (
                                                <RemoveButton
                                                    title="Back to the previous geometry"
                                                    onClick={() =>
                                                        set(
                                                            id,
                                                            geometry,
                                                            undefined,
                                                        )
                                                    }
                                                />
                                            )}
                                        </div>
                                    )}
                                    {geometry === 'area' && (
                                        <EntityRefField
                                            label="Area from an entity's territory"
                                            needsName={false}
                                            className="col-span-3"
                                            value={st.area_from_entity}
                                            onChange={(v) =>
                                                set(id, 'area_from_entity', v)
                                            }
                                        />
                                    )}
                                    {geometry === 'area' && (
                                        <div className="col-span-3 flex items-end gap-1 text-xs">
                                            <span className="flex-1 pb-2 text-muted-foreground">
                                                {st.area
                                                    ? `area redrawn here (${Array.isArray(st.area?.[0]?.[0]) ? `${st.area.length} rings` : 'one ring'})`
                                                    : 'area: as before'}
                                            </span>
                                            <IconButton
                                                title="Draw this step's area"
                                                className="h-7"
                                                onClick={() => setDrawing(id)}
                                            >
                                                <MapIcon className="size-3" />{' '}
                                                Draw area
                                            </IconButton>
                                            {st.area && (
                                                <RemoveButton
                                                    title="Back to the previous area"
                                                    onClick={() =>
                                                        set(
                                                            id,
                                                            'area',
                                                            undefined,
                                                        )
                                                    }
                                                />
                                            )}
                                        </div>
                                    )}
                                </>
                            )}
                        </div>
                    </div>
                );
            })}
            {drawing && (
                <GeometryDialog
                    open
                    title={`${features.find((f) => f.id === drawing)?.label ?? drawing} — area in this step`}
                    kind="area"
                    value={
                        states[drawing]?.area ??
                        features.find((f) => f.id === drawing)?.area
                    }
                    onClose={() => setDrawing(null)}
                    onSave={(value) => set(drawing, 'area', value)}
                />
            )}
        </Section>
    );
}
