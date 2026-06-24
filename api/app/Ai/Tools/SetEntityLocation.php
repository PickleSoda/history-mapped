<?php

namespace App\Ai\Tools;

use App\Actions\Entity\BackfillEntityAction;
use App\Actions\Entity\UpdateEntityAction;
use App\DTOs\EntityData;
use App\Enums\LocationResolutionMethod;
use App\Models\Entity;
use Illuminate\Contracts\JsonSchema\JsonSchema;

class SetEntityLocation extends AgentTool
{
    public function __construct(
        private UpdateEntityAction $update,
        private BackfillEntityAction $backfill,
    ) {}

    public static function name(): string
    {
        return 'set_entity_location';
    }

    public function description(): string
    {
        return 'Set or move the primary geographic point for an entity (lon/lat). Use when Wikidata or user provides corrected coordinates.';
    }

    public function schema(JsonSchema $schema): array
    {
        return [
            'entity_id' => $schema->string()->description('UUID of the entity to update')->required(),
            'lon' => $schema->number()->description('Longitude (WGS-84)')->required(),
            'lat' => $schema->number()->description('Latitude (WGS-84)')->required(),
        ];
    }

    public function buildParts(array $args): array
    {
        $e = Entity::with('primaryLocation')->findOrFail($args['entity_id']);
        $from = $e->primaryLocation?->geom; // [lon,lat] or null

        return [[
            'key' => 'location',
            'tool' => self::name(),
            'payload' => $args,
            'human_diff' => [
                'summary' => "Move {$e->name} → ({$args['lon']}, {$args['lat']})",
                'from' => $from,
                'to' => [$args['lon'], $args['lat']],
            ],
        ]];
    }

    public function applyPart(array $payload, array $resolved): array
    {
        $e = Entity::findOrFail($payload['entity_id']);

        $data = new EntityData(
            name: $e->name,
            entityType: $e->entity_type,
            entityGroup: $e->entity_group,
            locationMethod: LocationResolutionMethod::HumanAssigned,
            geojson: ['type' => 'Point', 'coordinates' => [$payload['lon'], $payload['lat']]],
        );

        $e = ($this->update)($e, $data);
        ($this->backfill)($e);

        return ['result_id' => $e->entity_id, 'summary' => 'Location updated'];
    }
}
