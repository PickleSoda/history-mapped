<?php

namespace App\Ai\Tools;

use App\Actions\Entity\BackfillEntityAction;
use App\Actions\Entity\CreateEntityAction;
use App\DTOs\EntityData;
use App\Enums\EntityType;
use App\Enums\LocationResolutionMethod;
use App\Models\Entity;
use App\Services\WikidataService;
use Illuminate\Contracts\JsonSchema\JsonSchema;

class CreateEntity extends AgentTool
{
    public function __construct(
        private CreateEntityAction $create,
        private BackfillEntityAction $backfill,
        private WikidataService $wikidata,
    ) {}

    public static function name(): string
    {
        return 'create_entity';
    }

    public function description(): string
    {
        return 'Create a new historical entity (the primary tool). Verify any wikidata_id first; pass a representative lon/lat when known.';
    }

    public function schema(JsonSchema $schema): array
    {
        return [
            'name' => $schema->string()->description('Entity name')->required(),
            'entity_type' => $schema->string()->description('One of the 30 EntityType values, e.g. political_entity, infrastructure_monument, event_battle')->required(),
            'wikidata_id' => $schema->string()->description('QID, verified against Wikidata; omit if none'),
            'summary' => $schema->string()->description('Short description'),
            'lon' => $schema->number()->description('Longitude of a representative location'),
            'lat' => $schema->number()->description('Latitude'),
            'start_year' => $schema->integer()->description('Signed year, BCE negative'),
            'end_year' => $schema->integer(),
        ];
    }

    public function buildParts(array $args): array
    {
        $note = '';
        if (! empty($args['wikidata_id'])) {
            $meta = $this->wikidata->fetch($args['wikidata_id']);
            $note = $meta
                ? " — verified Wikidata: {$meta['label']}"
                : ' — WARNING: Wikidata QID not found';
        }

        return [[
            'key' => 'entity',
            'tool' => self::name(),
            'payload' => $args,
            'human_diff' => [
                'summary' => "Create entity \"{$args['name']}\" ({$args['entity_type']})".$note,
                'fields' => $args,
            ],
        ]];
    }

    public function applyPart(array $payload, array $resolved): array
    {
        $type = EntityType::from($payload['entity_type']);
        $hasCoord = isset($payload['lon'], $payload['lat']);

        $data = new EntityData(
            name: $payload['name'],
            entityType: $type,
            entityGroup: $type->group(),
            summary: $payload['summary'] ?? null,
            wikidataId: $payload['wikidata_id'] ?? null,
            temporalStart: isset($payload['start_year']) ? (string) $payload['start_year'] : null,
            temporalEnd: isset($payload['end_year']) ? (string) $payload['end_year'] : null,
            locationMethod: $hasCoord
                ? (! empty($payload['wikidata_id']) ? LocationResolutionMethod::Wikidata : LocationResolutionMethod::HumanAssigned)
                : null,
            geojson: $hasCoord ? ['type' => 'Point', 'coordinates' => [$payload['lon'], $payload['lat']]] : null,
        );

        /** @var Entity $entity */
        $entity = ($this->create)($data, createdBy: 'agent:'.$resolved['user_id']);
        ($this->backfill)($entity);

        return ['result_id' => $entity->entity_id, 'summary' => "Created {$entity->name}"];
    }
}
