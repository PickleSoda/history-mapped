/**
 * Star + "save to folder" controls for an entity, chronicle or relationship.
 * State comes from the one cached star-keys list, so every control for the
 * same target agrees. Guests are sent to sign in and brought back.
 */
import { Popover } from '@base-ui/react/popover';
import { Check, FolderPlus, Plus, Star } from 'lucide-react';
import { useId, useState } from 'react';
import type { FormEvent } from 'react';
import {
  useCreateFolder,
  useFolderMembership,
  useFolders,
  useLoginRedirect,
  useMe,
  useStarState,
  useToggleStar,
} from '@/hooks';
import { errorMessage, fieldErrors } from '@/lib/api';
import type { SaveableType } from '@/lib/schemas/saved';
import { cn } from '@/lib/utils';
import { FIELD, FOLDER_COLORS, POPUP } from './styles';

const NOUN: Record<SaveableType, string> = {
  entity: 'entity',
  chronicle: 'chronicle',
  relationship: 'relationship',
};

/** Star toggle. `compact` = icon only (header size); `dense` = a small icon
 *  button for list rows. */
export function StarButton({
  type,
  id,
  compact,
  dense,
  className,
}: {
  type: SaveableType;
  id: string;
  compact?: boolean;
  dense?: boolean;
  className?: string;
}) {
  const { me } = useMe();
  const toLogin = useLoginRedirect();
  const { starred } = useStarState(type, id);
  const toggle = useToggleStar();
  const label = starred ? `Unstar this ${NOUN[type]}` : `Star this ${NOUN[type]}`;
  const iconOnly = compact || dense;

  const onClick = () => {
    if (!me) return toLogin();
    toggle.mutate({ type, id, starred });
  };

  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={starred}
      aria-label={iconOnly ? label : undefined}
      title={label}
      className={cn(
        'inline-flex flex-none items-center justify-center gap-1.5 rounded-lg font-medium transition-colors hover:bg-muted',
        dense ? 'size-6 rounded-md' : compact ? 'size-8' : 'h-8 px-2.5 text-[12px]',
        starred ? 'text-amber-600 dark:text-amber-400' : 'text-muted-foreground hover:text-foreground',
        className,
      )}
    >
      <Star size={dense ? 13 : 15} className={cn(starred && 'fill-current')} />
      {!iconOnly && (starred ? 'Starred' : 'Star')}
    </button>
  );
}

/** Folder checklist + quick "new folder" (files the target into it). */
export function FolderChecklist({ type, id }: { type: SaveableType; id: string }) {
  const { data: folders, isLoading } = useFolders();
  const { folderIds } = useStarState(type, id);
  const membership = useFolderMembership();
  const create = useCreateFolder();
  const [name, setName] = useState('');
  const inputId = useId();
  const nameError = fieldErrors(create.error).name ?? (create.error ? errorMessage(create.error) : null);

  const onCreate = (e: FormEvent) => {
    e.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) return;
    const color = FOLDER_COLORS[(folders?.length ?? 0) % FOLDER_COLORS.length];
    create.mutate(
      { name: trimmed, color },
      {
        onSuccess: (folder) => {
          setName('');
          membership.mutate({ folderId: folder.id, type, id, member: false });
        },
      },
    );
  };

  return (
    <div className="w-64">
      <p className="px-2 pb-1.5 pt-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
        Save to folder
      </p>
      {isLoading && <p className="px-2 py-1.5 text-[12px] text-muted-foreground">Loading…</p>}
      {folders && folders.length === 0 && (
        <p className="px-2 py-1.5 text-[12px] text-muted-foreground">No folders yet — make one below.</p>
      )}
      {folders && folders.length > 0 && (
        <ul className="max-h-60 overflow-y-auto">
          {folders.map((f) => {
            const member = folderIds.includes(f.id);
            return (
              <li key={f.id}>
                <button
                  type="button"
                  role="checkbox"
                  aria-checked={member}
                  onClick={() => membership.mutate({ folderId: f.id, type, id, member })}
                  className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-[13px] hover:bg-muted focus-visible:bg-muted focus-visible:outline-none"
                >
                  <span
                    aria-hidden
                    className={cn(
                      'grid size-4 flex-none place-items-center rounded border',
                      member && 'border-foreground bg-foreground text-background',
                    )}
                  >
                    {member && <Check size={11} strokeWidth={3} />}
                  </span>
                  <span
                    aria-hidden
                    className="size-2 flex-none rounded-full"
                    style={{ background: f.color ?? 'var(--muted-foreground)' }}
                  />
                  <span className="min-w-0 flex-1 truncate">{f.name}</span>
                  <span className="font-mono text-[10px] text-muted-foreground">{f.stars_count}</span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
      <form onSubmit={onCreate} className="mt-1.5 border-t px-1 pt-2">
        <label htmlFor={inputId} className="sr-only">
          New folder name
        </label>
        <div className="flex gap-1.5">
          <input
            id={inputId}
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="New folder…"
            maxLength={80}
            aria-invalid={nameError ? true : undefined}
            className={cn(FIELD, 'h-8 py-1')}
          />
          <button
            type="submit"
            disabled={!name.trim() || create.isPending}
            aria-label="Create folder"
            className="grid size-8 flex-none place-items-center rounded-lg border bg-card text-muted-foreground hover:bg-muted hover:text-foreground disabled:opacity-40"
          >
            <Plus size={15} />
          </button>
        </div>
        {nameError && <p className="mt-1 px-1 text-[11px] text-destructive">{nameError}</p>}
      </form>
    </div>
  );
}

/** "Save to folder" popover trigger (FolderPlus icon) with the checklist.
 *  `dense` = the small row size. */
export function SaveToFolder({
  type,
  id,
  dense,
}: {
  type: SaveableType;
  id: string;
  dense?: boolean;
}) {
  const { me } = useMe();
  const toLogin = useLoginRedirect();
  const [open, setOpen] = useState(false);
  const { folderIds } = useStarState(type, id);
  const filed = folderIds.length > 0;

  return (
    <Popover.Root
      open={open}
      onOpenChange={(next) => {
        if (next && !me) return toLogin();
        setOpen(next);
      }}
    >
      <Popover.Trigger
        aria-label="Save to folder"
        title={filed ? `In ${folderIds.length} folder${folderIds.length === 1 ? '' : 's'}` : 'Save to folder'}
        className={cn(
          'inline-flex flex-none items-center justify-center rounded-lg transition-colors hover:bg-muted hover:text-foreground data-[popup-open]:bg-muted',
          dense ? 'size-6 rounded-md' : 'size-8',
          filed ? 'text-foreground' : 'text-muted-foreground',
        )}
      >
        <FolderPlus size={dense ? 13 : 15} />
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Positioner sideOffset={6} align="end" className="z-50">
          <Popover.Popup className={POPUP}>
            <FolderChecklist type={type} id={id} />
          </Popover.Popup>
        </Popover.Positioner>
      </Popover.Portal>
    </Popover.Root>
  );
}

/** Star + folder controls side by side — page headers and the detail panel.
 *  `compact` drops the "Star" label. */
export function SaveControls({
  type,
  id,
  compact,
}: {
  type: SaveableType;
  id: string;
  compact?: boolean;
}) {
  return (
    <div className="flex flex-none items-center gap-0.5">
      <StarButton type={type} id={id} compact={compact} />
      <SaveToFolder type={type} id={id} />
    </div>
  );
}
