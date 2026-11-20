<?php

declare(strict_types=1);

namespace App\Mcp\Tools;

use App\Actions\Graph\GetEntityGraphAction;
use App\Enums\RelationshipType;
use App\Mcp\Resources\ConnectionsApp;
use App\Mcp\Support\EntityCards;
use App\Mcp\Support\OutputSchemas;
use App\Mcp\Support\RelationshipLabels;
use App\Mcp\Support\Reply;
use App\Models\Entity;
use Illuminate\Contracts\JsonSchema\JsonSchema;
use Illuminate\Validation\Rule;
use Laravel\Mcp\Request;
use Laravel\Mcp\Response;
use Laravel\Mcp\ResponseFactory;
use Laravel\Mcp\Server\Attributes\Description;
use Laravel\Mcp\Server\Attributes\RendersApp;
use Laravel\Mcp\Server\Tool;
use Laravel\Mcp\Server\Tools\Annotations\IsIdempotent;
use Laravel\Mcp\Server\Tools\Annotations\IsReadOnly;

#[Description('The entities directly connected to one entity (rulers, successors, battles fought, birthplaces, treaties and so on) as nodes and typed edges, most confident and most important links first. Optionally filter by relationship type. Capped: it is the strongest links, not all of them.')]
#[RendersApp(resource: ConnectionsApp::class)]
#[IsReadOnly]
#[IsIdempotent]
class GetConnections extends Tool
{
    public function schema(JsonSchema $schema): array
    {
        return [
            'id' => $schema->string()->description('Entity uuid, from search_atlas.')->format('uuid')->required(),
            'types' => $schema->array()->items($schema->string()->enum(array_column(RelationshipType::cases(), 'value')))
                ->description('Only these relationship types, e.g. ["succeeded_by", "participated_in"].'),
            'limit' => $schema->integer()->description('Connections to return, 1 to 40 (default 25).')->min(1)->max(40),
        ];
    }

    public function outputSchema(JsonSchema $schema): array
    {
        return [
            'center' => OutputSchemas::entitySummary($schema)->required(),
            'nodes' => OutputSchemas::entityList($schema)->description('Connected entities, not including the center.')->required(),
            'edges' => $schema->array()->items($schema->object([
                'source' => $schema->string()->description('Entity id the relationship starts at.')->required(),
                'target' => $schema->string()->description('Entity id it points to.')->required(),
                'type' => $schema->string()->required(),
                'label' => $schema->string()->description('Verb phrase read from source to target, e.g. "rules".')->required(),
                'start_year' => $schema->integer()->nullable()->required(),
                'end_year' => $schema->integer()->nullable()->required(),
            ]))->required(),
        ];
    }

    public function handle(Request $request, GetEntityGraphAction $graph): Response|ResponseFactory
    {
        $input = $request->validate([
            'id' => ['required', 'uuid'],
            'types' => ['sometimes', 'nullable', 'array', 'max:30'],
            'types.*' => ['string', Rule::enum(RelationshipType::class)],
            'limit' => ['sometimes', 'nullable', 'integer', 'min:1', 'max:40'],
        ]);

        $center = Entity::query()->withGeoJson()->where('entities.entity_id', $input['id'])->first();
        if ($center === null) {
            return Response::error("No atlas entity has id {$input['id']}. Use search_atlas to find the right id.");
        }

        $g = $graph($center->entity_id, array_filter([
            'depth' => 1,
            'limit' => (int) ($input['limit'] ?? 25),
            'relationship_types' => $input['types'] ?? null,
        ]));

        $ids = collect($g['nodes'])->pluck('id')->reject(fn (string $id): bool => $id === $center->entity_id)->values()->all();
        $byId = Entity::query()->withGeoJson()->whereIn('entities.entity_id', $ids)->get()->keyBy('entity_id');
        // Keep the graph's order (strongest links first); a node could vanish between the two queries.
        $nodes = collect($ids)->map(fn (string $id) => $byId->get($id))->filter()->values();

        $cards = EntityCards::summaries($nodes->prepend($center));
        $centerCard = array_shift($cards);

        $edges = array_map(fn (array $e): array => [
            'source' => $e['source'],
            'target' => $e['target'],
            'type' => $e['relationship_type'],
            'label' => RelationshipLabels::label($e['relationship_type'], true),
            'start_year' => $e['start_year'],
            'end_year' => $e['end_year'],
        ], $g['edges']);

        $text = sprintf(
            '%s has %d connection(s) shown%s, to %d entities%s.',
            $centerCard['name'],
            count($edges),
            $g['truncated'] ? ' (more exist; this is the strongest set)' : '',
            count($cards),
            $cards === [] ? '' : ': '.implode('; ', array_map(fn (array $c): string => $c['name'], array_slice($cards, 0, 8))),
        );

        return Reply::make($text, ['center' => $centerCard, 'nodes' => $cards, 'edges' => $edges]);
    }
}
