<?php

namespace App\Ai\Tools;

use App\Actions\Relationship\CreateRelationshipAction;
use App\DTOs\RelationshipData;
use App\Enums\RelationshipType;
use Illuminate\Contracts\JsonSchema\JsonSchema;

class CreateRelationship extends AgentTool
{
    public function __construct(
        private CreateRelationshipAction $create,
    ) {}

    public static function name(): string
    {
        return 'create_relationship';
    }

    public function description(): string
    {
        return 'Create a typed relationship between two entities. When the target entity does not exist yet, supply new_target to propose creating it first.';
    }

    public function schema(JsonSchema $schema): array
    {
        return [
            'source_entity_id' => $schema->string()->description('UUID of the source entity')->required(),
            'relationship_type' => $schema->string()->description('One of the RelationshipType values, e.g. contains, rules, founded, part_of')->required(),
            'target_entity_id' => $schema->string()->description('UUID of the target entity — omit when using new_target'),
            'new_target' => $schema->object()->description('New entity to create as relationship target when target_entity_id is unknown'),
            'start_year' => $schema->integer()->description('Signed year the relationship began (BCE negative)'),
            'end_year' => $schema->integer()->description('Signed year the relationship ended (BCE negative)'),
        ];
    }

    public function buildParts(array $args): array
    {
        if (empty($args['target_entity_id']) && empty($args['new_target'])) {
            throw new \InvalidArgumentException(
                'CreateRelationship requires either target_entity_id or new_target.'
            );
        }

        $parts = [];
        $targetRef = $args['target_entity_id'] ?? null;

        if (! $targetRef && ! empty($args['new_target'])) {
            // Far side missing — propose creating it first via the existing create_entity tool.
            $parts[] = [
                'key' => 'target',
                'tool' => 'create_entity',
                'payload' => $args['new_target'],
                'human_diff' => [
                    'summary' => "Create new entity \"{$args['new_target']['name']}\" (relationship target)",
                ],
            ];
        }

        $parts[] = [
            'key' => 'relationship',
            'tool' => self::name(),
            'payload' => [
                'source_entity_id' => $args['source_entity_id'],
                'target_entity_id' => $targetRef, // null → resolved from depends
                'relationship_type' => $args['relationship_type'],
                'start_year' => $args['start_year'] ?? null,
                'end_year' => $args['end_year'] ?? null,
            ],
            'human_diff' => [
                'summary' => "Link {$args['relationship_type']} → ".($targetRef ?? $args['new_target']['name'] ?? '?'),
            ],
            'depends_on' => $targetRef ? null : 'target',
        ];

        return $parts;
    }

    public function applyPart(array $payload, array $resolved): array
    {
        $targetId = $payload['target_entity_id'] ?? $resolved['depends']; // substituted new entity id

        $data = new RelationshipData(
            sourceEntityId: $payload['source_entity_id'],
            targetEntityId: $targetId,
            relationshipType: RelationshipType::from($payload['relationship_type']),
            temporalStart: isset($payload['start_year']) ? (string) $payload['start_year'] : null,
            temporalEnd: isset($payload['end_year']) ? (string) $payload['end_year'] : null,
        );

        $rel = ($this->create)($data, createdBy: 'agent:'.$resolved['user_id']);

        return ['result_id' => $rel->relationship_id, 'summary' => 'Relationship created'];
    }
}
