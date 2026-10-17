/**
 * Text contributions (suggested edits) as served to the admin review pages.
 * Contract: docs/superpowers/specs/2026-10-18-user-accounts-saved-contributions-design.md §4.
 */

export type ContributionStatus =
    | 'pending'
    | 'approved'
    | 'rejected'
    | 'withdrawn';

export type ContributionTargetType =
    | 'entity'
    | 'relationship'
    | 'chronicle'
    | 'chronicle_entry';

/**
 * One diff op: `=` unchanged, `-` removed, `+` added. Concatenating the `=`/`-`
 * texts gives the base text; `=`/`+` gives the proposed text.
 */
export type DiffOp = ['=' | '-' | '+', string];

export type Diff = DiffOp[];

export type DiffStats = {
    added: number;
    removed: number;
};

export type ContributionRow = {
    id: number;
    target_type: ContributionTargetType;
    target_id: string;
    field: string;
    target_label: string;
    status: ContributionStatus;
    note: string | null;
    stats: DiffStats;
    is_stale: boolean;
    user: { id: number; name: string; email: string } | null;
    reviewer: { id: number; name: string } | null;
    created_at: string;
    reviewed_at: string | null;
};

export type ContributionDetail = ContributionRow & {
    base_text: string;
    proposed_text: string;
    diff: Diff;
    review_note: string | null;
};

export type PaginatedContributions = {
    data: ContributionRow[];
    current_page: number;
    last_page: number;
    per_page: number;
    total: number;
    from: number | null;
    to: number | null;
};

export type ContributionFilters = {
    status: string;
    type: string;
};

export type ContributionIndexProps = {
    contributions: PaginatedContributions;
    filters: ContributionFilters;
    counts: Record<ContributionStatus, number>;
};

export type ContributionShowProps = {
    contribution: ContributionDetail;
    /** Null when the target record has been deleted. */
    current_text: string | null;
    /** Current → proposed, only when the contribution is stale. */
    current_diff: Diff | null;
    admin_url: string | null;
    public_url: string | null;
    other_pending: number;
};
