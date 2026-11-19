import { Head, Link, useForm } from '@inertiajs/react';
import {
    AlertTriangle,
    ArrowLeft,
    Check,
    ExternalLink,
    PencilLine,
    X,
} from 'lucide-react';
import AlertError from '@/components/alert-error';
import {
    formatDateTime,
    SourceBadge,
    StaleBadge,
    StatusBadge,
    TargetBadges,
} from '@/components/contribution-badges';
import { ContributionDiffViewer } from '@/components/contribution-diff-viewer';
import InputError from '@/components/input-error';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import AppLayout from '@/layouts/app-layout';
import type {
    BreadcrumbItem,
    ContributionDetail,
    ContributionProposal,
    ContributionShowProps,
} from '@/types';

type ReviewForm = {
    review_note: string;
    force: boolean;
    keep_old_name_as_alias: boolean;
};

function ReviewPanel({
    contribution,
    stale,
    targetMissing,
    blocked,
}: {
    contribution: ContributionDetail;
    stale: boolean;
    targetMissing: boolean;
    blocked: boolean;
}) {
    const isCreate = contribution.kind === 'create';
    const form = useForm<ReviewForm>({
        review_note: '',
        force: false,
        keep_old_name_as_alias: false,
    });
    // Renaming an entity can keep the old name searchable as an alias.
    const isRename =
        !isCreate &&
        contribution.target_type === 'entity' &&
        contribution.field === 'name';
    const errors = form.errors as Partial<Record<string, string>>;
    const otherErrors = Object.entries(errors)
        .filter(
            ([key]) =>
                !['review_note', 'force', 'keep_old_name_as_alias'].includes(
                    key,
                ),
        )
        .map(([, message]) => message)
        .filter((m): m is string => Boolean(m));

    const approve = () => {
        form.transform((data) => ({
            review_note: data.review_note,
            ...(stale && { force: data.force }),
            ...(isRename &&
                data.keep_old_name_as_alias && {
                    keep_old_name_as_alias: true,
                }),
        }));
        form.post(`/contributions/${contribution.id}/approve`, {
            preserveScroll: true,
        });
    };

    const reject = () => {
        form.transform((data) => ({ review_note: data.review_note }));
        form.post(`/contributions/${contribution.id}/reject`, {
            preserveScroll: true,
        });
    };

    const approveBlocked =
        targetMissing || blocked || (stale && !form.data.force);

    return (
        <Card>
            <CardHeader>
                <CardTitle>Review</CardTitle>
                <CardDescription>
                    {isCreate
                        ? `Approving creates the ${contribution.target_type} (verified, credited to the contributor). Nothing exists until you do.`
                        : 'Approving writes the proposed text to the record.'}{' '}
                    The contributor sees your note either way.
                </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
                {otherErrors.length > 0 && (
                    <AlertError
                        errors={otherErrors}
                        title={
                            errors.conflict
                                ? 'The text changed before approval.'
                                : errors.dependency
                                  ? 'It cannot be approved yet.'
                                  : undefined
                        }
                    />
                )}

                <div className="grid gap-2">
                    <Label htmlFor="review_note">
                        Note to the contributor (optional)
                    </Label>
                    <Textarea
                        id="review_note"
                        value={form.data.review_note}
                        onChange={(e) =>
                            form.setData('review_note', e.target.value)
                        }
                        rows={3}
                        maxLength={1000}
                        placeholder="Why this was approved or rejected…"
                    />
                    <InputError message={errors.review_note} />
                </div>

                {isRename && !targetMissing && (
                    <div className="flex items-start gap-2">
                        <Checkbox
                            id="keep_old_name_as_alias"
                            checked={form.data.keep_old_name_as_alias}
                            onCheckedChange={(v) =>
                                form.setData(
                                    'keep_old_name_as_alias',
                                    v === true,
                                )
                            }
                        />
                        <div className="grid gap-1">
                            <Label htmlFor="keep_old_name_as_alias">
                                Keep the old name as an alias
                            </Label>
                            <p className="text-xs text-muted-foreground">
                                For a real rename, so searches for the old name
                                still find it. Leave off when fixing a typo.
                            </p>
                            <InputError
                                message={errors.keep_old_name_as_alias}
                            />
                        </div>
                    </div>
                )}

                {stale && !targetMissing && (
                    <div className="flex items-start gap-2">
                        <Checkbox
                            id="force"
                            checked={form.data.force}
                            onCheckedChange={(v) =>
                                form.setData('force', v === true)
                            }
                        />
                        <div className="grid gap-1">
                            <Label htmlFor="force">
                                Overwrite the current text
                            </Label>
                            <p className="text-xs text-muted-foreground">
                                The record changed after this was submitted.
                                Approving replaces the current text with the
                                proposal, discarding the later change.
                            </p>
                            <InputError message={errors.force} />
                        </div>
                    </div>
                )}

                <div className="flex flex-wrap gap-2">
                    <Button
                        onClick={approve}
                        disabled={form.processing || approveBlocked}
                    >
                        <Check className="size-4" />
                        {isCreate ? 'Approve and create' : 'Approve and apply'}
                    </Button>
                    <Button
                        variant="outline"
                        onClick={reject}
                        disabled={form.processing}
                    >
                        <X className="size-4" />
                        Reject
                    </Button>
                </div>
            </CardContent>
        </Card>
    );
}

