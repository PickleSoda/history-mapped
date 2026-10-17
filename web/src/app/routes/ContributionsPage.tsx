import { ExternalLink, PencilLine } from 'lucide-react';
import { Link, useSearchParams } from 'react-router-dom';
import { DiffStats, DiffText } from '@/components/account/DiffText';
import { useMyContributions, useWithdrawContribution } from '@/hooks';
import { errorMessage } from '@/lib/api';
import { inAppPath } from '@/lib/atlas-links';
import { humanise } from '@/lib/entity-format';
import { CONTRIBUTION_STATUSES } from '@/lib/schemas/contribution';
import type { Contribution, ContributionStatus } from '@/lib/schemas/contribution';
import { cn } from '@/lib/utils';
import { AccountHeading, RequireUser } from './AccountLayout';

const STATUS_STYLE: Record<ContributionStatus, string> = {
  pending: 'bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-200',
  approved: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300',
  rejected: 'bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300',
  withdrawn: 'bg-muted text-muted-foreground',
};

const STATUS_LABEL: Record<ContributionStatus, string> = {
  pending: 'In review',
  approved: 'Approved',
  rejected: 'Not accepted',
  withdrawn: 'Withdrawn',
};

const TARGET_LABEL: Record<Contribution['target_type'], string> = {
  entity: 'Entity',
  relationship: 'Relationship',
  chronicle: 'Chronicle',
  chronicle_entry: 'Chronicle step',
};

const FIELD_LABEL: Record<string, string> = { narrative_text: 'Narrative', aliases: 'Other names' };

const dateFmt = new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' });
const when = (iso: string | null) => (iso ? dateFmt.format(new Date(iso)) : null);

function TargetLink({ c }: { c: Contribution }) {
  const label = c.target_label || 'Removed record';
  const path = inAppPath(c.public_url);
  const cls = 'font-heading text-[16px] font-semibold underline-offset-4 hover:underline';
  if (path) return <Link to={path} className={cls}>{label}</Link>;
  if (c.public_url) {
    return (
      <a href={c.public_url} className={cn(cls, 'inline-flex items-center gap-1')}>
        {label} <ExternalLink size={12} />
      </a>
    );
  }
  return <span className="font-heading text-[16px] font-semibold">{label}</span>;
}

function ContributionCard({ c }: { c: Contribution }) {
  const withdraw = useWithdrawContribution();
  return (
    <li className="rounded-xl border bg-card p-4">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
        <span className={cn('rounded-full px-2 py-0.5 text-[11px] font-medium', STATUS_STYLE[c.status])}>
          {STATUS_LABEL[c.status]}
        </span>
        <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
          {TARGET_LABEL[c.target_type]} · {FIELD_LABEL[c.field] ?? humanise(c.field)}
        </span>
        <DiffStats {...c.stats} />
        <span className="ml-auto font-mono text-[11px] text-muted-foreground">{when(c.created_at)}</span>
      </div>
      <div className="mt-2">
        <TargetLink c={c} />
      </div>
      <div className="mt-3 rounded-lg border bg-muted/30 px-3 py-2.5">
        <DiffText chunks={c.diff} />
      </div>
      {c.note && (
        <p className="mt-3 text-[12.5px] text-foreground/80">
          <span className="font-medium text-muted-foreground">Your note: </span>
          {c.note}
        </p>
      )}
      {c.review_note && (
        <p className="mt-2 border-l-[3px] pl-3 text-[12.5px] text-foreground/80">
          <span className="font-medium text-muted-foreground">
            Reviewer{c.reviewed_at ? `, ${when(c.reviewed_at)}` : ''}:{' '}
          </span>
          {c.review_note}
        </p>
      )}
      {c.status === 'pending' && (
        <div className="mt-3 flex items-center justify-end gap-3">
          {withdraw.error != null && (
            <span className="text-[12px] text-destructive">{errorMessage(withdraw.error)}</span>
          )}
          <button
            type="button"
            onClick={() => withdraw.mutate(c.id)}
            disabled={withdraw.isPending}
            className="h-7 rounded-md px-2.5 text-[12px] font-medium text-muted-foreground hover:bg-muted hover:text-foreground disabled:opacity-40"
          >
            {withdraw.isPending ? 'Withdrawing…' : 'Withdraw'}
          </button>
        </div>
      )}
    </li>
  );
}

