<?php

declare(strict_types=1);

namespace App\Mcp\Tools;

use App\Actions\Entity\ListEntitiesAction;
use App\DTOs\EntityFilterData;
use App\Enums\EntityType;
use App\Http\Api\V1\Controllers\EntityController;
use App\Mcp\Resources\YearMapApp;
use App\Mcp\Support\AtlasUrl;
use App\Mcp\Support\EntityCards;
use App\Mcp\Support\OutputSchemas;
use App\Mcp\Support\Reply;
use App\Mcp\Support\Text;
use App\Support\PgSettings;
use Illuminate\Contracts\JsonSchema\JsonSchema;
use Illuminate\Contracts\Pagination\LengthAwarePaginator;
use Illuminate\Validation\Rule;
use Laravel\Mcp\Request;
use Laravel\Mcp\ResponseFactory;
use Laravel\Mcp\Server\Attributes\Description;
use Laravel\Mcp\Server\Attributes\RendersApp;
use Laravel\Mcp\Server\Tool;
use Laravel\Mcp\Server\Tools\Annotations\IsIdempotent;
use Laravel\Mcp\Server\Tools\Annotations\IsReadOnly;

#[Description('What the atlas has on the map in a given year: entities that existed then and have a point on the map, most historically important first. Narrow it with a bounding box [west, south, east, north] or a region slug such as "western-europe", and with entity types. Years are signed (BC negative, no year 0). Results are capped; the list is the top of a larger set.')]
#[RendersApp(resource: YearMapApp::class)]
#[IsReadOnly]
#[IsIdempotent]
class WhatWasHappening extends Tool
{
    /** Every point on the map lies inside this box; it is how "has a point" is asked of the index. */
    private const WORLD = [-180.0, -90.0, 180.0, 90.0];

    public function schema(JsonSchema $schema): array
    {
        return [
            'year' => $schema->integer()->description('Signed year: 1066 is AD 1066, -44 is 44 BC.')->required(),
            'bbox' => $schema->array()->items($schema->number())->min(4)->max(4)
                ->description('Bounding box [west, south, east, north] in degrees. Not with region.'),
            'region' => $schema->string()->description('Region tag slug, e.g. "western-europe", "east-asia", "egypt". Not with bbox.'),
            'types' => $schema->array()->items($schema->string()->enum(array_column(EntityType::cases(), 'value')))
                ->description('Only these entity types, e.g. ["event_battle", "city"].'),
            'limit' => $schema->integer()->description('Entities to return, 1 to 50 (default 25).')->min(1)->max(50),
        ];
    }

    public function outputSchema(JsonSchema $schema): array
    {
        return [
            'year' => $schema->integer()->required(),
            'bbox' => $schema->array()->items($schema->number())->description('[west, south, east, north] when one was given.')->nullable()->required(),
            'region' => $schema->string()->nullable()->required(),
            'types' => $schema->array()->items($schema->string())->nullable()->required(),
            'entities' => OutputSchemas::entityList($schema)->required(),
            'total' => $schema->integer()->description('Matches, counted only up to a cap.')->required(),
            'total_capped' => $schema->boolean()->required(),
            'atlas_url' => $schema->string()->description('The map at this year.')->required(),
        ];
    }

    public function handle(Request $request, ListEntitiesAction $list): ResponseFactory
    {
        $input = $request->validate([
            'year' => ['required', 'integer', 'between:-100000,9999', 'not_in:0'],
            'bbox' => ['sometimes', 'nullable', 'array', 'size:4', 'prohibits:region'],
            'bbox.*' => ['numeric'],
            'bbox.0' => ['numeric', 'between:-180,180'],
            'bbox.1' => ['numeric', 'between:-90,90'],
            'bbox.2' => ['numeric', 'between:-180,180', 'gte:bbox.0'],
            'bbox.3' => ['numeric', 'between:-90,90', 'gte:bbox.1'],
            'region' => ['sometimes', 'nullable', 'string', Rule::exists('tags', 'slug')->where('facet', 'region')],
            'types' => ['sometimes', 'nullable', 'array', 'max:30'],
            'types.*' => ['string', Rule::enum(EntityType::class)],
            'limit' => ['sometimes', 'nullable', 'integer', 'min:1', 'max:50'],
        ], [
            'region.exists' => 'Unknown region. Use a region tag slug from GET /api/v1/tags, e.g. "western-europe".',
            'bbox.*.gte' => 'bbox must be [west, south, east, north] with west <= east and south <= north.',
            'bbox.prohibits' => 'Give a bbox or a region, not both.',
        ]);

        $year = (int) $input['year'];
        $bbox = isset($input['bbox']) ? array_map('floatval', array_values($input['bbox'])) : null;
        $region = $input['region'] ?? null;
        $types = $input['types'] ?? null;
        $limit = (int) ($input['limit'] ?? 25);

        // Every case filters by the world box when no narrower one is given:
        // that restricts to entities with a primary point, through the GiST index.
        [$west, $south, $east, $north] = $bbox ?? self::WORLD;
        $filters = EntityFilterData::fromArray([
            'exists_at' => $year,
            'bbox_min_lng' => $west,
            'bbox_min_lat' => $south,
            'bbox_max_lng' => $east,
            'bbox_max_lat' => $north,
            'tags' => $region !== null ? [$region] : null,
            'types' => $types,
            'sort' => 'impact',
            'per_page' => $limit,
        ]);
        $run = fn (): LengthAwarePaginator => $list($filters, totalCap: EntityController::LIST_TOTAL_CAP);
        // Plain index scans off when typed. With an entity type in the filter Postgres walks the impact index
        // backwards, testing every entity for the type, year and point (battles in 1800: 500 ms; people, of
        // whom none are placed, 1.3 s plus a 1.1 s count). Without them it starts from the type, year and
        // spatial indexes instead (36 ms and 0.26 s). Left on for the untyped search, where the impact walk
        // finds 25 rows at once.
        $page = $types !== null ? PgSettings::with(['enable_indexscan' => 'off'], $run) : $run();

        $cards = EntityCards::summaries($page->items());
        $capped = (bool) ($page->totalCapped ?? false);
        $names = array_map(
            fn (array $e): string => $e['name'].' ('.$e['type_label'].($e['date_label'] ? ', '.$e['date_label'] : '').')',
            array_slice($cards, 0, 8),
        );
        $where = $region !== null ? ' in '.Text::humanize($region) : ($bbox !== null ? ' in the box' : '');
        $text = $cards === []
            ? 'Nothing with a point on the map in '.Text::year($year).$where.'.'
            : sprintf(
                '%s%d mapped entities existed in %s%s; showing the top %d by impact. %s.',
                $capped ? 'More than ' : '',
                $page->total(),
                Text::year($year),
                $where,
                count($cards),
                implode('; ', $names),
            );

        return Reply::make($text, [
            'year' => $year,
            'bbox' => $bbox,
            'region' => $region,
            'types' => $types,
            'entities' => $cards,
            'total' => $page->total(),
            'total_capped' => $capped,
            'atlas_url' => AtlasUrl::map($year),
        ]);
    }
}
