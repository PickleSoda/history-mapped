<?php

declare(strict_types=1);

namespace App\Mcp\Tools;

use App\Actions\Chronicle\ListChroniclesAction;
use App\Actions\Entity\ListEntitiesAction;
use App\DTOs\EntityFilterData;
use App\Enums\EntityType;
use App\Http\Api\V1\Controllers\EntityController;
use App\Mcp\Support\AtlasUrl;
use App\Mcp\Support\EntityCards;
use App\Mcp\Support\OutputSchemas;
use App\Mcp\Support\Reply;
use App\Mcp\Support\Text;
use App\Models\Chronicle;
use Illuminate\Contracts\JsonSchema\JsonSchema;
use Illuminate\Validation\Rule;
use Laravel\Mcp\Request;
use Laravel\Mcp\ResponseFactory;
use Laravel\Mcp\Server\Attributes\Description;
use Laravel\Mcp\Server\Tool;
use Laravel\Mcp\Server\Tools\Annotations\IsIdempotent;
use Laravel\Mcp\Server\Tools\Annotations\IsReadOnly;

#[Description('Search the atlas by name: entities (people, places, battles, polities, works and more) ranked by name similarity, plus matching chronicles (curated narratives). Use it first to find an entity id, then call get_entity, get_connections or what_was_happening. Optionally restrict to entity types or to entities that existed in a given year (negative = BC).')]
#[IsReadOnly]
#[IsIdempotent]
class SearchAtlas extends Tool
{
    private const CHRONICLES = 5;

    public function schema(JsonSchema $schema): array
    {
        return [
            'query' => $schema->string()->description('Name or words to search for, 2 to 200 characters.')->min(2)->max(200)->required(),
            'types' => $schema->array()->items($schema->string()->enum(array_column(EntityType::cases(), 'value')))
                ->description('Only these entity types, e.g. ["person", "event_battle"].'),
            'year' => $schema->integer()->description('Only entities that existed in this signed year (BC negative, no year 0).'),
            'limit' => $schema->integer()->description('Entities to return, 1 to 20 (default 10).')->min(1)->max(20),
        ];
    }

    public function outputSchema(JsonSchema $schema): array
    {
        return [
            'query' => $schema->string()->required(),
            'entities' => OutputSchemas::entityList($schema)->required(),
            'total_entities' => $schema->integer()->description('Matches, counted only up to total_capped.')->required(),
            'total_capped' => $schema->boolean()->description('True when there are more matches than total_entities says.')->required(),
            'chronicles' => $schema->array()->items($schema->object(OutputSchemas::chronicleBriefFields($schema)))->required(),
        ];
    }

    public function handle(
        Request $request,
        ListEntitiesAction $entities,
        ListChroniclesAction $chronicles,
    ): ResponseFactory {
        $input = $request->validate([
            'query' => ['required', 'string', 'min:2', 'max:200'],
            'types' => ['sometimes', 'nullable', 'array', 'max:30'],
            'types.*' => ['string', Rule::enum(EntityType::class)],
            'year' => ['sometimes', 'nullable', 'integer', 'between:-100000,9999', 'not_in:0'],
            'limit' => ['sometimes', 'nullable', 'integer', 'min:1', 'max:20'],
        ]);
        $limit = (int) ($input['limit'] ?? 10);

        $page = $entities(EntityFilterData::fromArray([
            'search' => $input['query'],
            'types' => $input['types'] ?? null,
            'exists_at' => $input['year'] ?? null,
            'per_page' => $limit,
        ]), totalCap: EntityController::LIST_TOTAL_CAP);

        $cards = EntityCards::summaries($page->items());
        $capped = (bool) ($page->totalCapped ?? false);

        $matches = $chronicles(['search' => $input['query'], 'sort' => 'impact', 'per_page' => self::CHRONICLES])->items();
        $chronicleRows = array_map(fn (Chronicle $c): array => [
            'slug' => $c->slug,
            'title' => $c->title,
            'start_year' => $c->start_year,
            'end_year' => $c->end_year,
            'summary' => Text::limit($c->description, EntityCards::SUMMARY_CHARS),
            'atlas_url' => AtlasUrl::chronicle($c->slug),
        ], $matches);

        $top = array_map(
            fn (array $e): string => $e['name'].' ('.$e['type_label'].($e['date_label'] ? ', '.$e['date_label'] : '').')',
            array_slice($cards, 0, 5),
        );
        $summary = sprintf(
            '%s%d entities match "%s"%s; showing %d. %s%s',
            $capped ? 'More than ' : '',
            $page->total(),
            $input['query'],
            isset($input['year']) ? ' at '.Text::year((int) $input['year']) : '',
            count($cards),
            $top === [] ? '' : 'Top: '.implode('; ', $top).'. ',
            $chronicleRows === [] ? '' : count($chronicleRows).' chronicle(s) match too.',
        );

        return Reply::make(trim($summary), [
            'query' => $input['query'],
            'entities' => $cards,
            'total_entities' => $page->total(),
            'total_capped' => $capped,
            'chronicles' => $chronicleRows,
        ]);
    }
}
