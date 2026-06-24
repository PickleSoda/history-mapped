<?php

namespace App\Ai\Tools;

use App\Actions\Chronicle\CreateChronicleEntryAction;
use App\DTOs\ChronicleEntryData;
use Illuminate\Contracts\JsonSchema\JsonSchema;
use Illuminate\Support\Str;

class CreateChronicleEntry extends AgentTool
{
    public function __construct(private CreateChronicleEntryAction $create) {}

    public static function name(): string
    {
        return 'create_chronicle_entry';
    }

    public function description(): string
    {
        return 'Add a narrative entry to a chronicle, optionally linking the entities it concerns.';
    }

    public function schema(JsonSchema $schema): array
    {
        return [
            'chronicle_id' => $schema->string()->description('Chronicle to add the entry to')->required(),
            'narrative_text' => $schema->string()->description('The entry narrative')->required(),
            'entity_ids' => $schema->array()->description('Entity ids this entry concerns'),
            'notes' => $schema->string(),
        ];
    }

    public function buildParts(array $args): array
    {
        return [[
            'key' => 'entry',
            'tool' => self::name(),
            'payload' => $args,
            'human_diff' => ['summary' => 'Add chronicle entry: '.Str::limit($args['narrative_text'], 60)],
        ]];
    }

    public function applyPart(array $payload, array $resolved): array
    {
        $entry = ($this->create)(
            $payload['chronicle_id'],
            new ChronicleEntryData(
                narrativeText: $payload['narrative_text'],
                notes: $payload['notes'] ?? null,
                entityIds: $payload['entity_ids'] ?? null,
            ),
            createdBy: 'agent:'.$resolved['user_id'],
        );

        return ['result_id' => $entry->entry_id, 'summary' => 'Entry added'];
    }
}
