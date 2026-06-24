<?php

namespace App\Ai\Tools;

use App\Actions\Entity\BackfillEntityAction;
use App\Actions\Entity\UpdateEntityAction;
use App\DTOs\EntityData;
use App\Enums\EntityType;
use App\Models\Entity;
use Illuminate\Contracts\JsonSchema\JsonSchema;

class UpdateEntityFields extends AgentTool
{
    public function __construct(
        private UpdateEntityAction $update,
        private BackfillEntityAction $backfill,
    ) {}

    public static function name(): string
    {
        return 'update_entity_fields';
    }

    public function description(): string
    {
        return 'Update one or more text/date fields on an existing entity (name, summary, significance, entity_type, start_year, end_year). Only the provided fields are changed; all others are preserved.';
    }

    public function schema(JsonSchema $schema): array
    {
        return [
            'entity_id' => $schema->string()->description('UUID of the entity to update')->required(),
            'name' => $schema->string()->description('New canonical name'),
            'summary' => $schema->string()->description('Short description'),
            'significance' => $schema->string()->description('Historical significance note'),
            'entity_type' => $schema->string()->description('New EntityType value, e.g. political_entity'),
            'start_year' => $schema->integer()->description('Signed year BCE negative'),
            'end_year' => $schema->integer()->description('Signed year BCE negative'),
        ];
    }

    public function buildParts(array $args): array
    {
        $e = Entity::with('primaryTemporalRange')->findOrFail($args['entity_id']);

        $fields = ['name', 'summary', 'significance', 'entity_type', 'start_year', 'end_year'];
        $diff = [];

        foreach ($fields as $field) {
            if (! array_key_exists($field, $args)) {
                continue;
            }

            $old = match ($field) {
                'name' => $e->name,
                'summary' => $e->summary,
                'significance' => $e->significance,
                'entity_type' => $e->entity_type->value,
                'start_year' => $e->primaryTemporalRange?->start_date,
                'end_year' => $e->primaryTemporalRange?->end_date,
            };

            $diff[$field] = ['from' => $old, 'to' => $args[$field]];
        }

        return [[
            'key' => 'fields',
            'tool' => self::name(),
            'payload' => $args,
            'human_diff' => [
                'summary' => "Update fields on {$e->name}: ".implode(', ', array_keys($diff)),
                'diff' => $diff,
            ],
        ]];
    }

    public function applyPart(array $payload, array $resolved): array
    {
        $e = Entity::with('primaryTemporalRange')->findOrFail($payload['entity_id']);

        // Merge provided fields over existing values
        $name = $payload['name'] ?? $e->name;
        $type = isset($payload['entity_type'])
            ? EntityType::from($payload['entity_type'])
            : $e->entity_type;
        $group = $type->group();

        $data = new EntityData(
            name: $name,
            entityType: $type,
            entityGroup: $group,
            summary: $payload['summary'] ?? $e->summary,
            significance: $payload['significance'] ?? $e->significance,
            temporalStart: isset($payload['start_year']) ? (string) $payload['start_year'] : null,
            temporalEnd: isset($payload['end_year']) ? (string) $payload['end_year'] : null,
        );

        $e = ($this->update)($e, $data);

        $datesChanged = array_key_exists('start_year', $payload) || array_key_exists('end_year', $payload);
        if ($datesChanged) {
            ($this->backfill)($e);
        }

        return ['result_id' => $e->entity_id, 'summary' => 'Fields updated'];
    }
}
