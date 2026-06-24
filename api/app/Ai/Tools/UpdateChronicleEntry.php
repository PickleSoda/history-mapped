<?php

namespace App\Ai\Tools;

use App\Actions\Chronicle\UpdateChronicleEntryAction;
use App\DTOs\ChronicleEntryData;
use App\Models\ChronicleEntry;
use Illuminate\Contracts\JsonSchema\JsonSchema;

class UpdateChronicleEntry extends AgentTool
{
    public function __construct(private UpdateChronicleEntryAction $update) {}

    public static function name(): string
    {
        return 'update_chronicle_entry';
    }

    public function description(): string
    {
        return 'Edit an existing chronicle entry: narrative, notes, or which entities it links.';
    }

    public function schema(JsonSchema $schema): array
    {
        return [
            'entry_id' => $schema->string()->description('The chronicle entry to edit')->required(),
            'narrative_text' => $schema->string(),
            'notes' => $schema->string(),
            'entity_ids' => $schema->array()->description('Replaces the linked entities when provided'),
        ];
    }

    public function buildParts(array $args): array
    {
        return [[
            'key' => 'entry',
            'tool' => self::name(),
            'payload' => $args,
            'human_diff' => ['summary' => 'Edit chronicle entry '.$args['entry_id'], 'fields' => $args],
        ]];
    }

    public function applyPart(array $payload, array $resolved): array
    {
        $entry = ChronicleEntry::findOrFail($payload['entry_id']);
        ($this->update)($entry, new ChronicleEntryData(
            narrativeText: $payload['narrative_text'] ?? null,
            notes: $payload['notes'] ?? null,
            entityIds: $payload['entity_ids'] ?? null,
        ));

        return ['result_id' => $entry->entry_id, 'summary' => 'Entry updated'];
    }
}
