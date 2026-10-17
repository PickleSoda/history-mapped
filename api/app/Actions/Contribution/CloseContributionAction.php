<?php

declare(strict_types=1);

namespace App\Actions\Contribution;

use App\Enums\ContributionStatus;
use App\Models\Contribution;
use App\Models\User;
use Illuminate\Support\Facades\DB;
use Illuminate\Validation\ValidationException;

/**
 * Close a pending contribution without applying it: rejected by a reviewer
 * (with an optional note to the contributor) or withdrawn by its author.
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

            return $contribution;
        });
    }
}
