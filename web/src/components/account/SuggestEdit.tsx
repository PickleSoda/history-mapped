/**
 * "Suggest edit": a reader proposes a correction to one text field — or text
 * for a field that has none yet; staff review it (as a diff) before it goes
 * live. The dialog previews the change with the same word diff reviewers see.
 */
import { Dialog } from '@base-ui/react/dialog';
import { CheckCircle2, PencilLine, X } from 'lucide-react';
import { useId, useMemo, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { useLoginRedirect, useMe, useSubmitContribution } from '@/hooks';
import { errorMessage, fieldErrors } from '@/lib/api';
import type { ContributionTargetType } from '@/lib/schemas/contribution';
import { diffStats, diffWords, normaliseList, normaliseText } from '@/lib/text-diff';
import { cn } from '@/lib/utils';
import { DiffStats, DiffText } from './DiffText';
import { FIELD } from './styles';

/**
 * How a field is edited: one line (names / titles), a list of one item per
 * line (aliases — normalised like the server: trimmed, de-duplicated, sorted),
 * or free prose.
 */
type FieldKind = 'line' | 'list' | 'prose';
const LINE_FIELDS = new Set(['name', 'title']);
const LIST_FIELDS = new Set(['aliases']);
const fieldKind = (field: string): FieldKind =>
  LINE_FIELDS.has(field) ? 'line' : LIST_FIELDS.has(field) ? 'list' : 'prose';
const MAX_LENGTH: Record<FieldKind, number> = { line: 255, list: 10_000, prose: 10_000 };

/** "Suggest a summary" / "Suggest an alias" / "Suggest other names". */
function suggestTitle(fieldLabel: string, kind: FieldKind): string {
  const label = fieldLabel.toLowerCase();
  if (kind === 'list') return `Suggest ${label}`;
  return `Suggest ${/^[aeiou]/.test(label) ? 'an' : 'a'} ${label}`;
}

export interface SuggestEditTarget {
  targetType: ContributionTargetType;
  targetId: string;
  /** API field name, e.g. `summary`, `narrative_text`. */
  field: string;
  /** Human name of the field ("Summary"). */
  fieldLabel: string;
  /** What is being edited ("Roman Empire", "Step 3 of …"). */
  targetLabel: string;
  /** The field's text now; empty for a missing field. A list field takes one
   *  item per line (see `listText`). */
  currentText: string;
}

function SuggestEditBody({ target }: { target: SuggestEditTarget }) {
  const { targetType, targetId, field, fieldLabel, targetLabel } = target;
  const kind = fieldKind(field);
  const single = kind === 'line';
  // List fields are compared and sent in their canonical (server) form.
  const base = kind === 'list' ? normaliseList(target.currentText) : target.currentText;
  const [draft, setDraft] = useState(base);
  const [note, setNote] = useState('');
  const submit = useSubmitContribution();
  const draftId = useId();
  const hintId = useId();
  const noteId = useId();

  const proposed = kind === 'list' ? normaliseList(draft) : draft;
  const chunks = useMemo(() => diffWords(base, proposed, kind === 'list'), [base, proposed, kind]);
  const stats = useMemo(() => diffStats(chunks), [chunks]);
  const missing = normaliseText(base) === '';
  const changed = kind === 'list' ? proposed !== base : normaliseText(draft) !== normaliseText(base);
  const blank = single && !draft.trim();
  const errors = fieldErrors(submit.error);
  const general =
    submit.error && !errors.proposed_text && !errors.note ? errorMessage(submit.error) : null;

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!changed || blank) return;
    submit.mutate({
      target_type: targetType,
      target_id: targetId,
      field,
      proposed_text: single ? draft.trim() : proposed,
      note: note.trim() || null,
    });
  };

  if (submit.isSuccess) {
    return (
      <div className="flex flex-col items-center px-2 py-6 text-center">
        <CheckCircle2 size={34} className="text-emerald-600 dark:text-emerald-400" />
        <Dialog.Title className="mt-3 font-heading text-[19px] font-semibold">Sent for review</Dialog.Title>
        <Dialog.Description className="mt-1.5 max-w-sm text-[13px] text-muted-foreground">
          Thanks — a reviewer will look at your {missing ? 'suggested' : 'change to the'}{' '}
          {fieldLabel.toLowerCase()} {missing ? 'for' : 'of'} {targetLabel}.
        </Dialog.Description>
        <div className="mt-5 flex items-center gap-2">
          <Link
            to="/contributions"
            className="inline-flex h-8 items-center rounded-lg border bg-card px-3 text-[12px] font-medium hover:bg-muted"
          >
            My contributions
          </Link>
          <Dialog.Close className="inline-flex h-8 items-center rounded-lg bg-primary px-3 text-[12px] font-medium text-primary-foreground hover:bg-primary/85">
            Done
          </Dialog.Close>
        </div>
      </div>
    );
  }

  return (
    <form onSubmit={onSubmit} className="flex min-h-0 flex-col">
      <div className="flex items-start gap-3 border-b px-5 pb-3 pt-4">
        <div className="min-w-0 flex-1">
          <Dialog.Title className="font-heading text-[18px] font-semibold">
            {missing ? suggestTitle(fieldLabel, kind) : 'Suggest an edit'}
          </Dialog.Title>
          <Dialog.Description className="mt-0.5 text-[12px] text-muted-foreground">
            {fieldLabel} · <span className="text-foreground/80">{targetLabel}</span>.{' '}
            {missing && `There ${kind === 'list' ? 'are none' : 'is none'} yet. `}A reviewer checks every
            change before it goes live.
          </Dialog.Description>
        </div>
        <Dialog.Close
          aria-label="Close"
          className="grid size-8 flex-none place-items-center rounded-lg text-muted-foreground hover:bg-muted hover:text-foreground"
        >
          <X size={16} />
        </Dialog.Close>
      </div>

      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-5 py-4">
        <div>
          <label htmlFor={draftId} className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
            {fieldLabel}
          </label>
          {kind === 'list' && (
            <p id={hintId} className="-mt-1 mb-1.5 text-[11px] text-muted-foreground">
              One name per line. Order and duplicates don’t matter.
            </p>
          )}
          {single ? (
            <input
              id={draftId}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              maxLength={MAX_LENGTH.line}
              placeholder={missing ? fieldLabel : undefined}
              aria-invalid={errors.proposed_text || blank ? true : undefined}
              className={FIELD}
              data-autofocus
            />
          ) : (
            <textarea
              id={draftId}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              maxLength={MAX_LENGTH[kind]}
              rows={
                kind === 'list'
                  ? Math.min(12, Math.max(4, base.split('\n').length + 1))
                  : Math.min(12, Math.max(4, Math.ceil(base.length / 70)))
              }
              placeholder={kind === 'list' ? 'One name per line' : missing ? `Write the ${fieldLabel.toLowerCase()}…` : undefined}
              aria-describedby={kind === 'list' ? hintId : undefined}
              aria-invalid={errors.proposed_text ? true : undefined}
              className={cn(FIELD, 'resize-y leading-relaxed')}
              data-autofocus
            />
          )}
          {errors.proposed_text && <p className="mt-1 text-[11px] text-destructive">{errors.proposed_text}</p>}
          {blank && <p className="mt-1 text-[11px] text-destructive">The {fieldLabel.toLowerCase()} can’t be empty.</p>}
        </div>

        <div>
          <div className="mb-1.5 flex items-center justify-between gap-2">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
              Your change
            </span>
            {changed && <DiffStats {...stats} />}
          </div>
          <div aria-live="polite" className="rounded-lg border bg-muted/30 px-3 py-2.5">
            {changed ? (
              <DiffText chunks={chunks} />
            ) : (
              <p className="text-[12px] text-muted-foreground">
                {missing ? 'Write above to see your suggestion here.' : 'Edit the text above to see your change here.'}
              </p>
            )}
          </div>
        </div>

        <div>
          <label htmlFor={noteId} className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
            Why this change? <span className="font-normal normal-case tracking-normal">(optional — a source helps)</span>
          </label>
          <textarea
            id={noteId}
            value={note}
            onChange={(e) => setNote(e.target.value)}
            maxLength={1000}
            rows={2}
            aria-invalid={errors.note ? true : undefined}
            placeholder="e.g. Date corrected per Britannica, ‘Battle of Marathon’"
            className={cn(FIELD, 'resize-y')}
          />
          {errors.note && <p className="mt-1 text-[11px] text-destructive">{errors.note}</p>}
        </div>
        {general && <p className="text-[12px] text-destructive">{general}</p>}
      </div>

      <div className="flex items-center justify-end gap-2 border-t px-5 py-3">
        <Dialog.Close className="inline-flex h-8 items-center rounded-lg px-3 text-[12px] font-medium text-muted-foreground hover:bg-muted hover:text-foreground">
          Cancel
        </Dialog.Close>
        <button
          type="submit"
          disabled={!changed || blank || submit.isPending}
          className="inline-flex h-8 items-center rounded-lg bg-primary px-3 text-[12px] font-medium text-primary-foreground hover:bg-primary/85 disabled:opacity-40"
        >
          {submit.isPending ? 'Sending…' : 'Submit for review'}
        </button>
      </div>
    </form>
  );
}

