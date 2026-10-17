<?php

declare(strict_types=1);

namespace App\Actions\Contribution;

use App\Enums\ContributionStatus;
use App\Enums\ContributionTargetType;
use App\Models\Contribution;
use App\Models\User;
use App\Support\ContributionFields;
use Illuminate\Validation\ValidationException;

/**
 * Record a user's proposed correction to one field. The field's current value
 * (possibly empty — a suggestion for a missing field) is snapshotted as the
 * base and the word-level diff is stored with it. List fields (aliases) are
 * normalised on both sides first; see ContributionFields.
 */
class SubmitContributionAction
{
    /** Open proposals one account may have waiting at a time. */
    public const MAX_PENDING_PER_USER = 50;

    public function __invoke(
        User $user,
        ContributionTargetType $type,
        string $targetId,
        string $field,
        string $proposedText,
        ?string $note = null,
    ): Contribution {
        if (! in_array($field, $type->editableFields(), true)) {
            throw ValidationException::withMessages(['field' => 'This field cannot be edited.']);
        }

        $target = $type->find($targetId)
            ?? throw ValidationException::withMessages(['target_id' => 'The record no longer exists.']);

        $base = ContributionFields::read($target, $field);
        $proposed = ContributionFields::normalise($field, $proposedText);

        if (ContributionFields::unchanged($field, $base, $proposed)) {
            throw ValidationException::withMessages(['proposed_text' => 'Nothing has changed.']);
        }
        if ($type->isLineField($field) && $proposed === '') {
            throw ValidationException::withMessages(['proposed_text' => 'This field cannot be empty.']);
        }

        $pending = $user->contributions()->where('status', ContributionStatus::Pending)->count();
        if ($pending >= self::MAX_PENDING_PER_USER) {
            throw ValidationException::withMessages([
                'proposed_text' => 'You have too many suggestions awaiting review. Please wait for some to be reviewed.',
            ]);
        }

        return $user->contributions()->create([
            'target_type' => $type,
            'target_id' => $targetId,
            'field' => $field,
            'base_text' => $base,
            'proposed_text' => $proposed,
            'diff' => ContributionFields::diff($field, $base, $proposed),
            'note' => $note === null || trim($note) === '' ? null : trim($note),
            'status' => ContributionStatus::Pending,
        ]);
    }
}
