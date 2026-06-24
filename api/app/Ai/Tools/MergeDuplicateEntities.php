<?php

declare(strict_types=1);

namespace App\Ai\Tools;

use App\Actions\Entity\MergeEntitiesAction;
use App\Models\Entity;
use Illuminate\Contracts\JsonSchema\JsonSchema;

class MergeDuplicateEntities extends AgentTool
{
    public function __construct(
        private MergeEntitiesAction $merge,
    ) {}

    public static function name(): string
    {
        return 'merge_duplicate_entities';
    }

    public function description(): string
    {
        return 'Merge a duplicate (loser) entity into a surviving entity. Re-points all relationships, chronicle links, and timeline references from the loser to the survivor, then deletes the loser. Use when two entity rows denote the same real-world subject.';
    }

    public function schema(JsonSchema $schema): array
    {
        return [
            'survivor_id' => $schema->string()->description('UUID of the entity to keep')->required(),
            'loser_id' => $schema->string()->description('UUID of the duplicate entity to delete')->required(),
        ];
    }

    public function buildParts(array $args): array
    {
        $survivor = Entity::findOrFail($args['survivor_id']);
        $loser = Entity::findOrFail($args['loser_id']);

        return [[
            'key' => 'merge',
            'tool' => self::name(),
            'payload' => [
                'survivor_id' => $args['survivor_id'],
                'loser_id' => $args['loser_id'],
            ],
            'human_diff' => [
                'summary' => "Merge \"{$loser->name}\" into \"{$survivor->name}\"",
                'survivor_id' => $survivor->entity_id,
                'survivor_name' => $survivor->name,
                'loser_id' => $loser->entity_id,
                'loser_name' => $loser->name,
            ],
        ]];
    }

    public function applyPart(array $payload, array $resolved): array
    {
        $survivor = ($this->merge)($payload['survivor_id'], $payload['loser_id']);

        return [
            'result_id' => $survivor->entity_id,
            'summary' => "Merged entity into survivor {$survivor->entity_id}",
        ];
    }
}