function ProposalDetails({ proposal }: { proposal: ContributionProposal }) {
    return (
        <>
            {proposal.depends_on.length > 0 && (
                <Alert
                    variant={proposal.blocked ? 'destructive' : 'default'}
                    className={
                        proposal.blocked
                            ? undefined
                            : 'border-emerald-300 bg-emerald-50 text-emerald-950 dark:border-emerald-500/40 dark:bg-emerald-950/40 dark:text-emerald-100'
                    }
                >
                    <AlertTriangle />
                    <AlertTitle>
                        {proposal.blocked
                            ? 'Waiting on an entity proposal'
                            : 'Entity proposals it points at'}
                    </AlertTitle>
                    <AlertDescription>
                        <ul className="list-disc pl-4">
                            {proposal.depends_on.map((d) => (
                                <li key={d.id}>
                                    {d.url ? (
                                        <Link
                                            href={d.url}
                                            className="underline"
                                        >
                                            {d.label} (#{d.id})
                                        </Link>
                                    ) : (
                                        `${d.label} (#${d.id})`
                                    )}
                                    : {d.status}
                                </li>
                            ))}
                        </ul>
                        {proposal.blocked &&
                            'Approve the entity proposal first; this relationship then resolves to the entity it creates.'}
                    </AlertDescription>
                </Alert>
            )}

            {proposal.possible_duplicates.length > 0 && (
                <Alert className="border-amber-300 bg-amber-50 text-amber-950 dark:border-amber-500/40 dark:bg-amber-950/40 dark:text-amber-100">
                    <AlertTriangle />
                    <AlertTitle>
                        Possible duplicates already in the atlas
                    </AlertTitle>
                    <AlertDescription className="text-amber-900/90 dark:text-amber-100/80">
                        <p>
                            Same name and type, close in time. The contributor
                            was told and confirmed this is a different entity.
                        </p>
                        <ul className="mt-1 list-disc pl-4">
                            {proposal.possible_duplicates.map((d) => (
                                <li key={d.entity_id}>
                                    <Link
                                        href={d.admin_url}
                                        className="underline"
                                    >
                                        {d.name}
                                    </Link>{' '}
                                    ({d.entity_type.replace(/_/g, ' ')}
                                    {d.start_year !== null
                                        ? `, ${d.start_year}${d.end_year !== null ? ` to ${d.end_year}` : ''}`
                                        : ', undated'}
                                    ){' · '}
                                    <a
                                        href={d.public_url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="underline"
                                    >
                                        atlas
                                    </a>
                                </li>
                            ))}
                        </ul>
                    </AlertDescription>
                </Alert>
            )}

            {proposal.waiting.length > 0 && (
                <p className="text-sm text-muted-foreground">
                    {proposal.waiting.length} relationship{' '}
                    {proposal.waiting.length === 1
                        ? 'proposal waits'
                        : 'proposals wait'}{' '}
                    on this one:{' '}
                    {proposal.waiting.map((w, i) => (
                        <span key={w.id}>
                            {i > 0 && ', '}
                            <Link href={w.url} className="underline">
                                {w.label}
                            </Link>
                        </span>
                    ))}
                    . Rejecting this closes them too.
                </p>
            )}

            <Card>
                <CardHeader>
                    <CardTitle className="text-base">Proposed record</CardTitle>
                    <CardDescription>
                        Exactly what will be created on approval.
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    <dl className="grid grid-cols-[8rem_1fr] gap-x-4 gap-y-2 text-sm">
                        {proposal.rows.map((r) => (
                            <div key={r.label} className="contents">
                                <dt className="text-muted-foreground">
                                    {r.label}
                                </dt>
                                <dd className="break-words whitespace-pre-wrap">
                                    {r.value}
                                </dd>
                            </div>
                        ))}
                    </dl>
                </CardContent>
            </Card>
        </>
    );
}

function ReviewOutcome({ contribution }: { contribution: ContributionDetail }) {
    return (
        <Card>
            <CardHeader>
                <CardTitle className="flex items-center gap-2">
                    Review <StatusBadge status={contribution.status} />
                </CardTitle>
                <CardDescription>
                    {contribution.status === 'withdrawn'
                        ? `Withdrawn by the contributor${contribution.reviewed_at ? ` on ${formatDateTime(contribution.reviewed_at)}` : ''}.`
                        : `${contribution.reviewer?.name ?? 'A reviewer'} · ${formatDateTime(contribution.reviewed_at)}`}
                </CardDescription>
            </CardHeader>
            {contribution.review_note && (
                <CardContent>
                    <p className="text-sm whitespace-pre-wrap">
                        {contribution.review_note}
                    </p>
                </CardContent>
            )}
        </Card>
    );
}

export default function ContributionShow({
    contribution,
    current_text,
    current_diff,
    admin_url,
    public_url,
    other_pending,
    proposal,
}: ContributionShowProps) {
    const pending = contribution.status === 'pending';
    const isCreate = proposal !== null;
    const targetMissing = !isCreate && current_text === null;
    const stale = contribution.is_stale;

    const breadcrumbs: BreadcrumbItem[] = [
        { title: 'Dashboard', href: '/dashboard' },
        { title: 'Contributions', href: '/contributions' },
        {
            title: `#${contribution.id}`,
            href: `/contributions/${contribution.id}`,
        },
    ];

    return (
        <AppLayout breadcrumbs={breadcrumbs}>
            <Head title={`Contribution #${contribution.id}`} />

            <div className="flex max-w-5xl flex-col gap-4 p-4">
                <Link
                    href="/contributions"
                    className="inline-flex w-fit items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
                >
                    <ArrowLeft className="size-4" />
                    All contributions
                </Link>

                {/* Header */}
                <div className="flex flex-col gap-2">
                    <div className="flex flex-wrap items-center gap-1.5">
                        <TargetBadges
                            type={contribution.target_type}
                            field={contribution.field}
                            kind={contribution.kind}
                        />
                        <SourceBadge
                            source={contribution.source}
                            client={contribution.client}
                        />
                        <StatusBadge status={contribution.status} />
                        {stale && pending && <StaleBadge />}
                    </div>
                    <h1 className="text-2xl font-bold tracking-tight">
                        {contribution.target_label}
                    </h1>
                    <p className="text-sm text-muted-foreground">
                        #{contribution.id} · submitted by{' '}
                        {contribution.user
                            ? `${contribution.user.name} (${contribution.user.email})`
                            : 'a deleted user'}{' '}
                        on {formatDateTime(contribution.created_at)}
                    </p>
                    {(admin_url || public_url) && (
                        <div className="flex flex-wrap gap-2">
                            {admin_url && (
                                <Button variant="outline" size="sm" asChild>
                                    <Link href={admin_url}>
                                        <PencilLine className="size-4" />
                                        Open in admin
                                    </Link>
                                </Button>
                            )}
                            {public_url && (
                                <Button variant="outline" size="sm" asChild>
                                    <a
                                        href={public_url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                    >
                                        <ExternalLink className="size-4" />
                                        View on atlas
                                    </a>
                                </Button>
                            )}
                        </div>
                    )}
                </div>

                {contribution.note && (
                    <Card>
                        <CardHeader>
                            <CardTitle className="text-base">
                                Contributor’s note
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            <blockquote className="border-l-2 pl-3 text-sm whitespace-pre-wrap text-foreground/90">
                                {contribution.note}
                            </blockquote>
                        </CardContent>
                    </Card>
                )}

                {pending && targetMissing && (
                    <Alert variant="destructive">
                        <AlertTriangle />
                        <AlertTitle>The target no longer exists</AlertTitle>
                        <AlertDescription>
                            The record this contribution edits has been deleted,
                            so it can only be rejected.
                        </AlertDescription>
                    </Alert>
                )}

                {pending && stale && !targetMissing && (
                    <Alert className="border-amber-300 bg-amber-50 text-amber-950 dark:border-amber-500/40 dark:bg-amber-950/40 dark:text-amber-100">
                        <AlertTriangle />
                        <AlertTitle>
                            The text has changed since this was submitted
                        </AlertTitle>
                        <AlertDescription className="text-amber-900/90 dark:text-amber-100/80">
                            The diff below is against the text the contributor
                            saw. Compare the proposal with the current text
                            before approving — approval would overwrite the
                            newer edit.
                        </AlertDescription>
                    </Alert>
                )}

                {pending && other_pending > 0 && (
                    <p className="text-sm text-muted-foreground">
                        {other_pending} other pending{' '}
                        {other_pending === 1
                            ? 'contribution edits'
                            : 'contributions edit'}{' '}
                        this same field.
                    </p>
                )}

                {proposal && <ProposalDetails proposal={proposal} />}

                {/* Diff */}
                {!isCreate && (
                    <Card>
                        <CardHeader>
                            <CardTitle className="text-base">
                                Proposed change
                            </CardTitle>
                            <CardDescription>
                                Against the text as it was when submitted.
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            <ContributionDiffViewer
                                diff={contribution.diff}
                                stats={contribution.stats}
                                baseLabel="Submitted against"
                                proposedLabel="Proposed text"
                            />
                        </CardContent>
                    </Card>
                )}

                {stale && current_diff && (
                    <Card>
                        <CardHeader>
                            <CardTitle className="text-base">
                                Against the current text
                            </CardTitle>
                            <CardDescription>
                                What approving would change today.
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            <ContributionDiffViewer
                                diff={current_diff}
                                baseLabel="Current text"
                                proposedLabel="Proposed text"
                            />
                        </CardContent>
                    </Card>
                )}

                {pending ? (
                    <ReviewPanel
                        contribution={contribution}
                        stale={stale}
                        targetMissing={targetMissing}
                        blocked={proposal?.blocked ?? false}
                    />
                ) : (
                    <ReviewOutcome contribution={contribution} />
                )}
            </div>
        </AppLayout>
    );
}
