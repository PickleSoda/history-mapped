<?php

declare(strict_types=1);

namespace App\Actions\Contribution;

use App\Enums\ContributionKind;
use App\Enums\ContributionSource;
use App\Enums\ContributionStatus;
use App\Enums\ContributionTargetType;
use App\Enums\RelationshipType;
use App\Models\Contribution;
use App\Models\Entity;
use App\Models\EntityRelationship;
use App\Models\User;
use Illuminate\Support\Facades\Validator;
use Illuminate\Support\Str;
use Illuminate\Validation\Rule;
use Illuminate\Validation\ValidationException;

/**
 * Record a proposal for a new relationship. Nothing is created: the validated
 * payload is held as a `create` contribution until a moderator approves it
 * (ApproveProposalAction -> CreateRelationshipAction).
 *
 * Each end is an existing entity id, or the id of the caller's own contribution
 * that proposes a new entity. A pending entity proposal stays a reference
 * (`contribution_id`) and is resolved to the created entity on approval; one
 * that is already approved is resolved to that entity now. The type is read
 * from the source's side ("source rules target"), as RelationshipData expects.
 */
class ProposeRelationshipAction
{
    /**
     * @param  array<string, mixed>  $input  source, target (each an entity uuid or "proposal:{id}"),
     *                                       relationship_type, temporal_start, temporal_end, description, source_citations
     *
     * @throws ValidationException
     */
    public function __invoke(
        User $user,
        array $input,
        ?string $note = null,
        ContributionSource $source = ContributionSource::Atlas,
        ?string $client = null,
    ): Contribution {
        $year = ['nullable', 'string', 'max:50', 'regex:/^-?\d{1,5}(-\d{2}(-\d{2})?)?$/'];
        $data = Validator::make($input, [
            'source' => ['required', 'string', 'max:64'],
            'target' => ['required', 'string', 'max:64'],
            'relationship_type' => ['required', 'string', Rule::enum(RelationshipType::class)],
            'temporal_start' => $year,
            'temporal_end' => $year,
            'description' => ['nullable', 'string', 'max:2000'],
            'source_citations' => ['nullable', 'array', 'max:10'],
            'source_citations.*.title' => ['nullable', 'string', 'max:300'],
            'source_citations.*.url' => ['nullable', 'url:http,https', 'max:1000'],
        ])->after(function ($v) use ($input): void {
            $start = ProposeEntityAction::leadingYear($input['temporal_start'] ?? null);
            $end = ProposeEntityAction::leadingYear($input['temporal_end'] ?? null);
            if ($start !== null && $end !== null && $end < $start) {
                $v->errors()->add('temporal_end', 'The end cannot be before the start.');
            }
            foreach ((array) ($input['source_citations'] ?? []) as $i => $c) {
                if (is_array($c) && blank($c['title'] ?? null) && blank($c['url'] ?? null)) {
                    $v->errors()->add("source_citations.$i", 'A source needs a title or a url.');
                }
            }
        })->validate();

        $from = $this->resolveEnd($user, $data['source'], 'source');
        $to = $this->resolveEnd($user, $data['target'], 'target');

        if (isset($from['entity_id'], $to['entity_id']) && $from['entity_id'] === $to['entity_id']) {
            throw ValidationException::withMessages(['target' => 'A relationship needs two different entities.']);
        }
        if (isset($from['contribution_id'], $to['contribution_id']) && $from['contribution_id'] === $to['contribution_id']) {
            throw ValidationException::withMessages(['target' => 'A relationship needs two different entities.']);
        }
        if (isset($from['entity_id'], $to['entity_id'])) {
            $existing = EntityRelationship::query()
                ->where('source_entity_id', $from['entity_id'])
                ->where('target_entity_id', $to['entity_id'])
                ->where('relationship_type', $data['relationship_type'])
                ->value('relationship_id');
            if ($existing !== null) {
                throw ValidationException::withMessages(['relationship_type' => "The atlas already has this relationship ({$existing})."]);
            }
        }

        $pending = $user->contributions()->where('status', ContributionStatus::Pending)->count();
        if ($pending >= SubmitContributionAction::MAX_PENDING_PER_USER) {
            throw ValidationException::withMessages([
                'source' => 'You have too many proposals awaiting review. Please wait for some to be reviewed.',
            ]);
        }

        $relationship = ['source' => $from, 'target' => $to, 'relationship_type' => $data['relationship_type']];
        foreach (['temporal_start', 'temporal_end', 'description'] as $key) {
            if (! blank($data[$key] ?? null)) {
                $relationship[$key] = trim($data[$key]);
            }
        }
        $citations = [];
        foreach ((array) ($data['source_citations'] ?? []) as $c) {
            $citations[] = array_filter([
                'source_type' => 'reference',
                'title' => isset($c['title']) ? trim((string) $c['title']) : null,
                'url' => $c['url'] ?? null,
            ], fn ($v) => $v !== null && $v !== '');
        }
        if ($citations !== []) {
            $relationship['source_citations'] = $citations;
        }

        return $user->contributions()->create([
            'kind' => ContributionKind::Create,
            'target_type' => ContributionTargetType::Relationship,
            'payload' => ['relationship' => $relationship],
            'note' => $note === null || trim($note) === '' ? null : trim($note),
            'status' => ContributionStatus::Pending,
            'source' => $source,
            'client' => $client,
        ]);
    }

    /**
     * One end: an entity uuid, or "proposal:{id}" / a bare integer id of the
     * caller's own entity proposal.
     *
     * @return array{entity_id?: string, contribution_id?: int, label: string}
     */
    private function resolveEnd(User $user, string $ref, string $field): array
    {
        $ref = trim($ref);

        if (Str::isUuid($ref)) {
            $entity = Entity::query()->find($ref, ['entity_id', 'name']);
            if ($entity === null) {
                throw ValidationException::withMessages([$field => 'No entity has this id.']);
            }

            return ['entity_id' => $entity->entity_id, 'label' => $entity->name];
        }

        if (preg_match('/^(?:proposal:)?(\d+)$/', $ref, $m) !== 1) {
            throw ValidationException::withMessages([$field => 'Use an entity id (uuid) or the id of your own pending entity proposal.']);
        }

        $proposal = $user->contributions()
            ->where('kind', ContributionKind::Create)
            ->where('target_type', ContributionTargetType::Entity)
            ->whereKey((int) $m[1])
            ->first();
        $name = $proposal?->payload['entity']['name'] ?? null;
        if ($proposal === null) {
            throw ValidationException::withMessages([$field => 'No entity proposal of yours has this id.']);
        }

        return match ($proposal->status) {
            ContributionStatus::Pending => ['contribution_id' => $proposal->id, 'label' => (string) $name],
            ContributionStatus::Approved => ['entity_id' => (string) $proposal->target_id, 'label' => (string) $name],
            default => throw ValidationException::withMessages([$field => 'That entity proposal was '.$proposal->status->value.'.']),
        };
    }
}
