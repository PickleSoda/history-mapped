import { ArrowRight, FolderMinus, Pencil, Plus, Route, Star, Trash2 } from 'lucide-react';
import { useState } from 'react';
import type { FormEvent, ReactNode } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { SaveToFolder, StarButton } from '@/components/account/SaveControls';
import { FIELD, FOLDER_COLORS } from '@/components/account/styles';
import { GroupDot, TypeBadge } from '@/components/atlas/GroupBadge';
import {
  useCreateFolder,
  useDeleteFolder,
  useFolderMembership,
  useFolders,
  useStarKeys,
  useStars,
  useUpdateFolder,
} from '@/hooks';
import { errorMessage, fieldErrors } from '@/lib/api';
import { chronicleHref, entityHref } from '@/lib/atlas-links';
import { yearSpanText } from '@/lib/chronicle-page';
import { SAVEABLE_TYPES } from '@/lib/schemas/saved';
import type { Folder, SaveableType, Star as StarRow } from '@/lib/schemas/saved';
import { cn } from '@/lib/utils';
import { AccountHeading, RequireUser } from './AccountLayout';

const TYPE_LABEL: Record<SaveableType, string> = {
  entity: 'Entities',
  chronicle: 'Chronicles',
  relationship: 'Relationships',
};

// ── Folder form (create + rename) ──────────────────────────────────────────

function FolderForm({
  initial,
  submitLabel,
  pending,
  error,
  onSubmit,
  onCancel,
}: {
  initial?: Folder;
  submitLabel: string;
  pending: boolean;
  error: unknown;
  onSubmit: (input: { name: string; description: string | null; color: string | null }) => void;
  onCancel: () => void;
}) {
  const [name, setName] = useState(initial?.name ?? '');
  const [description, setDescription] = useState(initial?.description ?? '');
  const [color, setColor] = useState<string | null>(initial?.color ?? FOLDER_COLORS[0]);
  const errors = fieldErrors(error);
  const general = error && !errors.name && !errors.description ? errorMessage(error) : null;

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    onSubmit({ name: name.trim(), description: description.trim() || null, color });
  };

  return (
    <form onSubmit={submit} className="space-y-2.5 rounded-xl border bg-card p-3">
      <input
        aria-label="Folder name"
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="Folder name"
        maxLength={80}
        required
        autoFocus
        aria-invalid={errors.name ? true : undefined}
        className={cn(FIELD, 'h-9 py-1.5')}
      />
      {errors.name && <p className="text-[11px] text-destructive">{errors.name}</p>}
      <textarea
        aria-label="Description"
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        placeholder="Description (optional)"
        maxLength={500}
        rows={2}
        className={cn(FIELD, 'resize-y py-1.5')}
      />
      <div role="radiogroup" aria-label="Colour" className="flex gap-1.5">
        {FOLDER_COLORS.map((c) => (
          <button
            key={c}
            type="button"
            role="radio"
            aria-checked={color === c}
            aria-label={`Colour ${c}`}
            onClick={() => setColor(c)}
            className={cn(
              'size-5 rounded-full ring-offset-2 ring-offset-card transition-shadow',
              color === c && 'ring-2 ring-foreground',
            )}
            style={{ background: c }}
          />
        ))}
      </div>
      {general && <p className="text-[11px] text-destructive">{general}</p>}
      <div className="flex justify-end gap-1.5">
        <button
          type="button"
          onClick={onCancel}
          className="h-7 rounded-md px-2.5 text-[12px] text-muted-foreground hover:bg-muted hover:text-foreground"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={pending || !name.trim()}
          className="h-7 rounded-md bg-primary px-2.5 text-[12px] font-medium text-primary-foreground hover:bg-primary/85 disabled:opacity-40"
        >
          {submitLabel}
        </button>
      </div>
    </form>
  );
}

// ── Sidebar ────────────────────────────────────────────────────────────────

function NavRow({
  active,
  onClick,
  color,
  label,
  count,
  icon,
}: {
  active: boolean;
  onClick: () => void;
  color?: string | null;
  label: string;
  count?: number;
  icon?: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-current={active ? 'page' : undefined}
      className={cn(
        'flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-[13px] transition-colors',
        active ? 'bg-muted font-medium text-foreground' : 'text-foreground/80 hover:bg-muted/60',
      )}
    >
      {icon ?? (
        <span
          aria-hidden
          className="size-2.5 flex-none rounded-full"
          style={{ background: color ?? 'var(--muted-foreground)' }}
        />
      )}
      <span className="min-w-0 flex-1 truncate">{label}</span>
      {count != null && <span className="font-mono text-[10px] text-muted-foreground">{count}</span>}
    </button>
  );
}

