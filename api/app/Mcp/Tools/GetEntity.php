<?php

declare(strict_types=1);

namespace App\Mcp\Tools;

use App\Actions\Chronicle\GetEntityChroniclesAction;
use App\Actions\Entity\GetEntityAction;
use App\Actions\Entity\ListEntitiesAction;
use App\Actions\Graph\GetEntityGraphAction;
use App\DTOs\EntityFilterData;
use App\Mcp\Resources\EntityCardApp;
use App\Mcp\Support\AtlasUrl;
use App\Mcp\Support\EntityCards;
use App\Mcp\Support\OutputSchemas;
use App\Mcp\Support\RelationshipLabels;
use App\Mcp\Support\Reply;
use App\Mcp\Support\Text;
use App\Models\Chronicle;
use App\Models\Entity;
use Illuminate\Contracts\JsonSchema\JsonSchema;
use Illuminate\Database\Eloquent\ModelNotFoundException;
use Illuminate\Support\Facades\DB;
use Laravel\Mcp\Request;
use Laravel\Mcp\Response;
use Laravel\Mcp\ResponseFactory;
use Laravel\Mcp\Server\Attributes\Description;
use Laravel\Mcp\Server\Attributes\RendersApp;
use Laravel\Mcp\Server\Tool;
use Laravel\Mcp\Server\Tools\Annotations\IsIdempotent;
use Laravel\Mcp\Server\Tools\Annotations\IsReadOnly;

#[Description('Full record of one atlas entity: dates, places, aliases, description, tags, its image with credit, its most important relationships and the chronicles it appears in. Identify it by id (from search_atlas), by Wikidata QID (e.g. Q517), or by name (best match: an exact name first, otherwise the top search hit).')]
#[RendersApp(resource: EntityCardApp::class)]
#[IsReadOnly]
#[IsIdempotent]
class GetEntity extends Tool
{
    private const DESCRIPTION_CHARS = 2000;

    private const RELATIONSHIPS = 12;

    private const CHRONICLES = 8;

    private const LOCATIONS = 10;

    public function schema(JsonSchema $schema): array
    {
        return [
            'id' => $schema->string()->description('Entity uuid, from search_atlas or an atlas_url.')->format('uuid'),
            'qid' => $schema->string()->description('Wikidata id such as "Q517". Use when id is unknown.')->pattern('^[Qq][0-9]+$'),
            'name' => $schema->string()->description('Entity name; the best match is returned. Prefer id or qid when ambiguous.')->min(2)->max(200),
        ];
    }

    public function outputSchema(JsonSchema $schema): array
    {
        return [
            'entity' => $schema->object([
                ...OutputSchemas::entityFields($schema),
                'aliases' => $schema->array()->items($schema->string())->required(),
                'description' => $schema->string()->description('Long description, at most 2000 characters.')->nullable()->required(),
                'wikidata_qid' => $schema->string()->nullable()->required(),
                'wikipedia_url' => $schema->string()->description('Opens the English Wikipedia article via Wikidata.')->nullable()->required(),
                'tags' => $schema->array()->items($schema->string())->required(),
                'locations' => $schema->array()->items($schema->object([
                    'name' => $schema->string()->nullable()->required(),
                    'lng' => $schema->number()->nullable()->required(),
                    'lat' => $schema->number()->nullable()->required(),
                    'is_primary' => $schema->boolean()->required(),
                ]))->required(),
                'image' => $schema->object([
                    'url' => $schema->string()->required(),
                    'thumb_url' => $schema->string()->required(),
                    'credit' => $schema->string()->nullable()->required(),
                    'license' => $schema->string()->nullable()->required(),
                    'source_url' => $schema->string()->nullable()->required(),
                ])->description('Wikimedia Commons image; show its credit and license with it.')->nullable()->required(),
                'relationships' => $schema->array()->items($schema->object([
                    'id' => $schema->string()->required(),
                    'type' => $schema->string()->required(),
                    'label' => $schema->string()->description('Verb phrase from this entity\'s point of view, e.g. "ruled by".')->required(),
                    'direction' => $schema->string()->enum(['out', 'in'])->required(),
                    'start_year' => $schema->integer()->nullable()->required(),
                    'end_year' => $schema->integer()->nullable()->required(),
                    'other' => $schema->object([
                        'id' => $schema->string()->required(),
                        'name' => $schema->string()->required(),
                        'type' => $schema->string()->required(),
                        'date_label' => $schema->string()->nullable()->required(),
                        'atlas_url' => $schema->string()->required(),
                    ])->required(),
                ]))->required(),
                'chronicles' => $schema->array()->items($schema->object([
                    'slug' => $schema->string()->required(),
                    'title' => $schema->string()->required(),
                    'atlas_url' => $schema->string()->required(),
                ]))->required(),
            ])->required(),
        ];
    }

