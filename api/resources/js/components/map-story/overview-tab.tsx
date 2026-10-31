import { Plus, Video } from 'lucide-react';
import { issuesFor } from '@/lib/map-story-doc';
import type { StoryDoc } from '@/lib/map-story-doc';
import { useStoryEditor } from './editor-context';
import { EntityRefField } from './entity-ref-field';
import {
    CheckField,
    IconButton,
    NumberField,
    PointField,
    RemoveButton,
    Section,
    SelectField,
    setKey,
    TextField,
} from './fields';

/** Title, kind, dates, attachment, the prose, sources, alternative sites, legend and the overview camera. */
export function OverviewTab() {
    const { doc, edit, vocab, errors, pick, requestCamera } = useStoryEditor();
    const limits = vocab.text_limits;
    const at = (field: string) =>
        issuesFor(errors, (t) => t.tab === 'overview' && t.field === field);
    const list = (key: string): StoryDoc[] =>
        Array.isArray(doc[key]) ? doc[key] : [];

    return (
        <div className="space-y-3">
            <Section title="Story">
                <div className="grid grid-cols-2 gap-2">
                    <TextField
                        label="Title"
                        value={doc.title}
                        limits={limits.title}
                        issues={at('title')}
                        className="col-span-2"
                        onChange={(v) => edit((d) => setKey(d, 'title', v))}
                    />
                    <SelectField
                        label="Kind"
                        value={doc.kind}
                        options={vocab.story_kinds}
                        empty={null}
                        issues={at('kind')}
                        onChange={(v) => edit((d) => setKey(d, 'kind', v))}
                    />
                    <SelectField
                        label="Schema"
                        value={String(doc.schema ?? '')}
                        options={['1', '2', '3']}
                        empty={null}
                        issues={at('schema')}
                        onChange={(v) =>
                            edit((d) =>
                                setKey(d, 'schema', v ? Number(v) : undefined),
                            )
                        }
                    />
                    <NumberField
                        label="Year (first; BCE negative)"
                        value={doc.year}
                        step="1"
                        issues={at('year')}
                        onChange={(v) => edit((d) => setKey(d, 'year', v))}
                    />
                    <TextField
                        label="Date label"
                        value={doc.date_label}
                        limits={limits.date_label}
                        issues={at('date_label')}
                        onChange={(v) =>
                            edit((d) => setKey(d, 'date_label', v))
                        }
                    />
                    <NumberField
                        label="Period start (year)"
                        value={doc.period?.start?.year}
                        step="1"
                        issues={at('period')}
                        onChange={(v) =>
                            edit((d) => {
                                if (v === undefined) {
                                    delete d.period;
                                } else {
                                    d.period = {
                                        start: { year: v },
                                        end: d.period?.end ?? { year: v },
                                    };
                                }
                            })
                        }
                    />
                    <NumberField
                        label="Period end (year)"
                        value={doc.period?.end?.year}
                        step="1"
                        onChange={(v) =>
                            edit((d) => {
                                if (v === undefined) {
                                    delete d.period;
                                } else {
                                    d.period = {
                                        start: d.period?.start ?? { year: v },
                                        end: { year: v },
                                    };
                                }
                            })
                        }
                    />
                    <CheckField
                        label="Ambient: show faintly on the plain atlas (every step then needs a date)"
                        value={doc.ambient}
                        className="col-span-2"
                        onChange={(v) => edit((d) => setKey(d, 'ambient', v))}
                    />
                </div>
            </Section>

            <Section title="Belongs to">
                <EntityRefField
                    label="Entity"
                    value={doc.entity}
                    onChange={(v) => edit((d) => setKey(d, 'entity', v))}
                />
                <TextField
                    label="Chronicle slug (a chronicle's map layer)"
                    value={doc.chronicle?.slug}
                    issues={[...at('entity'), ...at('chronicle')]}
                    onChange={(v) =>
                        edit((d) =>
                            setKey(d, 'chronicle', v ? { slug: v } : undefined),
                        )
                    }
                />
            </Section>

            <Section title="Text">
                <TextField
                    label="Intro"
                    rows={6}
                    value={doc.intro}
                    limits={limits.intro}
                    issues={at('intro')}
                    onChange={(v) => edit((d) => setKey(d, 'intro', v))}
                />
                <TextField
                    label="Outcome"
                    rows={2}
                    value={doc.outcome}
                    limits={limits.outcome}
                    issues={at('outcome')}
                    onChange={(v) => edit((d) => setKey(d, 'outcome', v))}
                />
                <TextField
                    label="Uncertainty (what is debated; which reconstruction this follows)"
                    rows={4}
                    value={doc.uncertainty}
                    limits={limits.uncertainty}
                    issues={at('uncertainty')}
                    onChange={(v) => edit((d) => setKey(d, 'uncertainty', v))}
                />
            </Section>

            <Section
                title="Sources"
                actions={
                    <IconButton
                        title="Add a source"
                        onClick={() =>
                            edit(
                                (d) =>
                                    (d.sources = [
                                        ...list('sources'),
                                        { title: '' },
                                    ]),
                            )
                        }
                    >
                        <Plus className="size-3.5" /> Source
                    </IconButton>
                }
            >
                {at('sources').length > 0 && (
                    <p className="text-xs text-destructive">
                        {at('sources').join(' · ')}
                    </p>
                )}
                {list('sources').map((s, i) => (
                    <div
                        key={i}
                        className="grid grid-cols-[1fr_1fr_7rem_auto] items-end gap-1"
                    >
                        <TextField
                            label="Title"
                            value={s.title}
                            onChange={(v) =>
                                edit((d) => (d.sources[i].title = v ?? ''))
                            }
                        />
                        <TextField
                            label="URL"
                            value={s.url}
                            onChange={(v) =>
                                edit((d) => setKey(d.sources[i], 'url', v))
                            }
                        />
                        <SelectField
                            label="Kind"
                            value={s.kind}
                            options={vocab.source_kinds}
                            onChange={(v) =>
                                edit((d) => setKey(d.sources[i], 'kind', v))
                            }
                        />
                        <RemoveButton
                            title="Remove source"
                            onClick={() => edit((d) => d.sources.splice(i, 1))}
                        />
                    </div>
                ))}
            </Section>

            <Section
                title="Disputed sites"
                actions={
                    <IconButton
                        title="Add an alternative site (pick it on the map)"
                        onClick={() =>
                            pick('point', (p) =>
                                edit(
                                    (d) =>
                                        (d.alt_sites = [
                                            ...list('alt_sites'),
                                            {
                                                at: p,
                                                label: 'Alternative site',
                                            },
                                        ]),
                                ),
                            )
                        }
                    >
                        <Plus className="size-3.5" /> Site
                    </IconButton>
                }
            >
                {list('alt_sites').map((s, i) => (
                    <div
                        key={i}
                        className="grid grid-cols-[1fr_1fr_auto] items-end gap-1"
                    >
                        <TextField
                            label="Label"
                            value={s.label}
                            onChange={(v) =>
                                edit((d) => (d.alt_sites[i].label = v ?? ''))
                            }
                        />
                        <PointField
                            label="At"
                            value={s.at}
                            onChange={(v) =>
                                edit((d) => setKey(d.alt_sites[i], 'at', v))
                            }
                            onPick={() =>
                                pick('point', (p) =>
                                    edit((d) => (d.alt_sites[i].at = p)),
                                )
                            }
                        />
                        <RemoveButton
                            title="Remove site"
                            onClick={() =>
                                edit((d) => d.alt_sites.splice(i, 1))
                            }
                        />
                        <TextField
                            label="Note"
                            value={s.note}
                            className="col-span-3"
                            onChange={(v) =>
                                edit((d) => setKey(d.alt_sites[i], 'note', v))
                            }
                        />
                    </div>
                ))}
            </Section>

            <Section
                title="Legend"
                actions={
                    <IconButton
                        title="Add a legend entry"
                        onClick={() =>
                            edit(
                                (d) =>
                                    (d.legend = [
                                        ...list('legend'),
                                        {
                                            swatch: '#7f1d1d',
                                            label: 'Label',
                                            style: 'fill',
                                        },
                                    ]),
                            )
                        }
                    >
                        <Plus className="size-3.5" /> Entry
                    </IconButton>
                }
            >
                {list('legend').map((l, i) => (
                    <div
                        key={i}
                        className="grid grid-cols-[3rem_1fr_6rem_auto] items-end gap-1"
                    >
                        <input
                            type="color"
                            className="h-8 w-12 rounded border"
                            value={
                                /^#[0-9a-f]{6}$/i.test(l.swatch ?? '')
                                    ? l.swatch
                                    : '#000000'
                            }
                            onChange={(e) =>
                                edit(
                                    (d) =>
                                        (d.legend[i].swatch = e.target.value),
                                )
                            }
                        />
                        <TextField
                            label="Label"
                            value={l.label}
                            onChange={(v) =>
                                edit((d) => (d.legend[i].label = v ?? ''))
                            }
                        />
                        <SelectField
                            label="Style"
                            value={l.style}
                            options={vocab.legend_styles}
                            onChange={(v) =>
                                edit((d) => setKey(d.legend[i], 'style', v))
                            }
                        />
                        <RemoveButton
                            title="Remove entry"
                            onClick={() => edit((d) => d.legend.splice(i, 1))}
                        />
                    </div>
                ))}
            </Section>

            <Section
                title="Overview camera"
                actions={
                    <>
                        <IconButton
                            title="Use the preview's current view"
                            onClick={() =>
                                requestCamera((c) =>
                                    edit(
                                        (d) =>
                                            (d.camera = {
                                                center: c.center,
                                                zoom: c.zoom,
                                                bearing: c.bearing,
                                            }),
                                    ),
                                )
                            }
                        >
                            <Video className="size-3.5" /> Use current preview
                            view
                        </IconButton>
                        {doc.camera && (
                            <RemoveButton
                                title="Clear the camera"
                                onClick={() => edit((d) => delete d.camera)}
                            />
                        )}
                    </>
                }
            >
                <p className="text-xs text-muted-foreground">
                    {doc.camera
                        ? `centre ${doc.camera.center?.join(', ')} · zoom ${doc.camera.zoom}${doc.camera.bearing ? ` · bearing ${doc.camera.bearing}` : ''}`
                        : 'None: the atlas frames each step on what it draws.'}
                </p>
            </Section>
        </div>
    );
}