function FolderSidebar({
  folders,
  activeId,
  total,
  onPick,
}: {
  folders: Folder[];
  activeId: number | null;
  total: number | undefined;
  onPick: (id: number | null) => void;
}) {
  const [creating, setCreating] = useState(false);
  const create = useCreateFolder();
  return (
    <nav aria-label="Folders" className="space-y-0.5">
      <NavRow
        active={activeId == null}
        onClick={() => onPick(null)}
        label="All starred"
        count={total}
        icon={<Star size={14} className="flex-none text-amber-600 dark:text-amber-400" />}
      />
      <p className="px-2.5 pb-1 pt-4 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
        Folders
      </p>
      {folders.length === 0 && !creating && (
        <p className="px-2.5 pb-1 text-[12px] text-muted-foreground">Group your stars into folders.</p>
      )}
      {folders.map((f) => (
        <NavRow
          key={f.id}
          active={activeId === f.id}
          onClick={() => onPick(f.id)}
          color={f.color}
          label={f.name}
          count={f.stars_count}
        />
      ))}
      <div className="pt-2">
        {creating ? (
          <FolderForm
            submitLabel="Create"
            pending={create.isPending}
            error={create.error}
            onCancel={() => {
              setCreating(false);
              create.reset();
            }}
            onSubmit={(input) =>
              create.mutate(input, {
                onSuccess: (folder) => {
                  setCreating(false);
                  onPick(folder.id);
                },
              })
            }
          />
        ) : (
          <button
            type="button"
            onClick={() => setCreating(true)}
            className="flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-[13px] text-muted-foreground hover:bg-muted/60 hover:text-foreground"
          >
            <Plus size={14} /> New folder
          </button>
        )}
      </div>
    </nav>
  );
}

// ── Folder header (rename / delete) ────────────────────────────────────────

function FolderHeader({ folder, onDeleted }: { folder: Folder; onDeleted: () => void }) {
  const [editing, setEditing] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const update = useUpdateFolder();
  const remove = useDeleteFolder();

  if (editing) {
    return (
      <div className="mb-6 max-w-md">
        <FolderForm
          key={folder.id}
          initial={folder}
          submitLabel="Save"
          pending={update.isPending}
          error={update.error}
          onCancel={() => {
            setEditing(false);
            update.reset();
          }}
          onSubmit={(input) =>
            update.mutate({ id: folder.id, ...input }, { onSuccess: () => setEditing(false) })
          }
        />
      </div>
    );
  }

  return (
    <div className="mb-6 flex flex-wrap items-start gap-3">
      <div className="min-w-0 flex-1">
        <h2 className="flex items-center gap-2 font-heading text-[22px] font-semibold">
          <span aria-hidden className="size-3 rounded-full" style={{ background: folder.color ?? 'var(--muted-foreground)' }} />
          {folder.name}
        </h2>
        {folder.description && (
          <p className="mt-1 max-w-prose text-[13px] text-muted-foreground">{folder.description}</p>
        )}
      </div>
      {confirming ? (
        <div role="alertdialog" aria-label="Delete folder" className="flex items-center gap-2 rounded-lg border bg-card px-3 py-1.5 text-[12px]">
          <span>Delete “{folder.name}”? Its items stay starred.</span>
          <button
            type="button"
            onClick={() => remove.mutate(folder.id, { onSuccess: onDeleted })}
            disabled={remove.isPending}
            className="h-7 rounded-md bg-destructive/10 px-2.5 font-medium text-destructive hover:bg-destructive/20"
          >
            Delete
          </button>
          <button
            type="button"
            onClick={() => setConfirming(false)}
            className="h-7 rounded-md px-2 text-muted-foreground hover:bg-muted"
          >
            Cancel
          </button>
        </div>
      ) : (
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => setEditing(true)}
            className="inline-flex h-8 items-center gap-1.5 rounded-lg px-2.5 text-[12px] font-medium text-muted-foreground hover:bg-muted hover:text-foreground"
          >
            <Pencil size={13} /> Edit
          </button>
          <button
            type="button"
            onClick={() => setConfirming(true)}
            className="inline-flex h-8 items-center gap-1.5 rounded-lg px-2.5 text-[12px] font-medium text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
          >
            <Trash2 size={13} /> Delete
          </button>
        </div>
      )}
      {remove.error != null && <p className="w-full text-[12px] text-destructive">{errorMessage(remove.error)}</p>}
    </div>
  );
}

