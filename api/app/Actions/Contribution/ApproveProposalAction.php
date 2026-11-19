<?php

declare(strict_types=1);

namespace App\Actions\Contribution;

use App\Actions\Entity\CreateEntityAction;
use App\Actions\Relationship\CreateRelationshipAction;
use App\DTOs\EntityData;
use App\DTOs\RelationshipData;
use App\Enums\ContributionKind;
use App\Enums\ContributionStatus;
use App\Enums\ContributionTargetType;
use App\Enums\VerificationStatus;
use App\Models\Contribution;
use App\Models\Entity;
use App\Models\EntityRelationship;
use App\Models\User;
use Illuminate\Support\Facades\DB;
use Illuminate\Validation\ValidationException;

/**
 * Approve a `create` contribution: build the entity or relationship it holds
 * (CreateEntityAction / CreateRelationshipAction, `created_by` = the
 * contributor), mark it `human_verified` (a moderator has read it), store the
 * new record's id on the contribution and close it as approved.
 *
 * A relationship end that points at a still-pending entity proposal blocks
 * approval ("approve the entity first"); once that proposal is approved the
 * end resolves to the entity it created. The whole thing runs in one
 * transaction, so a failure leaves the proposal pending.
 */
class ApproveProposalAction
{
    public function __construct(
        private readonly CreateEntityAction $createEntity,
        private readonly CreateRelationshipAction $createRelationship,
    ) {}

    public function __invoke(Contribution $contribution, User $reviewer, ?string $note = null): Contribution
    {
        return DB::transaction(function () use ($contribution, $reviewer, $note): Contribution {
            $contribution = Contribution::query()->lockForUpdate()->findOrFail($contribution->getKey());
            if (! $contribution->isCreate()) {
                throw ValidationException::withMessages(['status' => 'This is not a proposal for a new record.']);
            }
            if (! $contribution->isPending()) {
                throw ValidationException::withMessages(['status' => 'This contribution has already been '.$contribution->status->value.'.']);
            }

            $createdBy = (string) $contribution->user_id;
            $targetId = $contribution->target_type === ContributionTargetType::Relationship
                ? $this->createRelationship($contribution, $createdBy)
                : $this->createEntity($contribution, $createdBy);

            $contribution->update([
                'target_id' => $targetId,
                'status' => ContributionStatus::Approved,
                'reviewer_id' => $reviewer->id,
                'review_note' => ApproveContributionAction::clean($note),
                'reviewed_at' => now(),
            ]);

            return $contribution;
        });
    }

    private function createEntity(Contribution $contribution, string $createdBy): string
    {
        $data = $contribution->payload['entity'] ?? throw ValidationException::withMessages(['payload' => 'The proposal has no entity data.']);

        if (isset($data['wikidata_id']) && Entity::query()->where('wikidata_id', $data['wikidata_id'])->exists()) {
            throw ValidationException::withMessages(['payload' => "The atlas now has {$data['wikidata_id']}. Reject this proposal or edit that entity instead."]);
        }

        $entity = ($this->createEntity)(
            EntityData::fromArray([...$data, 'verification_status' => VerificationStatus::HumanVerified->value]),
            $createdBy,
        );

        return $entity->entity_id;
    }

    private function createRelationship(Contribution $contribution, string $createdBy): string
    {
        $data = $contribution->payload['relationship'] ?? throw ValidationException::withMessages(['payload' => 'The proposal has no relationship data.']);

        $sourceId = $this->resolveEnd($data['source'], 'source');
        $targetId = $this->resolveEnd($data['target'], 'target');
        if ($sourceId === $targetId) {
            throw ValidationException::withMessages(['payload' => 'Both ends are the same entity.']);
        }
        if (EntityRelationship::query()
            ->where('source_entity_id', $sourceId)->where('target_entity_id', $targetId)
            ->where('relationship_type', $data['relationship_type'])->exists()) {
            throw ValidationException::withMessages(['payload' => 'The atlas already has this relationship.']);
        }

        $relationship = ($this->createRelationship)(
            RelationshipData::fromArray([
                ...$data,
                'source_entity_id' => $sourceId,
                'target_entity_id' => $targetId,
            ]),
            $createdBy,
        );

        return $relationship->relationship_id;
    }

    /**
     * @param  array{entity_id?: string, contribution_id?: int, label?: string}  $end
     */
    private function resolveEnd(array $end, string $field): string
    {
        $label = $end['label'] ?? 'the entity';

        if (isset($end['contribution_id'])) {
            $dependency = Contribution::query()->find($end['contribution_id']);
            if ($dependency?->kind !== ContributionKind::Create || $dependency->status !== ContributionStatus::Approved) {
                $state = $dependency?->status->value ?? 'missing';

                throw ValidationException::withMessages([
                    'dependency' => $dependency?->isPending()
                        ? "Approve the proposal for “{$label}” (#{$end['contribution_id']}) first: this relationship points at it."
                        : "The proposal for “{$label}” (#{$end['contribution_id']}) is {$state}, so this relationship cannot be approved.",
                ]);
            }
            $end = ['entity_id' => (string) $dependency->target_id, 'label' => $label];
        }

        $id = $end['entity_id'] ?? null;
        if ($id === null || ! Entity::query()->whereKey($id)->exists()) {
            throw ValidationException::withMessages(['dependency' => "The {$field} entity “{$label}” no longer exists."]);
        }

        return $id;
    }
}