/**
 * Pencil button that opens the suggest-edit dialog. Guests are sent to sign
 * in; signed-in users without the contribute permission don't see it. `label`
 * replaces the default "Suggest edit" text (e.g. "Suggest a summary" on an
 * empty field); `compact` shows the icon only.
 */
export function SuggestEditButton({
  compact,
  className,
  label: text,
  ...target
}: SuggestEditTarget & { compact?: boolean; className?: string; label?: string }) {
  const { me } = useMe();
  const toLogin = useLoginRedirect();
  const [open, setOpen] = useState(false);
  const popupRef = useRef<HTMLDivElement>(null);
  if (me && !me.can.contribute) return null;

  const label = text ?? `Suggest an edit to the ${target.fieldLabel.toLowerCase()}`;
  return (
    <Dialog.Root
      open={open}
      onOpenChange={(next) => {
        if (next && !me) return toLogin();
        setOpen(next);
      }}
    >
      <Dialog.Trigger
        aria-label={compact ? label : undefined}
        title={label}
        className={cn(
          'inline-flex flex-none items-center justify-center gap-1 rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground data-[popup-open]:bg-muted',
          compact ? 'size-6' : 'h-6 px-1.5 text-[11px] font-medium',
          className,
        )}
      >
        <PencilLine size={compact ? 13 : 12} />
        {!compact && (text ?? 'Suggest edit')}
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Backdrop className="fixed inset-0 z-50 bg-black/30 backdrop-blur-sm transition-opacity duration-150 data-[ending-style]:opacity-0 data-[starting-style]:opacity-0 motion-reduce:transition-none" />
        <Dialog.Popup
          ref={popupRef}
          // Start in the text field (not on Close) — except on touch, where
          // focusing would throw up the keyboard over the preview.
          initialFocus={(type) =>
            type === 'touch' ? true : (popupRef.current?.querySelector<HTMLElement>('[data-autofocus]') ?? true)
          }
          className="fixed left-1/2 top-[8dvh] z-50 flex max-h-[84dvh] w-[min(640px,calc(100vw-1.5rem))] -translate-x-1/2 flex-col overflow-hidden rounded-2xl border bg-popover text-popover-foreground shadow-2xl outline-none transition-[opacity,scale] duration-150 data-[ending-style]:scale-[0.98] data-[ending-style]:opacity-0 data-[starting-style]:scale-[0.98] data-[starting-style]:opacity-0 motion-reduce:transition-none">
          <SuggestEditBody target={target} />
        </Dialog.Popup>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