// ── Items ──────────────────────────────────────────────────────────────────

function ItemBody({ star }: { star: StarRow }) {
  const item = star.item;
  if (!item) {
    return (
      <p className="text-[13px] italic text-muted-foreground">
        This {star.type} is no longer in the atlas.
      </p>
    );
  }
  if (item.type === 'entity') {
    return (
      <>
        <div className="flex flex-wrap items-center gap-2">
          <GroupDot group={item.entity_group} />
          <Link to={entityHref(item.id)} className="font-heading text-[16px] font-semibold underline-offset-4 hover:underline">
            {item.name}
          </Link>
          <TypeBadge group={item.entity_group} type={item.entity_type} />
        </div>
        {item.summary && <p className="mt-1 line-clamp-2 text-[13px] text-foreground/75">{item.summary}</p>}
      </>
    );
  }
  if (item.type === 'chronicle') {
    const years = yearSpanText(item.start_year, item.end_year);
    return (
      <>
        <div className="flex flex-wrap items-center gap-2">
          <Route size={14} className="text-muted-foreground" />
          <Link to={chronicleHref(item.slug)} className="font-heading text-[16px] font-semibold underline-offset-4 hover:underline">
            {item.title}
          </Link>
        </div>
        <p className="mt-1 font-mono text-[11px] text-muted-foreground">
          {[years, item.entry_count != null && `${item.entry_count} steps`].filter(Boolean).join(' · ')}
        </p>
      </>
    );
  }
  return (
    <>
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[14px]">
        {item.source ? (
          <Link to={entityHref(item.source.id)} className="inline-flex items-center gap-1.5 font-medium underline-offset-4 hover:underline">
            <GroupDot group={item.source.entity_group} /> {item.source.name}
          </Link>
        ) : (
          <span className="text-muted-foreground">—</span>
        )}
        <ArrowRight size={13} className="text-muted-foreground" />
        {item.target ? (
          <Link to={entityHref(item.target.id)} className="inline-flex items-center gap-1.5 font-medium underline-offset-4 hover:underline">
            <GroupDot group={item.target.entity_group} /> {item.target.name}
          </Link>
        ) : (
          <span className="text-muted-foreground">—</span>
        )}
        {item.relationship_type && (
          <span className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
            {item.relationship_type.replace(/_/g, ' ')}
          </span>
        )}
      </div>
      {item.description && <p className="mt-1 line-clamp-2 text-[13px] text-foreground/75">{item.description}</p>}
    </>
  );
}

function SavedItemRow({ star, folderId }: { star: StarRow; folderId: number | null }) {
  const membership = useFolderMembership();
  return (
    <li className="flex items-start gap-3 py-4">
      <div className="min-w-0 flex-1">
        <ItemBody star={star} />
      </div>
      <div className="flex flex-none items-center gap-0.5">
        {star.item && <SaveToFolder type={star.type} id={star.target_id} />}
        {folderId != null && (
          <button
            type="button"
            onClick={() => membership.mutate({ folderId, type: star.type, id: star.target_id, member: true })}
            aria-label="Remove from this folder"
            title="Remove from this folder"
            className="grid size-8 place-items-center rounded-lg text-muted-foreground hover:bg-muted hover:text-foreground"
          >
            <FolderMinus size={15} />
          </button>
        )}
        <StarButton compact type={star.type} id={star.target_id} />
      </div>
    </li>
  );
}

// ── The page ───────────────────────────────────────────────────────────────