    public function handle(
        Request $request,
        GetEntityAction $get,
        ListEntitiesAction $list,
        GetEntityGraphAction $graph,
        GetEntityChroniclesAction $chronicles,
    ): Response|ResponseFactory {
        $input = $request->validate([
            'id' => ['required_without_all:qid,name', 'nullable', 'uuid'],
            'qid' => ['required_without_all:id,name', 'nullable', 'regex:/^[Qq][0-9]+$/'],
            'name' => ['required_without_all:id,qid', 'nullable', 'string', 'min:2', 'max:200'],
        ], [
            'required_without_all' => 'Give one of id, qid or name.',
        ]);

        $id = $this->resolve($input, $list);
        if ($id === null) {
            $which = isset($input['id']) ? 'id '.$input['id'] : (isset($input['qid']) ? 'QID '.strtoupper($input['qid']) : 'name "'.$input['name'].'"');

            return Response::error("No atlas entity matches {$which}. Use search_atlas to find the right id.");
        }

        try {
            $entity = $get($id);
        } catch (ModelNotFoundException) {
            return Response::error("No atlas entity has id {$id}. Use search_atlas to find the right id.");
        }

        $range = EntityCards::years([$entity->entity_id])[$entity->entity_id] ?? null;
        $base = EntityCards::summary($entity, $range);

        $detail = $base + [
            'aliases' => $entity->aliases->pluck('name')->unique()->values()->all(),
            'description' => Text::limit($entity->description, self::DESCRIPTION_CHARS),
            'wikidata_qid' => $entity->wikidata_id,
            'wikipedia_url' => $entity->wikidata_id !== null
                ? 'https://www.wikidata.org/wiki/Special:GoToLinkedPage/enwiki/'.$entity->wikidata_id
                : null,
            'tags' => $entity->entityTags->pluck('tag')->values()->all(),
            'locations' => $this->locations($entity->entity_id),
            'image' => EntityCards::image($entity),
            'relationships' => $this->relationships($entity->entity_id, $graph),
            'chronicles' => $chronicles($entity->entity_id)->take(self::CHRONICLES)->map(fn (Chronicle $c): array => [
                'slug' => $c->slug,
                'title' => $c->title,
                'atlas_url' => AtlasUrl::chronicle($c->slug),
            ])->values()->all(),
        ];

        $text = sprintf(
            '%s (%s%s)%s%s %d relationship(s) and %d chronicle(s) listed.',
            $detail['name'],
            $detail['type_label'],
            $detail['date_label'] ? ', '.$detail['date_label'] : '',
            $detail['place'] ? ' at '.$detail['place'] : '',
            $detail['summary'] ? '. '.$detail['summary'] : '.',
            count($detail['relationships']),
            count($detail['chronicles']),
        );

        return Reply::make($text, ['entity' => $detail]);
    }

    /**
     * @param  array<string, mixed>  $input
     */
    private function resolve(array $input, ListEntitiesAction $list): ?string
    {
        if (isset($input['id'])) {
            return (string) $input['id'];
        }
        if (isset($input['qid'])) {
            return Entity::query()->where('wikidata_id', strtoupper((string) $input['qid']))->value('entity_id');
        }

        $name = trim((string) $input['name']);
        $exact = Entity::query()
            ->whereRaw('lower(name) = ?', [mb_strtolower($name)])
            ->orderByRaw('impact_score DESC NULLS LAST')
            ->value('entity_id');
        if ($exact !== null) {
            return $exact;
        }

        $hit = $list(EntityFilterData::fromArray(['search' => $name, 'per_page' => 1]))->items()[0] ?? null;

        return $hit?->entity_id;
    }

    /** @return list<array{name: string|null, lng: float|null, lat: float|null, is_primary: bool}> */
    private function locations(string $entityId): array
    {
        return DB::table('entity_locations')
            ->where('entity_id', $entityId)
            ->selectRaw("location_name, is_primary, CASE WHEN GeometryType(geom) = 'POINT' THEN ST_X(geom) END AS lng, CASE WHEN GeometryType(geom) = 'POINT' THEN ST_Y(geom) END AS lat")
            ->orderByDesc('is_primary')
            ->orderBy('location_name')
            ->limit(self::LOCATIONS)
            ->get()
            ->map(fn (object $r): array => [
                'name' => $r->location_name,
                'lng' => $r->lng !== null ? round((float) $r->lng, 5) : null,
                'lat' => $r->lat !== null ? round((float) $r->lat, 5) : null,
                'is_primary' => (bool) $r->is_primary,
            ])->all();
    }

    /**
     * The entity's edges, the graph's own order (most confident, then the
     * more important neighbour first), capped.
     *
     * @return list<array<string, mixed>>
     */
    private function relationships(string $entityId, GetEntityGraphAction $graph): array
    {
        $g = $graph($entityId, ['depth' => 1, 'limit' => self::RELATIONSHIPS]);
        $nodes = collect($g['nodes'])->keyBy('id');
        $rows = [];

        foreach ($g['edges'] as $edge) {
            $outgoing = $edge['source'] === $entityId;
            $other = $nodes->get($outgoing ? $edge['target'] : $edge['source']);
            if ($other === null) {
                continue;
            }
            $rows[] = [
                'id' => $edge['id'],
                'type' => $edge['relationship_type'],
                'label' => RelationshipLabels::label($edge['relationship_type'], $outgoing),
                'direction' => $outgoing ? 'out' : 'in',
                'start_year' => $edge['start_year'],
                'end_year' => $edge['end_year'],
                'other' => [
                    'id' => $other['id'],
                    'name' => $other['name'],
                    'type' => $other['entity_type'],
                    'date_label' => Text::dateLabel($other['start_year'], $other['end_year']),
                    'atlas_url' => AtlasUrl::entity($other['id']),
                ],
            ];
        }

        return $rows;
    }
}
