/**
 * Text contributions (suggested edits) as served to the admin review pages.
 * Contract: docs/superpowers/specs/2026-10-18-user-accounts-saved-contributions-design.md §4.
 */

export type ContributionStatus =
    | 'pending'
    | 'approved'
    | 'rejected'
    | 'withdrawn';

/** `edit` corrects one text field; `create` proposes a new entity or relationship. */
export type ContributionKind = 'edit' | 'create';

/** Where it was submitted: the public atlas, or an MCP client such as Claude. */
export type ContributionSource = 'atlas' | 'mcp';

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
    kind: ContributionKind;
    source: ContributionSource;
    /** The MCP client's name, when source is `mcp`. */
    client: string | null;
    /** One line describing a `create` proposal; null for edits. */
    summary: string | null;
    target_type: ContributionTargetType;
    /** Null for a `create` proposal until it is approved (then the created record's id). */
    target_id: string | null;
    /** Empty for a `create` proposal. */
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
    kind: string;
};

export type ContributionIndexProps = {
    contributions: PaginatedContributions;
    filters: ContributionFilters;
    counts: Record<ContributionStatus, number>;
};

export type ProposalDuplicate = {
    entity_id: string;
    name: string;
    entity_type: string;
    start_year: number | null;
    end_year: number | null;
    admin_url: string;
    public_url: string;
};

/** A `create` proposal as the review page shows it. */
export type ContributionProposal = {
    rows: { label: string; value: string }[];
    possible_duplicates: ProposalDuplicate[];
    /** Entity proposals a relationship proposal points at. */
    depends_on: {
        id: number;
        label: string;
        status: ContributionStatus | 'missing';
        url: string | null;
    }[];
    /** A relationship whose entity proposal is not approved yet cannot be approved. */
    blocked: boolean;
    /** Pending relationship proposals waiting on this entity proposal. */
    waiting: { id: number; label: string; url: string }[];
};

export type ContributionShowProps = {
    contribution: ContributionDetail;
    /** Set for `create` proposals; null for edits. */
    proposal: ContributionProposal | null;
    /** Null when the target record has been deleted. */
    current_text: string | null;
    /** Current → proposed, only when the contribution is stale. */
    current_diff: Diff | null;
    admin_url: string | null;
    public_url: string | null;
    other_pending: number;
};
