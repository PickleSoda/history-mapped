<?php

declare(strict_types=1);

namespace App\Http\Controllers\Admin;

use App\Actions\Contribution\ApproveContributionAction;
use App\Actions\Contribution\CloseContributionAction;
use App\Actions\Contribution\DescribeContributionTargetsAction;
use App\Enums\ContributionStatus;
use App\Enums\ContributionTargetType;
use App\Http\Controllers\Controller;
use App\Http\Requests\ReviewContributionRequest;
use App\Models\Contribution;
use App\Support\ContributionFields;
use Illuminate\Http\RedirectResponse;
use Illuminate\Http\Request;
use Inertia\Inertia;
use Inertia\Response;

/**
 * Review queue for text corrections submitted from the public atlas: list,
 * diff viewer, approve (applies the text) and reject.
 */
class ContributionController extends Controller
{
    public function index(Request $request, DescribeContributionTargetsAction $describe): Response
    {
        $status = (string) $request->query('status', ContributionStatus::Pending->value);
        $type = (string) $request->query('type', '');

        $query = Contribution::query()
            ->with(['user:id,name,email', 'reviewer:id,name'])
            // Oldest pending first (a queue); reviewed ones newest first.
            ->when($status === ContributionStatus::Pending->value, fn ($q) => $q->oldest('created_at'), fn ($q) => $q->latest('created_at'))
            ->orderBy('id');
        if (ContributionStatus::tryFrom($status) !== null) {
            $query->where('status', $status);
        }
        if (ContributionTargetType::tryFrom($type) !== null) {
            $query->where('target_type', $type);
        }

        $page = $query->paginate(25)->withQueryString();
        $info = $describe($page->getCollection());

        $counts = Contribution::query()
            ->when(ContributionTargetType::tryFrom($type) !== null, fn ($q) => $q->where('target_type', $type))
            ->toBase()
            ->selectRaw('status, count(*) as n')
            ->groupBy('status')
            ->pluck('n', 'status');

        return Inertia::render('contributions/index', [
            'contributions' => $page->through(fn (Contribution $c) => self::row($c, $info)),
            'filters' => ['status' => $status, 'type' => $type],
            'counts' => collect(ContributionStatus::cases())
                ->mapWithKeys(fn (ContributionStatus $s) => [$s->value => (int) ($counts[$s->value] ?? 0)]),
        ]);
    }

    public function show(Contribution $contribution, DescribeContributionTargetsAction $describe): Response
    {
        $contribution->load(['user:id,name,email', 'reviewer:id,name']);
        $info = $describe([$contribution]);
        $target = $info[DescribeContributionTargetsAction::key($contribution)] ?? null;
        $current = $target === null ? null : (string) ($target['fields'][$contribution->field] ?? '');
        $stale = $contribution->isPending() && $contribution->isStaleAgainst($current);

        return Inertia::render('contributions/show', [
            'contribution' => [
                ...self::row($contribution, $info),
                'base_text' => $contribution->base_text,
                'proposed_text' => $contribution->proposed_text,
                'diff' => $contribution->diff,
                'review_note' => $contribution->review_note,
            ],
            'current_text' => $current,
            'current_diff' => $stale && $current !== null
                ? ContributionFields::diff($contribution->field, $current, $contribution->proposed_text)
                : null,
            'admin_url' => $target['admin_url'] ?? null,
            'public_url' => $target['public_url'] ?? null,
            'other_pending' => Contribution::query()
                ->where('status', ContributionStatus::Pending)
                ->where('target_type', $contribution->target_type)
                ->where('target_id', $contribution->target_id)
                ->where('field', $contribution->field)
                ->whereKeyNot($contribution->id)
                ->count(),
        ]);
    }

    public function approve(ReviewContributionRequest $request, Contribution $contribution, ApproveContributionAction $approve): RedirectResponse
    {
        $approve(
            $contribution,
            $request->user(),
            $request->validated('review_note'),
            $request->boolean('force'),
            $request->boolean('keep_old_name_as_alias'),
        );

        return to_route('contributions.show', $contribution);
    }

    public function reject(ReviewContributionRequest $request, Contribution $contribution, CloseContributionAction $close): RedirectResponse
    {
        $close->reject($contribution, $request->user(), $request->validated('review_note'));

        return to_route('contributions.show', $contribution);
    }

    /**
     * @param  array<string, array{label: string, admin_url: string, public_url: string, fields: array<string, string|null>}>  $info
     * @return array<string, mixed>
     */
    private static function row(Contribution $c, array $info): array
    {
        $target = $info[DescribeContributionTargetsAction::key($c)] ?? null;

        return [
            'id' => $c->id,
            'target_type' => $c->target_type->value,
            'target_id' => $c->target_id,
            'field' => $c->field,
            'target_label' => $target['label'] ?? 'Removed record',
            'status' => $c->status->value,
            'note' => $c->note,
            'stats' => $c->stats(),
            // Only a pending contribution can go stale; reviewed ones are history.
            'is_stale' => $c->isPending()
                && $c->isStaleAgainst($target === null ? null : (string) ($target['fields'][$c->field] ?? '')),
            'user' => $c->user?->only(['id', 'name', 'email']),
            'reviewer' => $c->reviewer?->only(['id', 'name']),
            'created_at' => $c->created_at?->toISOString(),
            'reviewed_at' => $c->reviewed_at?->toISOString(),
        ];
    }
}
