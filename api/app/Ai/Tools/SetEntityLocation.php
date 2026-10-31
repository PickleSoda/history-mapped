<?php

namespace App\Ai\Tools;

use App\Actions\Entity\ApplyEntityEditsAction;
use App\Actions\Entity\BackfillEntityAction;
use App\Enums\ConfidenceLevel;
use App\Enums\LocationResolutionMethod;
use App\Models\Entity;
use Illuminate\Contracts\JsonSchema\JsonSchema;

class SetEntityLocation extends AgentTool
{
    public function __construct(
        private ApplyEntityEditsAction $apply,
        private BackfillEntityAction $backfill,
    ) {}

    public static function name(): string
    {
        return 'set_entity_location';
    }

    public function description(): string
    {
        return 'Set or move the primary map point of an entity (lon/lat in WGS-84 degrees). Use coordinates from the user, from verify_wikidata, '
            .'or from the place tools (find_place, point_from_offset, point_between, nearest_coast). Name the spot in location_name. '
            .'The territory polygon and other location fields are kept.';
    }

    public function schema(JsonSchema $schema): array
    {
        return [
            'entity_id' => $schema->string()->description('UUID of the entity to update')->required(),
            'lon' => $schema->number()->description('Longitude, -180 to 180 (east is positive; Rome is 12.5)')->required(),
            'lat' => $schema->number()->description('Latitude, -90 to 90 (north is positive; Rome is 41.9)')->required(),
            'location_name' => $schema->string()->description('What the point marks, e.g. "Shore near Ostia" or "Between Nicaea and Nicomedia"'),
            'location_confidence' => $schema->string()->enum([ConfidenceLevel::High->value, ConfidenceLevel::Medium->value, ConfidenceLevel::Low->value])
                ->description('high = the source names the exact site; medium = derived from a stated relation to known places; low = a rough guess'),
        ];
    }

    public function buildParts(array $args): array
    {
        if (! is_numeric($args['lon'] ?? null) || ! is_numeric($args['lat'] ?? null)
            || abs((float) $args['lon']) > 180 || abs((float) $args['lat']) > 90) {
            throw new ToolArgumentException('lon must be within -180..180 and lat within -90..90 (degrees).');
        }

        $e = Entity::with('primaryLocation')->findOrFail($args['entity_id']);
        $from = $e->primaryLocation?->geom; // [lon,lat] or null

        return [[
            'key' => 'location',
            'tool' => self::name(),
            'payload' => $args,
            'human_diff' => [
                'summary' => "Move {$e->name} → ({$args['lon']}, {$args['lat']})"
                    .(isset($args['location_name']) ? " — {$args['location_name']}" : ''),
                'from' => $from,
                'to' => [$args['lon'], $args['lat']],
            ],
        ]];
    }

    public function applyPart(array $payload, array $resolved): array
    {
        $e = Entity::findOrFail($payload['entity_id']);

        // Through the form's write path, so the territory polygon, location
        // name and confidence survive a moved point.
        $e = ($this->apply)($e, array_filter([
            'geojson' => ['type' => 'Point', 'coordinates' => [(float) $payload['lon'], (float) $payload['lat']]],
            'location_method' => LocationResolutionMethod::HumanAssigned->value,
            'location_name' => $payload['location_name'] ?? null,
            'location_confidence' => $payload['location_confidence'] ?? null,
        ], fn ($value) => $value !== null));
        ($this->backfill)($e);

        return ['result_id' => $e->entity_id, 'summary' => 'Location updated'];
    }
}
