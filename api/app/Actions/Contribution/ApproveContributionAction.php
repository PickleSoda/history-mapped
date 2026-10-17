<?php

declare(strict_types=1);

namespace App\Actions\Contribution;

use App\Actions\Entity\SyncEntityAliasesAction;
use App\Enums\ContributionStatus;
use App\Models\Contribution;
use App\Models\Entity;
use App\Models\EntityAlias;
use App\Models\User;
use App\Support\ContributionFields;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Support\Facades\DB;
use Illuminate\Validation\ValidationException;

/**
 * Apply a pending contribution's proposed text to its target and mark it
 * approved. The target row is locked while comparing; if the field changed
 * since submission the contribution is stale and is only applied with
 * `$force` (overwriting whatever is there now).
 *
 * `$keepOldNameAsAlias` (entity `name` only) files the replaced name under the
 * entity's aliases, for renames where the old name is still a valid search term.
 */
class ApproveContributionAction
{
    /** `entity_aliases.source` of rows written by approved contributions. */
    public const ALIAS_SOURCE = 'contribution';

    public function __construct(private readonly SyncEntityAliasesAction $syncAliases) {}

    public function __invoke(
        Contribution $contribution,
        User $reviewer,
        ?string $note = null,
        bool $force = false,
        bool $keepOldNameAsAlias = false,
    ): Contribution {
        return DB::transaction(function () use ($contribution, $reviewer, $note, $force, $keepOldNameAsAlias): Contribution {
            $contribution = Contribution::query()->lockForUpdate()->findOrFail($contribution->getKey());
            if (! $contribution->isPending()) {
                throw ValidationException::withMessages(['status' => 'This contribution has already been '.$contribution->status->value.'.']);
            }

            $class = $contribution->target_type->modelClass();
            $target = $class::query()->lockForUpdate()->find($contribution->target_id)
                ?? throw ValidationException::withMessages(['conflict' => 'The record this contribution edits no longer exists.']);

            if (! $force && $contribution->isStaleAgainst($contribution->currentText($target))) {
                throw ValidationException::withMessages([
                    'conflict' => 'The text has changed since this was submitted. Review the current version and confirm the overwrite.',
                ]);
            }

            if ($keepOldNameAsAlias && $contribution->field === 'name' && $target instanceof Entity) {
                $this->keepAsAlias($target, (string) $target->name, $contribution->proposed_text);
            }

            $this->apply($target, $contribution->field, $contribution->proposed_text);

            $contribution->update([
                'status' => ContributionStatus::Approved,
                'reviewer_id' => $reviewer->id,
                'review_note' => self::clean($note),
                'reviewed_at' => now(),
            ]);

            return $contribution;
        });
    }

    public static function clean(?string $note): ?string
    {
        return $note === null || trim($note) === '' ? null : trim($note);
    }

    private function apply(Model $target, string $field, string $text): void
    {
        if ($field === 'aliases' && $target instanceof Entity) {
            ($this->syncAliases)($target, ContributionFields::listItems($text), self::ALIAS_SOURCE);

            return;
        }

        // A model save (not a query update) so observers — e.g. the
        // relationship → timeline rebuild — see the change.
        $target->setAttribute($field, $text);
        $target->save();
    }

    private function keepAsAlias(Entity $entity, string $oldName, string $newName): void
    {
        $oldName = trim($oldName);
        $exists = $entity->aliases()
            ->whereRaw('lower(name) = ?', [mb_strtolower($oldName)])
            ->exists();

        if ($oldName !== '' && $oldName !== trim($newName) && ! $exists) {
            EntityAlias::query()->create([
                'entity_id' => $entity->entity_id,
                'name' => $oldName,
                'source' => self::ALIAS_SOURCE,
            ]);
        }
    }
}