function SavedContent() {
  const [params, setParams] = useSearchParams();
  const folderParam = Number(params.get('folder'));
  const folderId = Number.isInteger(folderParam) && folderParam > 0 ? folderParam : null;
  const typeParam = params.get('type');
  const type = (SAVEABLE_TYPES as readonly string[]).includes(typeParam ?? '') ? (typeParam as SaveableType) : null;
  const page = Math.max(1, Number(params.get('page')) || 1);

  const { data: folders = [] } = useFolders();
  const { data: keys } = useStarKeys();
  const { data, isLoading, isError, isPlaceholderData } = useStars({ type, folder: folderId, page });
  const folder = folderId != null ? folders.find((f) => f.id === folderId) : undefined;

  const set = (next: { folder?: number | null; type?: SaveableType | null; page?: number }) => {
    const p = new URLSearchParams(params);
    const apply = (k: string, v: string | number | null | undefined) => {
      if (v === undefined) return;
      if (v === null || v === '' || (k === 'page' && v === 1)) p.delete(k);
      else p.set(k, String(v));
    };
    apply('folder', next.folder);
    apply('type', next.type);
    apply('page', next.page ?? 1);
    setParams(p);
  };

  const meta = data?.meta;
  const stars = data?.data ?? [];

  return (
    <div className="grid gap-8 md:grid-cols-[240px_minmax(0,1fr)]">
      <aside className="md:sticky md:top-[78px] md:self-start">
        <FolderSidebar
          folders={folders}
          activeId={folderId}
          total={keys?.size}
          onPick={(id) => set({ folder: id })}
        />
      </aside>

      <section aria-label={folder?.name ?? 'All starred'} className="min-w-0">
        {folder && <FolderHeader folder={folder} onDeleted={() => set({ folder: null })} />}

        <div className="mb-2 flex flex-wrap gap-1" role="group" aria-label="Filter by type">
          {[null, ...SAVEABLE_TYPES].map((t) => (
            <button
              key={t ?? 'all'}
              type="button"
              aria-pressed={type === t}
              onClick={() => set({ type: t })}
              className={cn(
                'h-7 rounded-full border px-3 text-[12px] transition-colors',
                type === t ? 'border-foreground bg-foreground text-background' : 'text-muted-foreground hover:bg-muted hover:text-foreground',
              )}
            >
              {t ? TYPE_LABEL[t] : 'Everything'}
            </button>
          ))}
        </div>

        {isLoading && <p className="py-10 text-[13px] text-muted-foreground">Loading…</p>}
        {isError && <p className="py-10 text-[13px] text-destructive">Could not load your saved items.</p>}
        {data && stars.length === 0 && (
          <div className="mt-4 rounded-xl border border-dashed px-6 py-12 text-center">
            <Star size={22} className="mx-auto text-muted-foreground" />
            <p className="mt-3 font-heading text-[16px] font-semibold">
              {folder ? 'This folder is empty' : type ? `No starred ${TYPE_LABEL[type].toLowerCase()}` : 'Nothing starred yet'}
            </p>
            <p className="mx-auto mt-1 max-w-sm text-[13px] text-muted-foreground">
              Use the star on any entity, chronicle or relationship in the atlas
              {folder ? ', then file it here from its folder menu' : ''}.
            </p>
            <Link to="/" className="mt-4 inline-flex h-8 items-center rounded-lg border bg-card px-3 text-[12px] font-medium hover:bg-muted">
              Explore the atlas
            </Link>
          </div>
        )}
        {stars.length > 0 && (
          <ul className={cn('divide-y', isPlaceholderData && 'opacity-60')}>
            {stars.map((s) => (
              <SavedItemRow key={s.id} star={s} folderId={folderId} />
            ))}
          </ul>
        )}

        {meta && meta.last_page > 1 && (
          <nav aria-label="Pages" className="mt-6 flex items-center justify-between text-[12px]">
            <button
              type="button"
              disabled={meta.current_page <= 1}
              onClick={() => set({ page: meta.current_page - 1 })}
              className="h-8 rounded-lg border bg-card px-3 font-medium hover:bg-muted disabled:opacity-40"
            >
              Previous
            </button>
            <span className="text-muted-foreground">
              Page {meta.current_page} of {meta.last_page}
            </span>
            <button
              type="button"
              disabled={meta.current_page >= meta.last_page}
              onClick={() => set({ page: meta.current_page + 1 })}
              className="h-8 rounded-lg border bg-card px-3 font-medium hover:bg-muted disabled:opacity-40"
            >
              Next
            </button>
          </nav>
        )}
      </section>
    </div>
  );
}

/** `/saved` — every star, filterable by folder and type; folder management. */
export function SavedPage() {
  return (
    <RequireUser>
      <AccountHeading title="Saved">
        Everything you’ve starred, and the folders you’ve filed it into.
      </AccountHeading>
      <SavedContent />
    </RequireUser>
  );
}
