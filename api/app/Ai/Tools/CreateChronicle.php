<?php

namespace App\Ai\Tools;

use App\Actions\Chronicle\CreateChronicleAction;
use App\DTOs\ChronicleData;
use App\Enums\ChronicleStatus;
use App\Enums\SourceType;
use App\Models\Chronicle;
use Illuminate\Contracts\JsonSchema\JsonSchema;

class CreateChronicle extends AgentTool
{
    public function __construct(private CreateChronicleAction $create) {}

    public static function name(): string
    {
        return 'create_chronicle';
    }

    public function description(): string
    {
        return 'Create a new chronicle (a narrative timeline). Sets title, summary, status and an optional year range. Entries are added afterward on the chronicle edit page — do NOT attempt to add entries here.';
    }

    public function schema(JsonSchema $schema): array
    {
        return [
            'title' => $schema->string()->description('Chronicle title')->required(),
            'summary' => $schema->string()->description('Short description / narrative summary'),
            'start_year' => $schema->integer()->description('Signed year, BCE negative'),
            'end_year' => $schema->integer(),
            'source_reference' => $schema->string()->description('Optional source citation'),
        ];
    }

    public function buildParts(array $args): array
    {
        return [[
            'key' => 'chronicle',
            'tool' => self::name(),
            'payload' => $args,
            'human_diff' => [
                'summary' => "Create chronicle \"{$args['title']}\"".(isset($args['start_year']) ? " ({$args['start_year']}–".($args['end_year'] ?? '…').')' : ''),
                'fields' => $args,
            ],
        ]];
    }

    public function applyPart(array $payload, array $resolved): array
    {
        $data = new ChronicleData(
            title: $payload['title'],
            sourceType: SourceType::Manual,
            sourceReference: $payload['source_reference'] ?? null,
            status: ChronicleStatus::Draft,
            startYear: $payload['start_year'] ?? null,
            endYear: $payload['end_year'] ?? null,
            metadata: isset($payload['summary']) ? ['summary' => $payload['summary']] : null,
        );

        /** @var Chronicle $chronicle */
        $chronicle = ($this->create)($data, createdBy: 'agent:'.$resolved['user_id']);

        return ['result_id' => $chronicle->chronicle_id, 'summary' => "Created chronicle {$chronicle->title}"];
    }
}
