import { Link, useForm } from '@inertiajs/react';
import { Map as MapIcon, Plus } from 'lucide-react';
import { useState } from 'react';
import { Button } from '@/components/ui/button';
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { edit as editStory, store } from '@/routes/map-stories';

export type EntityMapStory = {
    slug: string;
    title: string;
    kind: string;
    year: number | null;
    step_count: number;
};

/**
 * An entity's map stories on its edit page, and "Add a map story": a skeleton
 * (placeholders, a Wikidata source, two sides for a battle) opened in the editor.
 */
export function EntityMapStoriesPanel({
    entityId,
    entityName,
    entityType,
    startYear,
    stories,
    kinds,
    canEdit = true,
}: {
    entityId: string;
    entityName: string;
    entityType?: string | null;
    startYear?: number | null;
    stories: EntityMapStory[];
    kinds: string[];
    canEdit?: boolean;
}) {
    const [open, setOpen] = useState(false);
    const guess = kinds.includes(entityType ?? '')
        ? (entityType as string)
        : entityType === 'war'
          ? 'war'
          : 'battle';
    const form = useForm({
        entity_id: entityId,
        kind: guess,
        title: entityName,
        year: Number.isFinite(startYear) ? String(startYear) : '',
    });

    return (
        <div className="mt-4 rounded-lg border">
            <div className="flex items-center justify-between px-4 py-3">
                <span className="flex items-center gap-2 text-sm font-medium">
                    <MapIcon className="size-4" /> Map stories
                </span>
                {canEdit && (
                    <Button
                        size="sm"
                        variant="outline"
                        onClick={() => setOpen(true)}
                    >
                        <Plus className="size-4" /> Add a map story
                    </Button>
                )}
            </div>
            {stories.length > 0 ? (
                <ul className="divide-y border-t text-sm">
                    {stories.map((s) => (
                        <li
                            key={s.slug}
                            className="flex items-center gap-2 px-4 py-2"
                        >
                            <Link
                                href={editStory.url(s.slug)}
                                className="font-medium hover:underline"
                            >
                                {s.title}
                            </Link>
                            <span className="text-xs text-muted-foreground">
                                {s.kind.replace(/_/g, ' ')} · {s.step_count}{' '}
                                step{s.step_count === 1 ? '' : 's'}
                            </span>
                        </li>
                    ))}
                </ul>
            ) : (
                <p className="border-t px-4 py-3 text-xs text-muted-foreground">
                    None yet.
                </p>
            )}

            <Dialog open={open} onOpenChange={setOpen}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Add a map story</DialogTitle>
                        <DialogDescription>
                            Creates a skeleton — placeholder text, a Wikidata
                            source
                            {guess === 'battle'
                                ? ', two sides with one unit each'
                                : ''}{' '}
                            and one step at this entity's location — and opens
                            it in the editor. It is public as soon as it exists.
                        </DialogDescription>
                    </DialogHeader>
                    <form
                        className="space-y-3"
                        onSubmit={(e) => {
                            e.preventDefault();
                            form.transform((data) => ({
                                ...data,
                                year: Number(data.year),
                            }));
                            form.post(store.url(), {
                                onSuccess: () => setOpen(false),
                            });
                        }}
                    >
                        <div className="space-y-1">
                            <Label htmlFor="ms-kind">Kind</Label>
                            <select
                                id="ms-kind"
                                className="h-9 w-full rounded-md border bg-background px-2 text-sm"
                                value={form.data.kind}
                                onChange={(e) =>
                                    form.setData('kind', e.target.value)
                                }
                            >
                                {kinds.map((k) => (
                                    <option key={k} value={k}>
                                        {k.replace(/_/g, ' ')}
                                    </option>
                                ))}
                            </select>
                        </div>
                        <div className="space-y-1">
                            <Label htmlFor="ms-title">Title</Label>
                            <Input
                                id="ms-title"
                                value={form.data.title}
                                maxLength={120}
                                onChange={(e) =>
                                    form.setData('title', e.target.value)
                                }
                            />
                        </div>
                        <div className="space-y-1">
                            <Label htmlFor="ms-year">
                                Year (BCE as negative)
                            </Label>
                            <Input
                                id="ms-year"
                                type="number"
                                step="1"
                                value={form.data.year}
                                onChange={(e) =>
                                    form.setData('year', e.target.value)
                                }
                            />
                        </div>
                        {Object.values(form.errors).length > 0 && (
                            <p className="text-sm text-destructive">
                                {Object.values(form.errors).join(' · ')}
                            </p>
                        )}
                        <DialogFooter>
                            <Button
                                type="button"
                                variant="outline"
                                onClick={() => setOpen(false)}
                            >
                                Cancel
                            </Button>
                            <Button
                                type="submit"
                                disabled={
                                    form.processing ||
                                    form.data.title.trim() === '' ||
                                    form.data.year === ''
                                }
                            >
                                Create and edit
                            </Button>
                        </DialogFooter>
                    </form>
                </DialogContent>
            </Dialog>
        </div>
    );
}