function ContributionsContent() {
  const [params, setParams] = useSearchParams();
  const statusParam = params.get('status');
  const status = (CONTRIBUTION_STATUSES as readonly string[]).includes(statusParam ?? '')
    ? (statusParam as ContributionStatus)
    : null;
  const page = Math.max(1, Number(params.get('page')) || 1);
  const { data, isLoading, isError, isPlaceholderData } = useMyContributions({ status, page });

  const go = (next: { status?: ContributionStatus | null; page?: number }) => {
    const p = new URLSearchParams();
    const s = next.status !== undefined ? next.status : status;
    if (s) p.set('status', s);
    if (next.page && next.page > 1) p.set('page', String(next.page));
    setParams(p);
  };

  const items = data?.data ?? [];
  const meta = data?.meta;

  return (
    <>
      <div className="mb-5 flex flex-wrap gap-1" role="group" aria-label="Filter by status">
        {[null, ...CONTRIBUTION_STATUSES].map((s) => (
          <button
            key={s ?? 'all'}
            type="button"
            aria-pressed={status === s}
            onClick={() => go({ status: s })}
            className={cn(
              'h-7 rounded-full border px-3 text-[12px] transition-colors',
              status === s ? 'border-foreground bg-foreground text-background' : 'text-muted-foreground hover:bg-muted hover:text-foreground',
            )}
          >
            {s ? STATUS_LABEL[s] : 'All'}
          </button>
        ))}
      </div>

      {isLoading && <p className="py-10 text-[13px] text-muted-foreground">Loading…</p>}
      {isError && <p className="py-10 text-[13px] text-destructive">Could not load your contributions.</p>}
      {data && items.length === 0 && (
        <div className="rounded-xl border border-dashed px-6 py-12 text-center">
          <PencilLine size={22} className="mx-auto text-muted-foreground" />
          <p className="mt-3 font-heading text-[16px] font-semibold">
            {status ? `Nothing ${STATUS_LABEL[status].toLowerCase()}` : 'No suggestions yet'}
          </p>
          <p className="mx-auto mt-1 max-w-sm text-[13px] text-muted-foreground">
            Spot something wrong or missing? Use “Suggest edit” next to any name, other names, summary or narrative in the atlas.
          </p>
        </div>
      )}
      {items.length > 0 && (
        <ul className={cn('space-y-3', isPlaceholderData && 'opacity-60')}>
          {items.map((c) => (
            <ContributionCard key={c.id} c={c} />
          ))}
        </ul>
      )}

      {meta && meta.last_page > 1 && (
        <nav aria-label="Pages" className="mt-6 flex items-center justify-between text-[12px]">
          <button
            type="button"
            disabled={meta.current_page <= 1}
            onClick={() => go({ page: meta.current_page - 1 })}
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
            onClick={() => go({ page: meta.current_page + 1 })}
            className="h-8 rounded-lg border bg-card px-3 font-medium hover:bg-muted disabled:opacity-40"
          >
            Next
          </button>
        </nav>
      )}
    </>
  );
}

/** `/contributions` — the user's suggested edits and where each one stands. */
export function ContributionsPage() {
  return (
    <RequireUser>
      <div className="mx-auto max-w-3xl">
        <AccountHeading title="My contributions">
          Corrections you’ve suggested. A reviewer approves or declines each one; approved changes go live in
          the atlas.
        </AccountHeading>
        <ContributionsContent />
      </div>
    </RequireUser>
  );
}
