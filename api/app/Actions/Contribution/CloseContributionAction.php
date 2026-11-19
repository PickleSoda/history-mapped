<?php

declare(strict_types=1);

namespace App\Actions\Contribution;

use App\Enums\ContributionKind;
use App\Enums\ContributionStatus;
use App\Enums\ContributionTargetType;
use App\Models\Contribution;
use App\Models\User;
use Illuminate\Support\Facades\DB;
use Illuminate\Validation\ValidationException;

/**
 * Close a pending contribution without applying it: rejected by a reviewer
 * (with an optional note to the contributor) or withdrawn by its author.
 *
 * Closing a proposal for a new entity also closes the contributor's pending
 * relationship proposals that point at it (they could never be approved), with
 * the same status and a note saying why; they are never left dangling.
 */
class CloseContributionAction
{
    public function reject(Contribution $contribution, User $reviewer, ?string $note = null): Contribution
    {
        return $this->close($contribution, [
            'status' => ContributionStatus::Rejected,
            'reviewer_id' => $reviewer->id,
            'review_note' => ApproveContributionAction::clean($note),
            'reviewed_at' => now(),
        ]);
    }

    public function withdraw(Contribution $contribution): Contribution
    {
        return $this->close($contribution, ['status' => ContributionStatus::Withdrawn]);
    }

    /** @param  array<string, mixed>  $attributes */
    private function close(Contribution $contribution, array $attributes): Contribution
    {
        return DB::transaction(function () use ($contribution, $attributes): Contribution {
            $contribution = Contribution::query()->lockForUpdate()->findOrFail($contribution->getKey());
            if (! $contribution->isPending()) {
                throw ValidationException::withMessages(['status' => 'This contribution has already been '.$contribution->status->value.'.']);
            }
            $contribution->update($attributes);

            if ($contribution->isCreate() && $contribution->target_type === ContributionTargetType::Entity) {
                $this->closeDependents($contribution, $attributes);
            }

            return $contribution;
        });
    }

    /**
     * Pending relationship proposals whose source or target is `$entityProposal`.
     *
     * @param  array<string, mixed>  $attributes
     */
    private function closeDependents(Contribution $entityProposal, array $attributes): void
    {
        $why = 'Closed automatically: the entity proposal this relationship points at (#'.$entityProposal->id.') was '
            .$entityProposal->status->value.'.';

        Contribution::query()
            ->where('kind', ContributionKind::Create)
            ->where('target_type', ContributionTargetType::Relationship)
            ->where('status', ContributionStatus::Pending)
            ->where('user_id', $entityProposal->user_id)
            ->where(fn ($q) => $q
                ->whereRaw("(payload->'relationship'->'source'->>'contribution_id')::bigint = ?", [$entityProposal->id])
                ->orWhereRaw("(payload->'relationship'->'target'->>'contribution_id')::bigint = ?", [$entityProposal->id]))
            ->lockForUpdate()
            ->get()
            ->each(fn (Contribution $dependent) => $dependent->update([
                ...$attributes,
                'review_note' => $why,
            ]));
    }
}
